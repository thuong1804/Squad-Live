import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { useSuspenseQuery } from "@tanstack/react-query";
import {
  commands,
  itemOptions,
  projectOptions,
  runsOptions,
} from "@/lib/business-api";
import { Button } from "@/components/ui/button";
import {
  ErrorNotice,
  Pagination,
  Status,
  timeLabel,
  useCommand,
} from "@/components/shared/business-ui";

export function NewItemPage({
  projectId,
}: {
  projectId: string;
}): React.JSX.Element {
  const { data: project } = useSuspenseQuery(projectOptions(projectId));
  const navigate = useNavigate();
  const [validation, setValidation] = useState("");
  const mutation = useCommand(
    (body: {
      title: string;
      description: string;
      acceptance_criteria: string;
      priority: string;
    }) => commands.createItem(projectId, body),
    (item) => {
      void navigate({
        to: "/work-items/$workItemId",
        params: { workItemId: item.id },
      });
    },
  );
  function submit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    const body = {
      title: String(fields.get("title")).trim(),
      description: String(fields.get("description")).trim(),
      acceptance_criteria: String(fields.get("acceptance_criteria")).trim(),
      priority: String(fields.get("priority")),
    };
    if (!body.title || !body.description) {
      setValidation("Vui lòng nhập tiêu đề và mô tả có nội dung.");
      return;
    }
    setValidation("");
    mutation.mutate(body);
  }
  return (
    <section className="panel content-panel">
      <h1>Tạo công việc</h1>
      <p>Dự án: {project.name}</p>
      {project.status === "archived" && (
        <p role="alert">
          Dự án đã lưu trữ. Hãy khôi phục trước khi tạo công việc.
        </p>
      )}
      <form onSubmit={submit}>
        <label htmlFor="item-title">Tiêu đề</label>
        <input id="item-title" name="title" required maxLength={200} />
        <label htmlFor="item-description">Mô tả yêu cầu</label>
        <textarea
          id="item-description"
          name="description"
          required
          maxLength={20000}
        />
        <label htmlFor="item-ac">Tiêu chí nghiệm thu</label>
        <textarea id="item-ac" name="acceptance_criteria" maxLength={20000} />
        <label htmlFor="item-priority">Độ ưu tiên</label>
        <select id="item-priority" name="priority" defaultValue="medium">
          <option value="low">Thấp</option>
          <option value="medium">Trung bình</option>
          <option value="high">Cao</option>
          <option value="critical">Khẩn cấp</option>
        </select>
        {validation && <p role="alert">{validation}</p>}
        <ErrorNotice error={mutation.error} />
        <div className="actions">
          <Button
            type="submit"
            disabled={mutation.isPending || project.status !== "active"}
          >
            {mutation.isPending ? "Đang tạo…" : "Tạo công việc"}
          </Button>
          <Link to="/projects/$projectId" params={{ projectId }}>
            Quay lại dự án
          </Link>
        </div>
      </form>
    </section>
  );
}
export function ItemPage({ id }: { id: string }): React.JSX.Element {
  const [offset, setOffset] = useState(0);
  const [key, setKey] = useState(() => crypto.randomUUID());
  const { data: item, error } = useSuspenseQuery(itemOptions(id));
  const { data: project } = useSuspenseQuery(projectOptions(item.project_id));
  const { data: runs } = useSuspenseQuery(runsOptions(id, offset));
  const navigate = useNavigate();
  const start = useCommand(
    () => commands.start(id, key),
    (run) => {
      setKey(crypto.randomUUID());
      void navigate({ to: "/workflow-runs/$runId", params: { runId: run.id } });
    },
  );
  const canStart =
    project.status === "active" &&
    ["draft", "completed", "failed", "cancelled"].includes(item.status);
  return (
    <>
      <div className="page-heading">
        <div>
          <Link
            to="/projects/$projectId"
            params={{ projectId: item.project_id }}
          >
            ← {project.name}
          </Link>
          <h1>{item.title}</h1>
          <Status value={item.status} />
        </div>
        <Button
          disabled={!canStart || start.isPending}
          onClick={() => start.mutate(undefined)}
        >
          {start.isPending ? "Đang khởi tạo…" : "Bắt đầu workflow mô phỏng"}
        </Button>
      </div>
      <ErrorNotice error={error || start.error} />
      {!canStart && (
        <p>
          Chỉ có thể bắt đầu khi dự án hoạt động và công việc không có run đang
          chạy.
        </p>
      )}
      <section className="panel content-panel">
        <h2>Yêu cầu</h2>
        <p className="pre-wrap">{item.description}</p>
        <h2>Tiêu chí nghiệm thu</h2>
        <p className="pre-wrap">
          {item.acceptance_criteria || "Chưa có tiêu chí nghiệm thu."}
        </p>
        <p>Ưu tiên: {item.priority}</p>
      </section>
      <section className="panel content-panel">
        <h2>Lịch sử workflow</h2>
        {runs.items.length ? (
          <div className="record-list">
            {runs.items.map((run) => (
              <Link
                key={run.id}
                className="record"
                to="/workflow-runs/$runId"
                params={{ runId: run.id }}
              >
                <div>
                  <strong>Run {run.id.slice(0, 8)}</strong>
                  <p>
                    {timeLabel(run.created_at)} · Phiên bản chỉnh sửa{" "}
                    {run.revision}
                  </p>
                </div>
                <Status value={run.status} />
              </Link>
            ))}
          </div>
        ) : (
          <p>Chưa có workflow trong trang này.</p>
        )}
        <Pagination
          offset={offset}
          count={runs.items.length}
          onChange={setOffset}
        />
      </section>
    </>
  );
}
