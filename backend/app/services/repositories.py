"""Read-only access to a PM-selected local Git working tree."""

import os
import subprocess
import threading
from pathlib import Path

from app.core.errors import DomainError, conflict
from app.services.projects import project_for

MAX_FILES = 2000
MAX_FILE_BYTES = 256 * 1024
_picker_lock = threading.Lock()


def _git(root: Path, *args: str) -> bytes:
    try:
        result = subprocess.run(
            ["git", "-c", "core.fsmonitor=false", "-C", str(root), *args],
            capture_output=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise DomainError(
            422, "repository_unavailable", "Cannot inspect this Git repository"
        ) from None
    if result.returncode:
        raise DomainError(422, "invalid_repository", "A local Git working tree is required")
    return result.stdout


def _safe_name(name: str) -> bool:
    parts = Path(name).parts
    if not parts or Path(name).is_absolute() or ".." in parts:
        return False
    for part in parts:
        lower = part.lower()
        if lower in {".git", "node_modules", ".venv", "venv", "dist", "build", "__pycache__"}:
            return False
        if lower == ".env" or lower.startswith(".env."):
            return False
        if lower.endswith((".pem", ".key", ".p12", ".pfx")):
            return False
    return True


def _tracked(root: Path) -> list[str]:
    output = _git(root, "ls-files", "-z", "--cached", "--full-name")
    if len(output) > 2_000_000:
        raise DomainError(413, "repository_too_large", "Too many tracked files")
    names = [os.fsdecode(name) for name in output.split(b"\0") if name]
    if len(names) > MAX_FILES:
        raise DomainError(413, "repository_too_large", "Too many tracked files")
    return sorted(name for name in names if _safe_name(name))


def _root(path: str) -> Path:
    candidate = Path(path).expanduser()
    if not candidate.is_absolute() or str(candidate).startswith("\\\\"):
        raise DomainError(422, "invalid_repository_path", "Choose an absolute local folder")
    root = candidate.resolve()
    if not root.is_dir():
        raise DomainError(422, "invalid_repository_path", "Repository folder does not exist")
    git_root = Path(os.fsdecode(_git(root, "rev-parse", "--show-toplevel")).strip()).resolve()
    if git_root != root:
        raise DomainError(422, "invalid_repository_path", "Choose the root of a Git repository")
    _git(root, "rev-parse", "--verify", "HEAD")
    return root


def connect(session, project_id: str, user: str, path: str):
    project = project_for(session, project_id, user, lock=True)
    if project.status != "active":
        conflict("Archived projects cannot connect a repository")
    root = _root(path)
    _tracked(root)
    project.repository_path = str(root)
    session.flush()
    return project


def _choose_directory() -> str:
    try:
        import tkinter as tk
        from tkinter import filedialog

        window = tk.Tk()
        try:
            window.withdraw()
            window.attributes("-topmost", True)
            return filedialog.askdirectory(parent=window, title="Chọn thư mục gốc Git")
        finally:
            window.destroy()
    except Exception:
        raise DomainError(
            503, "folder_picker_unavailable", "Folder picker needs an interactive desktop"
        ) from None


def pick_and_connect(session, project_id: str, user: str):
    project = project_for(session, project_id, user)
    if project.status != "active":
        conflict("Archived projects cannot connect a repository")
    if not _picker_lock.acquire(blocking=False):
        conflict("A folder picker is already open")
    try:
        path = _choose_directory()
    finally:
        _picker_lock.release()
    return connect(session, project_id, user, path) if path else project


def disconnect(session, project_id: str, user: str):
    project = project_for(session, project_id, user, lock=True)
    project.repository_path = None
    session.flush()
    return project


def _connected(session, project_id: str, user: str) -> Path:
    project = project_for(session, project_id, user)
    if not project.repository_path:
        raise DomainError(404, "repository_not_connected", "No repository is connected")
    root = Path(project.repository_path)
    if not root.is_dir() or _root(str(root)) != root:
        raise DomainError(409, "repository_unavailable", "Connected repository is unavailable")
    return root


def inspect(session, project_id: str, user: str):
    root = _connected(session, project_id, user)
    branch = os.fsdecode(_git(root, "branch", "--show-current")).strip() or None
    head = os.fsdecode(_git(root, "rev-parse", "HEAD")).strip()
    dirty = bool(_git(root, "status", "--porcelain", "--untracked-files=no"))
    return {
        "path": str(root),
        "branch": branch,
        "head": head,
        "dirty": dirty,
        "files": _tracked(root),
    }


def read_file(session, project_id: str, user: str, name: str):
    root = _connected(session, project_id, user)
    if not _safe_name(name) or name not in _tracked(root):
        raise DomainError(404, "file_not_found", "File is not available")
    file = root / name
    if not file.resolve().is_relative_to(root) or not file.is_file() or file.is_symlink():
        raise DomainError(404, "file_not_found", "File is not available")
    try:
        with file.open("rb") as source:
            content = source.read(MAX_FILE_BYTES + 1)
        if len(content) > MAX_FILE_BYTES or b"\0" in content:
            raise DomainError(415, "file_not_text", "Only small text files can be viewed")
        return {"path": name, "content": content.decode("utf-8")}
    except (OSError, UnicodeDecodeError):
        raise DomainError(415, "file_not_text", "Only UTF-8 text files can be viewed") from None
