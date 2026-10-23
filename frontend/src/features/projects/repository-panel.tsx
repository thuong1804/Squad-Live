import { useDeferredValue, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Check,
  ChevronRight,
  Copy,
  FileCode2,
  Folder,
  FolderOpen,
  GitBranch,
  HardDrive,
  RotateCw,
  Search,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ErrorNotice, useCommand } from "@/components/shared/business-ui";
import {
  commands,
  repositoryFileOptions,
  repositoryOptions,
} from "@/lib/business-api";
import type { Project } from "@/types/contracts";

interface TreeNode {
  name: string;
  path: string;
  children: TreeNode[] | null;
}

function fileTree(files: string[]): TreeNode[] {
  const root: TreeNode = { name: "", path: "", children: [] };
  const folders = new Map<string, TreeNode>([["", root]]);
  for (const file of files) {
    const parts = file.split("/");
    let parent = root;
    for (let index = 0; index < parts.length; index += 1) {
      const path = parts.slice(0, index + 1).join("/");
      if (index === parts.length - 1) {
        parent.children?.push({ name: parts[index], path, children: null });
      } else {
        let folder = folders.get(path);
        if (!folder) {
          folder = { name: parts[index], path, children: [] };
          folders.set(path, folder);
          parent.children?.push(folder);
        }
        parent = folder;
      }
    }
  }
  function sort(nodes: TreeNode[]): TreeNode[] {
    nodes.sort(
      (left, right) =>
        Number(right.children !== null) - Number(left.children !== null) ||
        left.name.localeCompare(right.name),
    );
    nodes.forEach((node) => {
      if (node.children) sort(node.children);
    });
    return nodes;
  }
  return sort(root.children ?? []);
}

const fileLabel = (path: string): string => path.split("/").at(-1) ?? path;

export function RepositoryPanel({
  project,
}: {
  project: Project;
}): React.JSX.Element {
  const [path, setPath] = useState("");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState("");
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [visibleLines, setVisibleLines] = useState(400);
  const [copied, setCopied] = useState(false);
  const connected = Boolean(project.repository_path);
  const repository = useQuery({
    ...repositoryOptions(project.id),
    enabled: connected,
  });
  const file = useQuery({
    ...repositoryFileOptions(project.id, selected),
    enabled: connected && Boolean(selected),
  });
  const connect = useCommand(
    (value: string) => commands.connectRepository(project.id, value),
    () => {
      setPath("");
      setSelected("");
    },
  );
  const pick = useCommand(
    () => commands.pickRepository(project.id),
    () => setSelected(""),
  );
  const disconnect = useCommand(
    () => commands.disconnectRepository(project.id),
    () => setSelected(""),
  );

  const tree = useMemo(
    () => fileTree(repository.data?.files ?? []),
    [repository.data?.files],
  );
  const deferredSearch = useDeferredValue(search.trim().toLocaleLowerCase());
  const matches = useMemo(
    () =>
      repository.data?.files.filter((name) =>
        name.toLocaleLowerCase().includes(deferredSearch),
      ) ?? [],
    [repository.data?.files, deferredSearch],
  );
  const lines = useMemo(() => {
    if (!file.data || file.data.path !== selected) return [];
    const sourceLines = file.data.content.replaceAll("\r\n", "\n").split("\n");
    if (sourceLines.at(-1) === "") sourceLines.pop();
    return sourceLines;
  }, [file.data, selected]);

  function submit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    connect.mutate(path.trim());
  }

  function selectFile(name: string): void {
    setSelected(name);
    setVisibleLines(400);
    setCopied(false);
    const parts = name.split("/");
    setExpanded((current) => {
      const next = { ...current };
      for (let index = 1; index < parts.length; index += 1) {
        next[parts.slice(0, index).join("/")] = true;
      }
      return next;
    });
  }

  function renderNodes(nodes: TreeNode[], depth = 0): React.JSX.Element[] {
    return nodes.flatMap((node) => {
      const folder = node.children !== null;
      const open = expanded[node.path] ?? depth === 0;
      const row = (
        <button
          key={node.path}
          type="button"
          className={`repository-tree-row${selected === node.path ? " selected" : ""}`}
          style={{ paddingInlineStart: `${12 + depth * 18}px` }}
          aria-expanded={folder ? open : undefined}
          aria-current={!folder && selected === node.path ? "true" : undefined}
          title={node.path}
          onClick={() =>
            folder
              ? setExpanded((current) => ({ ...current, [node.path]: !open }))
              : selectFile(node.path)
          }
        >
          {folder ? (
            <ChevronRight
              className={
                open ? "repository-chevron open" : "repository-chevron"
              }
              size={14}
            />
          ) : (
            <span className="repository-chevron-spacer" />
          )}
          {folder ? (
            open ? (
              <FolderOpen className="repository-folder-icon" size={16} />
            ) : (
              <Folder className="repository-folder-icon" size={16} />
            )
          ) : (
            <FileCode2 className="repository-file-icon" size={16} />
          )}
          <span className="repository-tree-name">{node.name}</span>
        </button>
      );
      return folder && open
        ? [row, ...renderNodes(node.children ?? [], depth + 1)]
        : [row];
    });
  }

  async function copySource(): Promise<void> {
    if (!file.data) return;
    try {
      await navigator.clipboard.writeText(file.data.content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  }

  return (
    <section
      className="panel content-panel repository-panel"
      aria-labelledby="repository-title"
    >
      <div className="repository-heading">
        <div className="repository-heading-title">
          <span className="repository-heading-mark">
            <HardDrive size={17} aria-hidden="true" />
          </span>
          <div>
            <h2 id="repository-title">Mã nguồn dự án</h2>
            <p>
              Duyệt repository Git trên máy. AI chưa chỉnh sửa mã nguồn tại đây.
            </p>
          </div>
        </div>
        {connected && (
          <Button
            variant="outline"
            disabled={disconnect.isPending}
            onClick={() => disconnect.mutate()}
          >
            Ngắt kết nối
          </Button>
        )}
      </div>
      <ErrorNotice
        error={
          pick.error || connect.error || disconnect.error || repository.error
        }
      />
      {!connected ? (
        <div className="repository-chooser">
          <Button
            disabled={
              pick.isPending || connect.isPending || project.status !== "active"
            }
            onClick={() => pick.mutate()}
          >
            {pick.isPending ? "Đang chờ chọn thư mục…" : "Chọn thư mục Git"}
          </Button>
          <p>Hộp thoại chọn thư mục sẽ mở trên máy chạy backend.</p>
          <details>
            <summary>Nhập đường dẫn thủ công</summary>
            <form onSubmit={submit}>
              <label htmlFor="repository-path">
                Đường dẫn tuyệt đối tới thư mục gốc Git
              </label>
              <div className="repository-connect">
                <input
                  id="repository-path"
                  type="text"
                  value={path}
                  onChange={(event) => setPath(event.target.value)}
                  placeholder="D:\\du-an\\my-app"
                  maxLength={4096}
                  required
                  disabled={project.status !== "active" || pick.isPending}
                />
                <Button
                  type="submit"
                  disabled={
                    connect.isPending ||
                    pick.isPending ||
                    project.status !== "active"
                  }
                >
                  {connect.isPending ? "Đang kết nối…" : "Kết nối"}
                </Button>
              </div>
            </form>
          </details>
        </div>
      ) : (
        <div className="repository-workspace">
          {repository.data && (
            <div className="repository-toolbar">
              <div className="repository-toolbar-main">
                <span className="repository-branch">
                  <GitBranch size={15} aria-hidden="true" />
                  {repository.data.branch || "detached HEAD"}
                </span>
                <span
                  className="repository-commit"
                  title={repository.data.head}
                >
                  Commit <code>{repository.data.head.slice(0, 10)}</code>
                </span>
                <span
                  className={`repository-state ${repository.data.dirty ? "is-dirty" : ""}`}
                >
                  <span className="repository-state-dot" />
                  {repository.data.dirty ? "Có thay đổi" : "Working tree sạch"}
                </span>
              </div>
              <Button
                variant="outline"
                onClick={() => {
                  void repository.refetch();
                  if (selected) void file.refetch();
                }}
              >
                <RotateCw size={14} aria-hidden="true" /> Làm mới
              </Button>
            </div>
          )}
          {repository.isPending && (
            <p className="repository-loading">Đang đọc repository…</p>
          )}
          {repository.data && (
            <>
              <div className="repository-location" title={repository.data.path}>
                <HardDrive size={13} aria-hidden="true" />
                <span>{repository.data.path}</span>
              </div>
              <div className="repository-browser">
                <nav
                  className="repository-files"
                  aria-label="Cây file repository"
                >
                  <div className="repository-sidebar-heading">
                    <strong>Files</strong>
                    <span>{repository.data.files.length}</span>
                  </div>
                  <label
                    className="repository-search"
                    htmlFor="repository-search"
                  >
                    <Search size={15} aria-hidden="true" />
                    <input
                      id="repository-search"
                      value={search}
                      onChange={(event) => setSearch(event.target.value)}
                      placeholder="Tìm file…"
                      autoComplete="off"
                    />
                  </label>
                  <div className="repository-file-list">
                    {deferredSearch ? (
                      <>
                        <p className="repository-result-count">
                          {matches.length} kết quả
                        </p>
                        {matches.slice(0, 100).map((name) => (
                          <button
                            className={`repository-search-result${selected === name ? " selected" : ""}`}
                            type="button"
                            key={name}
                            onClick={() => selectFile(name)}
                          >
                            <FileCode2 size={15} aria-hidden="true" />
                            <span>
                              <strong>{fileLabel(name)}</strong>
                              <small>{name}</small>
                            </span>
                          </button>
                        ))}
                        {matches.length > 100 && (
                          <p className="repository-result-count">
                            Hiển thị 100 file đầu. Hãy tìm cụ thể hơn.
                          </p>
                        )}
                        {!matches.length && (
                          <p className="repository-empty-list">
                            Không có file phù hợp.
                          </p>
                        )}
                      </>
                    ) : tree.length ? (
                      renderNodes(tree)
                    ) : (
                      <p className="repository-empty-list">
                        Không có file để hiển thị.
                      </p>
                    )}
                  </div>
                </nav>
                <div className="repository-preview">
                  {selected ? (
                    <>
                      <div className="repository-file-heading">
                        <div className="repository-breadcrumb" title={selected}>
                          <FileCode2 size={16} aria-hidden="true" />
                          <span>
                            {selected.split("/").slice(0, -1).join(" / ")}
                          </span>
                          {selected.includes("/") && (
                            <ChevronRight size={14} aria-hidden="true" />
                          )}
                          <strong>{fileLabel(selected)}</strong>
                        </div>
                        <Button
                          variant="outline"
                          onClick={() => void copySource()}
                          disabled={!file.data}
                          aria-label="Sao chép nội dung file"
                        >
                          {copied ? (
                            <Check size={14} aria-hidden="true" />
                          ) : (
                            <Copy size={14} aria-hidden="true" />
                          )}
                          {copied ? "Đã sao chép" : "Sao chép"}
                        </Button>
                      </div>
                      <ErrorNotice error={file.error} />
                      {file.isPending && (
                        <p className="repository-loading">Đang tải file…</p>
                      )}
                      {file.data && file.data.path === selected && (
                        <>
                          <div className="repository-file-info">
                            <span>Source</span>
                            <span>{lines.length} dòng · UTF-8 · Chỉ đọc</span>
                          </div>
                          <div
                            className="repository-code-scroll"
                            tabIndex={0}
                            aria-label={`Mã nguồn ${selected}`}
                          >
                            {lines.slice(0, visibleLines).map((line, index) => (
                              <div className="repository-code-line" key={index}>
                                <span
                                  className="repository-line-number"
                                  aria-hidden="true"
                                >
                                  {index + 1}
                                </span>
                                <code>{line || " "}</code>
                              </div>
                            ))}
                          </div>
                          {lines.length > visibleLines && (
                            <div className="repository-more-lines">
                              <Button
                                variant="outline"
                                onClick={() =>
                                  setVisibleLines((count) => count + 400)
                                }
                              >
                                Xem thêm dòng ({lines.length - visibleLines} còn
                                lại)
                              </Button>
                            </div>
                          )}
                        </>
                      )}
                    </>
                  ) : (
                    <div className="repository-empty-preview">
                      <FileCode2 size={28} aria-hidden="true" />
                      <h3>Chọn file để xem mã nguồn</h3>
                      <p>Dùng cây thư mục hoặc tìm kiếm để mở một file.</p>
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </section>
  );
}
