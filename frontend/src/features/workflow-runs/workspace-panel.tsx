import { useState } from "react";
import { useQuery, useSuspenseQuery } from "@tanstack/react-query";
import {
  GitBranch,
  GitCompareArrows,
  FolderGit2,
  RotateCw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ErrorNotice, useCommand } from "@/components/shared/business-ui";
import {
  commands,
  projectOptions,
  repositoryOptions,
  workspaceOptions,
  workspaceEditsOptions,
} from "@/lib/business-api";
import { useAIAccess } from "@/features/ai/settings";
import { WorkspaceDiffBrowser } from "./workspace-diff-browser";

const editErrorMessage: Record<string, string> = {
  workspace_changed:
    "Workspace đã thay đổi trong lúc AI xử lý. Hãy làm mới diff rồi thử lại.",
  workspace_invalid_edit:
    "Model trả về file không hợp lệ hoặc nằm ngoài phạm vi được phép sửa.",
  workspace_no_changes:
    "Model không tạo ra thay đổi mới. Hãy thử lại với model khác hoặc mô tả công việc rõ hơn.",
  workspace_source_unavailable:
    "File bạn chọn không còn đọc được hoặc vượt giới hạn ngữ cảnh. Hãy chọn ít file hơn.",
  workspace_context_too_large:
    "Ngữ cảnh quá lớn. Hãy chọn ít file nguồn hơn trước khi chạy Dev AI.",
  workspace_unavailable:
    "Không ghi được file vào workspace. Kiểm tra thư mục trên máy.",
  invalid_output: "Model không trả về đúng định dạng file yêu cầu.",
  provider_timeout: "Model phản hồi quá lâu. Hãy thử lại với lượt mới.",
  provider_quota_exhausted: "API key đã hết quota hoặc số dư.",
};

export function RunWorkspacePanel({
  runId,
  projectId,
}: {
  runId: string;
  projectId: string;
}): React.JSX.Element | null {
  const { data: project } = useSuspenseQuery(projectOptions(projectId));
  const { connections } = useAIAccess();
  const connected = Boolean(project.repository_path);
  const workspace = useQuery(workspaceOptions(runId));
  const prepare = useCommand(() => commands.prepareWorkspace(runId));
  const data = workspace.data?.workspace;
  const repository = useQuery({
    ...repositoryOptions(projectId),
    enabled: connected && Boolean(data),
  });
  const edits = useQuery({
    ...workspaceEditsOptions(runId),
    enabled: Boolean(data),
    refetchInterval: 5000,
  });
  const [connectionId, setConnectionId] = useState("");
  const [selectedPaths, setSelectedPaths] = useState<string[]>([]);
  const [fileSearch, setFileSearch] = useState("");
  const [editKey, setEditKey] = useState(() => crypto.randomUUID());
  const selectedConnection = connectionId || connections[0]?.id || "";
  const sourcePaths = [
    ...new Set([
      ...(repository.data?.files ?? []),
      ...(data?.changed_files ?? []),
      ...(data?.untracked_files ?? []),
    ]),
  ];
  const selectableFiles =
    sourcePaths
      .filter(
        (path) =>
          /\.(html|css|scss|js|jsx|ts|tsx|py|json|md|vue|svelte)$/i.test(
            path,
          ) &&
          !path.toLowerCase().endsWith("package-lock.json") &&
          path.toLowerCase().includes(fileSearch.toLowerCase()),
      )
      .slice(0, 40) ?? [];
  const edit = useCommand(
    () =>
      commands.runWorkspaceDev(
        runId,
        selectedConnection,
        editKey,
        selectedPaths,
      ),
    () => setEditKey(crypto.randomUUID()),
  );
  if (!connected && !data) return null;
  return (
    <section
      className="panel content-panel run-workspace"
      aria-labelledby="run-workspace-title"
    >
      <div className="run-workspace-heading">
        <div>
          <h2 id="run-workspace-title">
            <FolderGit2 size={19} aria-hidden="true" /> Workspace Git của run
          </h2>
          <p>
            Một working tree riêng từ commit gốc. Repository của bạn không bị
            sửa khi chuẩn bị workspace.
          </p>
        </div>
        {data && (
          <Button variant="outline" onClick={() => void workspace.refetch()}>
            <RotateCw size={14} aria-hidden="true" /> Làm mới diff
          </Button>
        )}
      </div>
      <ErrorNotice
        error={workspace.error || prepare.error || edits.error || edit.error}
      />
      {workspace.isPending && <p>Đang kiểm tra workspace…</p>}
      {workspace.data && !data && (
        <div className="run-workspace-start">
          <p>
            Chưa có workspace cho run này. Nguồn phải được commit sạch trước khi
            tạo.
          </p>
          <Button disabled={prepare.isPending} onClick={() => prepare.mutate()}>
            {prepare.isPending ? "Đang tạo workspace…" : "Tạo workspace riêng"}
          </Button>
        </div>
      )}
      {data && (
        <>
          <div className="run-workspace-facts">
            <span>
              <GitBranch size={14} aria-hidden="true" />{" "}
              {data.base_branch || "detached HEAD"}
            </span>
            <span>
              Commit gốc <code>{data.base_commit.slice(0, 12)}</code>
            </span>
            <span>
              {data.changed_files.length + data.untracked_files.length} file
              thay đổi
            </span>
          </div>
          <div className="run-workspace-path">
            <strong>Thư mục workspace</strong>
            <code>{data.worktree_path}</code>
          </div>
          <div className="run-workspace-diff-heading">
            <GitCompareArrows size={16} aria-hidden="true" />
            <strong>Thay đổi so với commit gốc</strong>
          </div>
          {!data.files.length && !data.truncated ? (
            <p className="run-workspace-empty">
              Chưa có thay đổi trong workspace.
            </p>
          ) : (
            <WorkspaceDiffBrowser files={data.files} />
          )}
          {data.truncated && (
            <p role="note">
              Diff được giới hạn kích thước hoặc có file không hỗ trợ hiển thị.
              Kiểm tra trực tiếp trong workspace trước khi duyệt.
            </p>
          )}
          <div className="run-workspace-agent">
            <div>
              <h3>Dev AI sửa trong workspace</h3>
              <p>
                AI đọc tối đa 12 file nguồn UTF-8 phù hợp với công việc và chỉ
                ghi file hợp lệ vào worktree này. Nội dung file được gửi tới
                model bạn chọn; mỗi lần chạy có thể dùng quota API.
              </p>
            </div>
            <div className="run-workspace-agent-controls">
              <label htmlFor="run-workspace-model">Model Dev</label>
              <select
                id="run-workspace-model"
                value={selectedConnection}
                disabled={edit.isPending}
                onChange={(event) => {
                  setConnectionId(event.target.value);
                  setEditKey(crypto.randomUUID());
                }}
              >
                {!connections.length && (
                  <option value="">Chưa có kết nối AI</option>
                )}
                {connections.map((connection) => (
                  <option key={connection.id} value={connection.id}>
                    {connection.name} · {connection.provider} /{" "}
                    {connection.model}
                  </option>
                ))}
              </select>
              {sourcePaths.length > 0 && (
                <details className="run-workspace-source-picker">
                  <summary>
                    Chọn file nguồn cho AI ({selectedPaths.length}/12)
                  </summary>
                  <p>
                    Để trống nếu muốn hệ thống tự chọn. File đã chọn sẽ được gửi
                    tới model.
                  </p>
                  <input
                    type="search"
                    value={fileSearch}
                    onChange={(event) => setFileSearch(event.target.value)}
                    placeholder="Tìm file nguồn..."
                    aria-label="Tìm file nguồn cho Dev AI"
                  />
                  <div className="run-workspace-source-list">
                    {selectableFiles.map((path) => (
                      <label key={path}>
                        <input
                          type="checkbox"
                          checked={selectedPaths.includes(path)}
                          disabled={
                            edit.isPending ||
                            (selectedPaths.length >= 12 &&
                              !selectedPaths.includes(path))
                          }
                          onChange={(event) => {
                            setSelectedPaths((current) =>
                              event.target.checked
                                ? [...current, path]
                                : current.filter((value) => value !== path),
                            );
                            setEditKey(crypto.randomUUID());
                          }}
                        />
                        <code>{path}</code>
                      </label>
                    ))}
                    {!selectableFiles.length && (
                      <p>Không tìm thấy file phù hợp.</p>
                    )}
                  </div>
                </details>
              )}
              <Button
                disabled={
                  !selectedConnection ||
                  edit.isPending ||
                  edits.data?.[0]?.status === "pending"
                }
                onClick={() => edit.mutate()}
              >
                {edit.isPending ? "Dev AI đang sửa…" : "Cho Dev AI sửa code"}
              </Button>
            </div>
            {edits.data?.[0] && (
              <div className="run-workspace-agent-result" role="status">
                <strong>
                  {edits.data[0].status === "succeeded"
                    ? "Đã ghi vào workspace"
                    : edits.data[0].status === "pending"
                      ? "Dev AI đang xử lý"
                      : "Dev AI chưa ghi được file"}
                </strong>
                {edits.data[0].summary && <p>{edits.data[0].summary}</p>}
                {edits.data[0].files.length > 0 && (
                  <p>File: {edits.data[0].files.join(", ")}</p>
                )}
                {edits.data[0].error_code && (
                  <p>
                    {editErrorMessage[edits.data[0].error_code] ||
                      `Mã lỗi: ${edits.data[0].error_code}`}
                  </p>
                )}
                <small>
                  Đã đọc {edits.data[0].source_files.length} file nguồn. Lịch sử
                  này được lưu cùng run.
                </small>
              </div>
            )}
            {Boolean(edits.data?.length) && (
              <details className="run-workspace-agent-history">
                <summary>Lịch sử Dev AI ({edits.data?.length})</summary>
                <ol>
                  {edits.data?.map((entry) => (
                    <li key={entry.id}>
                      <strong>
                        {entry.status === "succeeded"
                          ? "Đã ghi file"
                          : entry.status === "pending"
                            ? "Đang xử lý"
                            : "Thất bại"}
                      </strong>
                      <time dateTime={entry.created_at}>
                        {new Date(entry.created_at).toLocaleString("vi-VN")}
                      </time>
                      {entry.summary && <span>{entry.summary}</span>}
                      {entry.files.length > 0 && (
                        <code>{entry.files.join(", ")}</code>
                      )}
                    </li>
                  ))}
                </ol>
              </details>
            )}
          </div>
          <p className="run-workspace-note">
            Dev AI chỉ ghi file trong worktree. Không có lệnh build/test nào
            được chạy ở bước này; PM cần xem diff trước khi dùng thay đổi.
          </p>
        </>
      )}
    </section>
  );
}
