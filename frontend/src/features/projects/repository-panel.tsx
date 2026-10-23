import { useState } from "react";
import type { FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { ErrorNotice, useCommand } from "@/components/shared/business-ui";
import {
  commands,
  repositoryFileOptions,
  repositoryOptions,
} from "@/lib/business-api";
import type { Project } from "@/types/contracts";

export function RepositoryPanel({ project }: { project: Project }): React.JSX.Element {
  const [path, setPath] = useState("");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState("");
  const connected = Boolean(project.repository_path);
  const repository = useQuery({ ...repositoryOptions(project.id), enabled: connected });
  const file = useQuery({
    ...repositoryFileOptions(project.id, selected),
    enabled: connected && Boolean(selected),
  });
  const connect = useCommand((value: string) => commands.connectRepository(project.id, value), () => {
    setPath("");
    setSelected("");
  });
  const pick = useCommand(() => commands.pickRepository(project.id), () => {
    setSelected("");
  });
  const disconnect = useCommand(() => commands.disconnectRepository(project.id), () => {
    setSelected("");
  });

  function submit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    connect.mutate(path.trim());
  }

  const files = repository.data?.files.filter((name) =>
    name.toLocaleLowerCase().includes(search.toLocaleLowerCase()),
  ) ?? [];

  return (
    <section className="panel content-panel repository-panel">
      <div className="repository-heading">
        <div>
          <h2>Repository trên máy</h2>
          <p>
            Kết nối một thư mục Git để xem mã nguồn. Hiện tại AI chưa sửa file trong repository này.
          </p>
        </div>
        {connected && (
          <Button variant="outline" disabled={disconnect.isPending} onClick={() => disconnect.mutate()}>
            Ngắt kết nối
          </Button>
        )}
      </div>
      <ErrorNotice error={pick.error || connect.error || disconnect.error || repository.error} />
      {!connected ? (
        <div className="repository-chooser">
          <Button
            disabled={pick.isPending || connect.isPending || project.status !== "active"}
            onClick={() => pick.mutate()}
          >
            {pick.isPending ? "Đang chờ chọn thư mục…" : "Chọn thư mục Git"}
          </Button>
          <p>Hộp thoại chọn thư mục sẽ mở trên máy chạy backend.</p>
          <details>
            <summary>Nhập đường dẫn thủ công</summary>
            <form onSubmit={submit}>
              <label htmlFor="repository-path">Đường dẫn tuyệt đối tới thư mục gốc Git</label>
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
                <Button type="submit" disabled={connect.isPending || pick.isPending || project.status !== "active"}>
                  {connect.isPending ? "Đang kết nối…" : "Kết nối"}
                </Button>
              </div>
            </form>
          </details>
        </div>
      ) : (
        <>
          {repository.data && (
            <div className="repository-meta">
              <span>{repository.data.path}</span>
              <span>Nhánh: {repository.data.branch || "detached HEAD"}</span>
              <span>Commit: {repository.data.head.slice(0, 12)}</span>
              <span>{repository.data.dirty ? "Có thay đổi chưa commit" : "Không có thay đổi tracked"}</span>
              <Button variant="outline" onClick={() => {
                void repository.refetch();
                if (selected) void file.refetch();
              }}>
                Làm mới
              </Button>
            </div>
          )}
          {repository.isPending && <p>Đang đọc repository…</p>}
          {repository.data && (
            <div className="repository-browser">
              <div className="repository-files">
                <label htmlFor="repository-search">Tìm file ({repository.data.files.length})</label>
                <input
                  id="repository-search"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="Tên hoặc đường dẫn file"
                />
                <div className="repository-file-list">
                  {files.slice(0, 100).map((name) => (
                    <button
                      className={selected === name ? "repository-file selected" : "repository-file"}
                      type="button"
                      key={name}
                      onClick={() => setSelected(name)}
                    >
                      {name}
                    </button>
                  ))}
                  {files.length > 100 && <p>Hiển thị 100 file đầu. Hãy tìm để thu hẹp kết quả.</p>}
                  {!files.length && <p>Không có file phù hợp.</p>}
                </div>
              </div>
              <div className="repository-preview">
                <h3>{selected || "Chọn một file để xem"}</h3>
                <ErrorNotice error={file.error} />
                {selected && file.isPending && <p>Đang tải file…</p>}
                {selected && file.data && <pre><code>{file.data.content}</code></pre>}
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}
