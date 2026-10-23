import { useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  FileCode2,
  Folder,
  Search,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import type { WorkspaceFile } from "@/types/contracts";

type TreeNode = {
  name: string;
  path: string;
  folders: Map<string, TreeNode>;
  files: WorkspaceFile[];
  count: number;
};

function treeFor(files: WorkspaceFile[]): TreeNode {
  const root: TreeNode = {
    name: "",
    path: "",
    folders: new Map(),
    files: [],
    count: files.length,
  };
  for (const file of files) {
    const parts = file.path.split("/");
    let node = root;
    for (const part of parts.slice(0, -1)) {
      const path = node.path ? `${node.path}/${part}` : part;
      if (!node.folders.has(part)) {
        node.folders.set(part, {
          name: part,
          path,
          folders: new Map(),
          files: [],
          count: 0,
        });
      }
      node = node.folders.get(part)!;
      node.count += 1;
    }
    node.files.push(file);
  }
  return root;
}

const labelFor = (status: string) =>
  ({
    added: "Mới",
    deleted: "Đã xóa",
    untracked: "Chưa theo dõi",
    modified: "Đã sửa",
  })[status as "added" | "deleted" | "untracked" | "modified"] ?? "Đã sửa";

function diffClass(line: string): string {
  if (line.startsWith("+") && !line.startsWith("+++")) return "diff-added";
  if (line.startsWith("-") && !line.startsWith("---")) return "diff-removed";
  if (line.startsWith("@@")) return "diff-hunk";
  return "";
}

export function WorkspaceDiffBrowser({
  files,
}: {
  files: WorkspaceFile[];
}): React.JSX.Element {
  const [query, setQuery] = useState("");
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [visibleLines, setVisibleLines] = useState(300);
  const visibleFiles = files.filter((file) =>
    file.path.toLowerCase().includes(query.trim().toLowerCase()),
  );
  const selected =
    visibleFiles.find((file) => file.path === selectedPath) ?? visibleFiles[0];
  const tree = treeFor(visibleFiles);
  const lines = selected?.diff.split("\n") ?? [];
  if (lines.at(-1) === "") lines.pop();

  function select(path: string) {
    setSelectedPath(path);
    setVisibleLines(300);
  }

  function toggle(path: string) {
    setCollapsed((current) => {
      const next = new Set(current);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }

  function renderNode(node: TreeNode, depth: number): React.ReactNode {
    const folders = [...node.folders.values()].sort((a, b) =>
      a.name.localeCompare(b.name),
    );
    const folderItems = folders.map((folder) => (
      <div key={folder.path}>
        <button
          type="button"
          className="run-workspace-tree-row run-workspace-folder"
          style={{ paddingLeft: 12 + depth * 16 }}
          aria-expanded={!collapsed.has(folder.path)}
          onClick={() => toggle(folder.path)}
        >
          {collapsed.has(folder.path) ? (
            <ChevronRight size={14} />
          ) : (
            <ChevronDown size={14} />
          )}
          <Folder size={15} aria-hidden="true" />
          <span className="run-workspace-tree-name">{folder.name}</span>
          <span className="run-workspace-folder-count">{folder.count}</span>
        </button>
        {!collapsed.has(folder.path) && renderNode(folder, depth + 1)}
      </div>
    ));
    const fileItems = [...node.files]
      .sort((a, b) => a.path.localeCompare(b.path))
      .map((file) => (
        <button
          key={file.path}
          type="button"
          className={`run-workspace-tree-row run-workspace-file${selected?.path === file.path ? " is-selected" : ""}`}
          style={{ paddingLeft: 30 + depth * 16 }}
          aria-current={selected?.path === file.path ? "true" : undefined}
          title={file.path}
          onClick={() => select(file.path)}
        >
          <FileCode2 size={15} aria-hidden="true" />
          <span className="run-workspace-tree-name">
            {file.path.split("/").at(-1)}
          </span>
          <span
            className={`run-workspace-status status-${file.status}`}
            aria-label={labelFor(file.status)}
          >
            {file.status === "deleted"
              ? "D"
              : file.status === "modified"
                ? "M"
                : "A"}
          </span>
        </button>
      ));
    return (
      <>
        {folderItems}
        {fileItems}
      </>
    );
  }

  return (
    <div className="run-workspace-browser">
      <aside className="run-workspace-sidebar" aria-label="File thay đổi">
        <div className="run-workspace-sidebar-head">
          <strong>File thay đổi</strong>
          <span>{files.length}</span>
        </div>
        <label className="run-workspace-search">
          <Search size={15} aria-hidden="true" />
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Tìm file..."
            aria-label="Tìm file thay đổi"
          />
        </label>
        <div className="run-workspace-tree">
          {visibleFiles.length ? (
            renderNode(tree, 0)
          ) : (
            <p className="run-workspace-no-match">Không tìm thấy file.</p>
          )}
        </div>
      </aside>
      <div className="run-workspace-preview">
        {selected ? (
          <>
            <div className="run-workspace-preview-head">
              <div className="run-workspace-preview-path">
                <FileCode2 size={16} aria-hidden="true" />
                <strong>{selected.path}</strong>
              </div>
              <span
                className={`run-workspace-preview-status status-${selected.status}`}
              >
                {labelFor(selected.status)}
              </span>
            </div>
            {lines.length ? (
              <div
                className="run-workspace-diff"
                tabIndex={0}
                aria-label={`Git diff của ${selected.path}`}
              >
                {lines.slice(0, visibleLines).map((line, index) => (
                  <div key={index} className={diffClass(line)}>
                    <code>{line || " "}</code>
                  </div>
                ))}
              </div>
            ) : (
              <p className="run-workspace-empty">
                Không có bản xem diff cho file này. Hãy kiểm tra file trực tiếp
                trong workspace.
              </p>
            )}
            {lines.length > visibleLines && (
              <div className="run-workspace-more">
                <Button
                  variant="outline"
                  onClick={() => setVisibleLines((count) => count + 300)}
                >
                  Xem thêm diff
                </Button>
              </div>
            )}
            {selected.truncated && (
              <p className="run-workspace-file-note">
                Bản xem trước của file này bị giới hạn dung lượng hoặc không hỗ
                trợ định dạng.
              </p>
            )}
          </>
        ) : (
          <p className="run-workspace-empty">Chọn một file để xem thay đổi.</p>
        )}
      </div>
    </div>
  );
}
