import { Link } from "@tanstack/react-router";
import { useSuspenseQuery } from "@tanstack/react-query";
import { dashboardOptions } from "@/lib/business-api";
import {
  Status,
  ErrorNotice,
  timeLabel,
} from "@/components/shared/business-ui";
import { Button } from "@/components/ui/button";
import { shouldPoll } from "@/lib/status";
import HealthPanel from "./health-panel";
export default function Dashboard(): React.JSX.Element {
  const { data, error } = useSuspenseQuery(dashboardOptions);
  const waiting = ["requirements_approval", "plan_approval", "pm_review"];
  const pendingCount = waiting.reduce(
    (sum, status) => sum + (data.counts[status] || 0),
    0,
  );
  const activeCount = Object.entries(data.counts).reduce(
    (sum, [status, count]) =>
      sum + (shouldPoll(status) && !waiting.includes(status) ? count : 0),
    0,
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">WORKSPACE OVERVIEW</p>
          <h1>Điều phối cùng nhau.</h1>
          <p>Dữ liệu từ backend · Workflow hiện chạy ở chế độ mô phỏng.</p>
        </div>
        <Button asChild>
          <Link to="/projects">Quản lý dự án</Link>
        </Button>
      </div>
      <ErrorNotice error={error} />
      <div className="metrics">
        {[
          ["Đang thực hiện", activeCount],
          ["Chờ phê duyệt", pendingCount],
          ["Hoàn tất mô phỏng", data.counts.completed || 0],
          ["Thất bại", data.counts.failed || 0],
        ].map(([label, count]) => (
          <section className="metric" key={label}>
            <span>{label}</span>
            <strong>{count}</strong>
          </section>
        ))}
      </div>
      <section className="panel content-panel">
        <h2>Cần PM phê duyệt</h2>
        {!data.waiting_runs.length ? (
          <p>Không có run đang chờ phê duyệt.</p>
        ) : (
          <div className="record-list">
            {data.waiting_runs.map((run) => (
              <Link
                className="record"
                key={run.id}
                to="/workflow-runs/$runId"
                params={{ runId: run.id }}
              >
                <strong>Run {run.id.slice(0, 8)}</strong>
                <Status value={run.status} />
              </Link>
            ))}
          </div>
        )}
        <small>Hiển thị tối đa 10 run; xem thêm trong từng dự án.</small>
      </section>
      <section className="panel content-panel">
        <h2>Workflow gần đây</h2>
        {!data.recent_runs.length ? (
          <p>Chưa có workflow. Hãy tạo dự án và công việc đầu tiên.</p>
        ) : (
          <div className="record-list">
            {data.recent_runs.map((run) => (
              <Link
                className="record"
                key={run.id}
                to="/workflow-runs/$runId"
                params={{ runId: run.id }}
              >
                <div>
                  <strong>Run {run.id.slice(0, 8)}</strong>
                  <p>{timeLabel(run.created_at)}</p>
                </div>
                <Status value={run.status} />
              </Link>
            ))}
          </div>
        )}
      </section>
      <section className="panel content-panel">
        <h2>Hoạt động gần đây</h2>
        {data.recent_events.length ? (
          <ul className="timeline">
            {data.recent_events.map((event) => (
              <li key={event.id}>
                <Link
                  to="/workflow-runs/$runId"
                  params={{ runId: event.run_id }}
                >
                  {event.event_type}
                </Link>
                <small>{timeLabel(event.created_at)}</small>
              </li>
            ))}
          </ul>
        ) : (
          <p>Chưa có hoạt động.</p>
        )}
      </section>
      <HealthPanel />
    </>
  );
}
