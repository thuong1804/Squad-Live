import { useEffect, useState } from "react";
import { Link } from "@tanstack/react-router";
import { useQueryClient, useSuspenseQuery } from "@tanstack/react-query";
import * as AlertDialog from "@radix-ui/react-alert-dialog";
import {
  commands,
  agentRunsOptions,
  runOptions,
  itemOptions,
  eventsOptions,
  approvalsOptions,
  artifactsOptions,
  artifactOptions,
} from "@/lib/business-api";
import { shouldPoll } from "@/lib/status";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
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
import { WorkflowProgress } from "./progress";
import { WebsiteResults } from "./website";
import { AIChoice } from "@/features/ai/settings";
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
function AgentExecutions({
  id,
  active,
}: {
  id: string;
  active: boolean;
}): React.JSX.Element {
  const [offset, setOffset] = useState(0);
  const { data, error } = useSuspenseQuery(
    agentRunsOptions(id, offset, active),
  );
  return (
    <section className="panel content-panel">
      <h2>Lần thực thi AI</h2>
      <ErrorNotice error={error} />
      {!data.items.length && <p>Chưa có lần gọi BA.</p>}
      {data.items.map((agent) => (
        <article key={agent.id}>
          <h3>
            {agent.role} · {agent.provider} / {agent.model}
          </h3>
          <p>
            {agent.status} · Bản {agent.revision} · Lần {agent.attempt}
          </p>
          <p>
            {agent.connection_id
              ? `Kết nối riêng: ${agent.connection_id.slice(0, 8)}`
              : "Lần thực thi cũ chưa gắn kết nối BYOK"}
          </p>
          <p>
            Token vào / ra: {agent.input_tokens ?? "—"} /{" "}
            {agent.output_tokens ?? "—"} · Thời gian:{" "}
            {agent.duration_ms === null
              ? "—"
              : `${(agent.duration_ms / 1000).toFixed(1)} s`}
          </p>
          {agent.error_code && <p role="alert">Mã lỗi: {agent.error_code}</p>}
        </article>
      ))}
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
  const [decisionNotice, setDecisionNotice] = useState("");
  const approve = useCommand((body: ApprovalDecision) =>
    commands.approve(id, body).then((result) => {
      setDecisionNotice(
        body.decision === "approve"
          ? "Đã ghi nhận phê duyệt. Tiến độ bên dưới hiển thị trạng thái mới nhất."
          : "Đã gửi yêu cầu chỉnh sửa. Workflow quay về bước xử lý; bạn sẽ duyệt lại tài liệu mới.",
      );
      return result;
    }),
  );
  const [retryConnection, setRetryConnection] = useState("");
  const retry = useCommand(() =>
    commands.retry(id, retryConnection || undefined),
  );
  const active = shouldPoll(run.status);
  const gated = [
    "requirements_approval",
    "plan_approval",
    "pm_review",
  ].includes(run.status);
  useEffect(() => {
    for (const key of [
      "events",
      "artifacts",
      "approvals",
      "agent-runs",
      "websites",
    ])
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
            for (const key of [
              "events",
              "artifacts",
              "approvals",
              "agent-runs",
              "websites",
            ])
              void client.invalidateQueries({ queryKey: [key, id] });
          }}
        >
          {isFetching ? "Đang tải…" : "Làm mới"}
        </Button>
      </div>
      <div className="simulation-notice" role="note">
        {run.snapshot.mode === "static_site"
          ? run.snapshot.quality_prompt_version
            ? "BA, Dev, Tester và Reviewer dùng AI. Tester/Reviewer phân tích mã nguồn, chưa chạy kiểm thử trình duyệt. PM quyết định cuối cùng."
            : "BA và Dev dùng AI thật để tạo website HTML/CSS/JS. Tester mô phỏng; chưa tạo PR hoặc deploy."
          : run.snapshot.mode === "ba_live"
            ? "BA dùng AI thật để tạo yêu cầu. Dev và Tester vẫn mô phỏng; chưa sửa code, chạy test hoặc tạo PR."
            : "Workflow mô phỏng · Không thực thi AI, sửa code, chạy test hoặc tạo PR."}
      </div>
      {decisionNotice && (
        <p className="decision-notice" role="status">
          {decisionNotice}
        </p>
      )}
      <WorkflowProgress run={run} />
      <section className="panel content-panel">
        <details>
          <summary>
            Thông tin phiên chạy · Bản {run.revision} · Lần {run.attempt}
          </summary>
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
        </details>
        <ErrorNotice
          error={error || cancel.error || retry.error || approve.error}
        />
        {run.failure_reason && <p role="alert">{run.failure_reason}</p>}
        {run.status === "failed" && run.snapshot.mode !== "mock" && (
          <p>
            Số lần thử đã dùng: {run.attempt}/
            {Number(run.snapshot.max_attempts ?? 3)}. Mỗi lần thử lại có thể
            tiêu tốn quota AI. Nếu nhà cung cấp đang quá tải, hãy chờ hoặc chọn
            kết nối với model khác trước khi thử lại.
          </p>
        )}
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
              disabled={
                retry.isPending ||
                (!run.retryable &&
                  !(
                    retryConnection &&
                    run.attempt < Number(run.snapshot.max_attempts ?? 3)
                  ))
              }
              onClick={() => retry.mutate(undefined)}
            >
              Thử lại bước lỗi
            </Button>
          )}
        </div>
      </section>
      {run.status === "failed" &&
        run.snapshot.mode !== "mock" &&
        [
          "ba_in_progress",
          "plan_in_progress",
          "implementation_in_progress",
          "testing_in_progress",
          "reviewing_in_progress",
        ].includes(run.failed_step || "") && (
          <section className="panel content-panel">
            <h2>Kết nối để tiếp tục bước AI</h2>
            <DataBoundary>
              <AIChoice
                retry
                value={retryConnection}
                disabled={retry.isPending}
                onChange={setRetryConnection}
              />
            </DataBoundary>
            <p>
              Chọn kết nối mới để thử lại với yêu cầu và các bản tài liệu đã
              lưu. Lịch sử lần gọi trước không thay đổi.
            </p>
          </section>
        )}
      {run.snapshot.mode === "static_site" && (
        <DataBoundary>
          <WebsiteResults run={run} />
        </DataBoundary>
      )}
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
      <details className="workflow-diagnostics">
        <summary>Chi tiết thực thi và lịch sử workflow</summary>
        {run.snapshot.mode !== "mock" && (
          <DataBoundary>
            <AgentExecutions id={id} active={active} />
          </DataBoundary>
        )}
        <div className="run-columns">
          <DataBoundary>
            <Timeline id={id} active={active} />
          </DataBoundary>
          <section className="panel content-panel">
            <Tabs
              value={tab}
              onValueChange={(value) =>
                setTab(value as "artifacts" | "approvals")
              }
            >
              <TabsList aria-label="Bằng chứng và lịch sử">
                <TabsTrigger value="artifacts">Artifacts</TabsTrigger>
                <TabsTrigger value="approvals">Lịch sử phê duyệt</TabsTrigger>
              </TabsList>
              <TabsContent value="artifacts">
                <DataBoundary>
                  <Artifacts id={id} />
                </DataBoundary>
              </TabsContent>
              <TabsContent value="approvals">
                <DataBoundary>
                  <Approvals id={id} />
                </DataBoundary>
              </TabsContent>
            </Tabs>
          </section>
        </div>
      </details>
    </>
  );
}
