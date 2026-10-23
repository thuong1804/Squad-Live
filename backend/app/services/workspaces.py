"""Isolated Git worktrees attached to existing workflow runs."""

import difflib
import os
import subprocess
from pathlib import Path

from app.core.errors import DomainError, conflict
from app.models.entities import RunWorkspace
from app.services import repositories
from app.services.projects import item_for, project_for
from app.services.workflows import run_for

MAX_DIFF_BYTES = 512 * 1024
MAX_CHANGED_FILES = 100


def _run(root: Path, *args: str) -> bytes:
    # Git checkout hooks are disabled; repository build/test commands are never run here.
    empty_hooks = os.devnull
    try:
        result = subprocess.run(
            [
                "git",
                "-c",
                "core.fsmonitor=false",
                "-c",
                f"core.hooksPath={empty_hooks}",
                "-C",
                str(root),
                *args,
            ],
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise DomainError(
            503, "workspace_unavailable", "Git workspace command did not complete"
        ) from None
    if result.returncode:
        raise DomainError(409, "workspace_conflict", "Git workspace could not be prepared or read")
    return result.stdout


def _text(value: bytes) -> str:
    return os.fsdecode(value).strip()


def _common_dir(root: Path) -> Path:
    value = Path(_text(_run(root, "rev-parse", "--git-common-dir")))
    return (root / value).resolve()


def _workspace_root(settings) -> Path:
    root = settings.workspace_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _verify(workspace: RunWorkspace, settings) -> Path:
    root = _workspace_root(settings)
    target = Path(workspace.worktree_path)
    if target.parent != root or target.name != workspace.run_id or not target.is_dir():
        raise DomainError(409, "workspace_unavailable", "Run workspace is unavailable")
    if Path(_text(_run(target, "rev-parse", "--show-toplevel"))).resolve() != target:
        raise DomainError(409, "workspace_unavailable", "Run workspace is unavailable")
    if _common_dir(target) != _common_dir(Path(workspace.source_path)):
        raise DomainError(409, "workspace_unavailable", "Run workspace is unavailable")
    return target


def prepare(session, run_id: str, user: str, settings) -> RunWorkspace:
    run = run_for(session, run_id, user)
    existing = session.get(RunWorkspace, run_id)
    if existing:
        _verify(existing, settings)
        return existing
    item = item_for(session, run.work_item_id, user)
    project = project_for(session, item.project_id, user)
    if project.status != "active":
        conflict("Cannot prepare a workspace for an archived project")
    source = repositories._connected(session, project.id, user)
    if _run(source, "status", "--porcelain", "--untracked-files=all"):
        raise DomainError(
            409,
            "workspace_source_dirty",
            "Commit or remove source repository changes before preparing a workspace",
        )
    base_commit = _text(_run(source, "rev-parse", "HEAD"))
    base_branch = _text(_run(source, "branch", "--show-current")) or None
    root = settings.workspace_root.resolve()
    if root == source or root.is_relative_to(source):
        conflict("Workspace storage must be outside the connected repository")
    root = _workspace_root(settings)
    target = root / run_id
    if target.exists() or target.is_symlink():
        # Recover an orphan only if it is the exact worktree created for this run.
        if (
            not target.is_dir()
            or _common_dir(target) != _common_dir(source)
            or _run(target, "status", "--porcelain", "--untracked-files=all")
        ):
            conflict("Workspace path is already occupied")
        base_commit = _text(_run(target, "rev-parse", "HEAD"))
    else:
        _run(source, "worktree", "add", "--detach", str(target), base_commit)
    workspace = RunWorkspace(
        run_id=run_id,
        source_path=str(source),
        worktree_path=str(target),
        base_commit=base_commit,
        base_branch=base_branch,
    )
    session.add(workspace)
    session.flush()
    return workspace


def workspace_for(session, run_id: str, user: str) -> RunWorkspace | None:
    run_for(session, run_id, user)
    return session.get(RunWorkspace, run_id)


def inspect(workspace: RunWorkspace, settings) -> dict:
    root = _verify(workspace, settings)
    tracked_raw = _run(
        root, "diff", "--name-status", "--no-renames", "-z", workspace.base_commit, "--"
    )
    untracked_raw = _run(root, "ls-files", "--others", "--exclude-standard", "-z")
    tracked_parts = [part for part in tracked_raw.split(b"\0") if part]
    tracked_all = [
        (os.fsdecode(tracked_parts[index + 1]), os.fsdecode(tracked_parts[index]))
        for index in range(0, len(tracked_parts), 2)
    ]
    untracked_all = [os.fsdecode(name) for name in untracked_raw.split(b"\0") if name]
    tracked = [(name, status) for name, status in tracked_all if repositories._safe_name(name)]
    untracked = [name for name in untracked_all if repositories._safe_name(name)]
    truncated = len(tracked) + len(untracked) > MAX_CHANGED_FILES or (
        len(tracked) != len(tracked_all) or len(untracked) != len(untracked_all)
    )
    tracked = tracked[:MAX_CHANGED_FILES]
    untracked = untracked[: max(0, MAX_CHANGED_FILES - len(tracked))]
    files = []
    remaining = MAX_DIFF_BYTES
    for name, git_status in tracked:
        patch = _run(
            root,
            "diff",
            "--no-ext-diff",
            "--no-textconv",
            "--no-color",
            workspace.base_commit,
            "--",
            name,
        )
        clipped = len(patch) > remaining
        files.append(
            {
                "path": name,
                "status": {"A": "added", "D": "deleted"}.get(git_status, "modified"),
                "diff": patch[:remaining].decode("utf-8", errors="replace"),
                "truncated": clipped,
            }
        )
        remaining = max(0, remaining - len(patch))
        truncated = truncated or clipped
    for name in untracked:
        file = root / name
        patch = b""
        unavailable = False
        if file.is_symlink() or not file.is_file() or not file.resolve().is_relative_to(root):
            unavailable = True
        else:
            try:
                content = file.read_bytes()
                if len(content) > 64 * 1024 or b"\0" in content:
                    unavailable = True
                else:
                    lines = content.decode("utf-8").splitlines(keepends=True)
                    patch = "".join(
                        difflib.unified_diff([], lines, fromfile="/dev/null", tofile=f"b/{name}")
                    ).encode("utf-8")
            except (OSError, UnicodeDecodeError):
                unavailable = True
        clipped = len(patch) > remaining
        files.append(
            {
                "path": name,
                "status": "untracked",
                "diff": patch[:remaining].decode("utf-8", errors="replace"),
                "truncated": unavailable or clipped,
            }
        )
        remaining = max(0, remaining - len(patch))
        truncated = truncated or unavailable or clipped
    return {
        "run_id": workspace.run_id,
        "source_path": workspace.source_path,
        "worktree_path": workspace.worktree_path,
        "base_commit": workspace.base_commit,
        "base_branch": workspace.base_branch,
        "created_at": workspace.created_at,
        "changed_files": [name for name, _ in tracked],
        "untracked_files": untracked,
        "files": files,
        "truncated": truncated,
    }
