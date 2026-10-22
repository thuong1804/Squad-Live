import { useEffect, useState } from "react";
import { Link } from "@tanstack/react-router";
import { useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import * as AlertDialog from "@radix-ui/react-alert-dialog";
import {
  commands,
  runOptions,
  itemOptions,
  eventsOptions,
  approvalsOptions,
  artifactsOptions,
  artifactOptions,
} from "@/lib/business-api";
import { shouldPoll } from "@/lib/status";
import { Button } from "@/components/ui/button";
import { DataBoundary } from "@/components/shared/data-boundary";
import {
  ErrorNotice,
  Pagination,
  Status,
  timeLabel,
  useCommand,
} from "@/components/shared/business-ui";
import { ApprovalPanel, ArtifactView } from "./approval-panel";
import type { Run, ApprovalDecision } from "@/types/contracts";

function Gate(props: {
  run: Run;
  pending: boolean;
  error: unknown;
  onDecision: (data: ApprovalDecision) => void;
}): React.JSX.Element {
  return props.run.gate_artifact_id ? (
    <CurrentGate {...props} />
  ) : (
    <ApprovalPanel {...props} />
  );
}
function CurrentGate(props: {
  run: Run;
  pending: boolean;
  error: unknown;
  onDecision: (data: ApprovalDecision) => void;
}): React.JSX.Element {
  const { data } = useSuspenseQuery(
    artifactOptions(props.run.id, props.run.gate_artifact_id!),
  );
  return <ApprovalPanel key={props.run.gate_id} {...props} artifact={data} />;
}
function Timeline({
  id,
  active,
}: {
  id: string;
  active: boolean;
}): React.JSX.Element {
  const [offset, setOffset] = useState(0);
  const { data, error } = useSuspenseQuery(eventsOptions(id, offset, active));
  return (
    <section className="panel content-panel">
      <h2>Timeline</h2>
      <ErrorNotice error={error} />
      {!data.items.length ? (
        <p>Chưa có sự kiện.</p>
      ) : (
        <ol
          className="timeline run-timeline"
          tabIndex={0}
          aria-label="Sự kiện workflow theo thời gian"
        >
          {data.items.map((event) => (
            <li key={event.id}>
              <strong>
                {event.event_type === "state_changed" &&
                typeof event.payload.status === "string" ? (
                  <Status value={event.payload.status} />
                ) : (
                  event.event_type
                )}
              </strong>
              <small>
                {timeLabel(event.created_at)} · Lần{" "}
                {String(event.payload.attempt ?? "—")} · Bản{" "}
                {String(event.payload.revision ?? "—")}
              </small>
              <details>
                <summary>Chi tiết sự kiện</summary>
                <pre>{JSON.stringify(event.payload, null, 2)}</pre>
              </details>
            </li>
          ))}
        </ol>
      )}
      <Pagination
        offset={offset}
        count={data.items.length}
        onChange={setOffset}
      />
    </section>
  );
}
function Artifacts({ id }: { id: string }): React.JSX.Element {
  const [offset, setOffset] = useState(0);
  const { data, error } = useSuspenseQuery(artifactsOptions(id, offset));
  return (
    <>
      <ErrorNotice error={error} />
      {data.items.length ? (
        data.items.map((artifact) => (
          <ArtifactView key={artifact.id} artifact={artifact} />
        ))
      ) : (
        <p>Chưa có artifact trong trang này.</p>
      )}
      <Pagination
        offset={offset}
        count={data.items.length}
        onChange={setOffset}
      />
    </>
  );
}
function Approvals({ id }: { id: string }): React.JSX.Element {
  const [offset, setOffset] = useState(0);
  const { data, error } = useSuspenseQuery(approvalsOptions(id, offset));
  return (
    <>
      <ErrorNotice error={error} />
      {data.items.length ? (
        data.items.map((approval) => (
          <article className="artifact" key={approval.id}>
            <h3>
              {approval.decision === "approve"
                ? "Đã phê duyệt"
                : "Đã yêu cầu chỉnh sửa"}{" "}
              · Bản {approval.revision}
            </h3>
            <p>
              {approval.reviewer} · {timeLabel(approval.created_at)}
            </p>
            <Status value={approval.step} />
            <p className="pre-wrap">
              {approval.comment || "Không có nhận xét"}
            </p>
            <small>
              Artifact: {approval.artifact_id || "Run phiên bản cũ"}
            </small>
            {approval.return_to && (
              <p>
                Chuyển về: <Status value={approval.return_to} />
              </p>
            )}
          </article>
        ))
      ) : (
        <p>Chưa có quyết định phê duyệt.</p>
      )}
      <Pagination
        offset={offset}
        count={data.items.length}
        onChange={setOffset}
      />
    </>
  );
}
export function RunPage({ id }: { id: string }): React.JSX.Element {
  const {
    data: run,
    error,
    isFetching,
    refetch,
  } = useSuspenseQuery(runOptions(id));
  const { data: item } = useSuspenseQuery(itemOptions(run.work_item_id));
  const client = useQueryClient();
  const [tab, setTab] = useState<"artifacts" | "approvals">("artifacts");
  const cancel = useCommand(() => commands.cancel(id));
  const approve = useCommand((body: ApprovalDecision) =>
    commands.approve(id, body),
  );
  const retry = useCommand(() => commands.retry(id));
  const active = shouldPoll(run.status);
  const gated = [
    "requirements_approval",
    "plan_approval",
    "pm_review",
  ].includes(run.status);
  useEffect(() => {
    for (const key of ["events", "artifacts", "approvals"])
      void client.invalidateQueries({ queryKey: [key, id] });
  }, [client, id, run.status, run.gate_id, run.attempt]);
  return (
    <>
      <div className="page-heading">
        <div>
          <Link to="/work-items/$workItemId" params={{ workItemId: item.id }}>
            ← Công việc
          </Link>
          <h1>{item.title}</h1>
          <Status value={run.status} />
        </div>
        <Button
          variant="outline"
          disabled={isFetching}
          onClick={() => {
            void refetch();
            for (const key of ["events", "artifacts", "approvals"])
              void client.invalidateQueries({ queryKey: [key, id] });
          }}
        >
          {isFetching ? "Đang tải…" : "Làm mới"}
        </Button>
      </div>
      <div className="simulation-notice" role="note">
        Workflow mô phỏng · Không thực thi AI, sửa code, chạy test hoặc tạo PR.
      </div>
      <section className="panel content-panel">
        <dl className="run-facts">
          <div>
            <dt>Run ID</dt>
            <dd>{run.id}</dd>
          </div>
          <div>
            <dt>Phiên bản chỉnh sửa</dt>
            <dd>{run.revision}</dd>
          </div>
          <div>
            <dt>Lần thực thi</dt>
            <dd>{run.attempt}</dd>
          </div>
          <div>
            <dt>Bắt đầu / kết thúc</dt>
            <dd>
              {timeLabel(run.started_at)} / {timeLabel(run.ended_at)}
            </dd>
          </div>
        </dl>
        <ErrorNotice
          error={error || cancel.error || retry.error || approve.error}
        />
        {run.failure_reason && <p role="alert">{run.failure_reason}</p>}
        {run.cancellation_reason && <p>{run.cancellation_reason}</p>}
        <div className="actions">
          {active && (
            <AlertDialog.Root>
              <AlertDialog.Trigger asChild>
                <Button variant="outline" disabled={cancel.isPending}>
                  Hủy workflow
                </Button>
              </AlertDialog.Trigger>
              <AlertDialog.Portal>
                <AlertDialog.Overlay className="dialog-overlay" />
                <AlertDialog.Content className="dialog-content">
                  <AlertDialog.Title>Hủy workflow này?</AlertDialog.Title>
                  <AlertDialog.Description>
                    Run sẽ dừng và không thể tiếp tục. Lịch sử và artifact vẫn
                    được giữ lại.
                  </AlertDialog.Description>
                  <div className="actions">
                    <AlertDialog.Cancel asChild>
                      <Button variant="outline">Tiếp tục công việc</Button>
                    </AlertDialog.Cancel>
                    <AlertDialog.Action asChild>
                      <Button onClick={() => cancel.mutate(undefined)}>
                        Xác nhận hủy
                      </Button>
                    </AlertDialog.Action>
                  </div>
                </AlertDialog.Content>
              </AlertDialog.Portal>
            </AlertDialog.Root>
          )}
          {run.status === "failed" && (
            <Button
              disabled={!run.retryable || retry.isPending}
              onClick={() => retry.mutate(undefined)}
            >
              Thử lại bước lỗi
            </Button>
          )}
        </div>
      </section>
      {gated && (
        <DataBoundary key={run.gate_id || run.status}>
          <Gate
            run={run}
            pending={approve.isPending}
            error={null}
            onDecision={approve.mutate}
          />
        </DataBoundary>
      )}
      <div className="run-columns">
        <DataBoundary>
          <Timeline id={id} active={active} />
        </DataBoundary>
        <section className="panel content-panel">
          <div
            className="actions"
            role="group"
            aria-label="Bằng chứng và lịch sử"
          >
            <Button
              variant={tab === "artifacts" ? "default" : "outline"}
              aria-pressed={tab === "artifacts"}
              onClick={() => setTab("artifacts")}
            >
              Artifacts
            </Button>
            <Button
              variant={tab === "approvals" ? "default" : "outline"}
              aria-pressed={tab === "approvals"}
              onClick={() => setTab("approvals")}
            >
              Lịch sử phê duyệt
            </Button>
          </div>
          <DataBoundary>
            {tab === "artifacts" ? (
              <Artifacts id={id} />
            ) : (
              <Approvals id={id} />
            )}
          </DataBoundary>
        </section>
      </div>
    </>
  );
}
