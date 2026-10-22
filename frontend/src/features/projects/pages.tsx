import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { useSuspenseQuery } from "@tanstack/react-query";
import {
  commands,
  projectsOptions,
  projectOptions,
  itemsOptions,
} from "@/lib/business-api";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/shared/page-layout";
import {
  ErrorNotice,
  Pagination,
  Status,
  timeLabel,
  useCommand,
} from "@/components/shared/business-ui";

export function ProjectsPage(): React.JSX.Element {
  const [offset, setOffset] = useState(0);
  const { data, error } = useSuspenseQuery(projectsOptions(offset));
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Dự án</h1>
          <p>Quản lý yêu cầu và các lượt thực thi của đội AI.</p>
        </div>
        <Button asChild>
          <Link to="/projects/new">Tạo dự án</Link>
        </Button>
      </div>
      <ErrorNotice error={error} />
      <section className="panel content-panel">
        {!data.items.length ? (
          <EmptyState
            title="Chưa có dự án trong trang này"
            description="Tạo dự án để tập hợp yêu cầu, theo dõi đội AI và duyệt kết quả."
          />
        ) : (
          <div className="record-list">
            {data.items.map((project) => (
              <Link
                key={project.id}
                to="/projects/$projectId"
                params={{ projectId: project.id }}
                className="record"
              >
                <div>
                  <strong>{project.name}</strong>
                  <p>{project.description || "Chưa có mô tả"}</p>
                  <small>Cập nhật {timeLabel(project.updated_at)}</small>
                </div>
                <span
                  className={`status-badge ${project.status === "active" ? "status-success" : "status-neutral"}`}
                >
                  {project.status === "active"
                    ? "Đang hoạt động"
                    : "Đã lưu trữ"}
                </span>
              </Link>
            ))}
          </div>
        )}
        <Pagination
          offset={offset}
          count={data.items.length}
          onChange={setOffset}
        />
      </section>
    </>
  );
}
export function NewProjectPage(): React.JSX.Element {
  const navigate = useNavigate();
  const mutation = useCommand(commands.createProject, (project) => {
    void navigate({
      to: "/projects/$projectId",
      params: { projectId: project.id },
    });
  });
  function submit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    mutation.mutate({
      name: String(fields.get("name")).trim(),
      description: String(fields.get("description")).trim(),
    });
  }
  return (
    <section className="panel content-panel">
      <h1>Tạo dự án</h1>
      <p>
        Tập hợp công việc trong một dự án, sau đó chọn model và chế độ thực thi
        cho từng workflow.
      </p>
      <form onSubmit={submit}>
        <label htmlFor="project-name">Tên dự án</label>
        <input
          id="project-name"
          name="name"
          required
          maxLength={200}
          pattern=".*\S.*"
        />
        <label htmlFor="project-description">Mô tả</label>
        <textarea
          id="project-description"
          name="description"
          maxLength={20000}
        />
        <ErrorNotice error={mutation.error} />
        <div className="actions">
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? "Đang tạo…" : "Tạo dự án"}
          </Button>
          <Link to="/projects">Quay lại</Link>
        </div>
      </form>
    </section>
  );
}
export function ProjectPage({ id }: { id: string }): React.JSX.Element {
  const [offset, setOffset] = useState(0);
  const { data: project, error } = useSuspenseQuery(projectOptions(id));
  const { data: items } = useSuspenseQuery(itemsOptions(id, offset));
  const archive = useCommand((status: "active" | "archived") =>
    commands.archiveProject(id, status),
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <Link to="/projects">← Dự án</Link>
          <h1>{project.name}</h1>
          <p>{project.description}</p>
        </div>
        {project.status === "active" ? (
          <Button asChild>
            <Link
              to="/projects/$projectId/work-items/new"
              params={{ projectId: id }}
            >
              Tạo công việc
            </Link>
          </Button>
        ) : (
          <span>Đã lưu trữ</span>
        )}
      </div>
      <ErrorNotice error={error || archive.error} />
      <section className="panel content-panel">
        <h2>Kết nối repository</h2>
        <p>
          Chưa kết nối. BA có thể phân tích yêu cầu bằng AI; phiên bản này chưa
          sửa code hoặc tạo PR.
        </p>
        <Button
          variant="outline"
          disabled={archive.isPending}
          onClick={() => {
            if (
              project.status === "archived" ||
              window.confirm(
                "Lưu trữ dự án sẽ chặn công việc và run mới. Tiếp tục?",
              )
            )
              archive.mutate(
                project.status === "active" ? "archived" : "active",
              );
          }}
        >
          {project.status === "active" ? "Lưu trữ dự án" : "Khôi phục dự án"}
        </Button>
      </section>
      <section className="panel content-panel">
        <h2>Công việc</h2>
        {!items.items.length ? (
          <p>Chưa có công việc trong trang này.</p>
        ) : (
          <div className="record-list">
            {items.items.map((item) => (
              <Link
                className="record"
                key={item.id}
                to="/work-items/$workItemId"
                params={{ workItemId: item.id }}
              >
                <div>
                  <strong>{item.title}</strong>
                  <p>Ưu tiên: {item.priority}</p>
                </div>
                <Status value={item.status} />
              </Link>
            ))}
          </div>
        )}
        <Pagination
          offset={offset}
          count={items.items.length}
          onChange={setOffset}
        />
      </section>
    </>
  );
}
