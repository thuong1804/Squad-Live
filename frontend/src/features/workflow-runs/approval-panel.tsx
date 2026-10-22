import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ErrorNotice } from "@/components/shared/business-ui";
import type { Artifact, ApprovalDecision, Run } from "@/types/contracts";

export function ArtifactView({
  artifact,
}: {
  artifact: Artifact;
}): React.JSX.Element {
  return (
    <article className="artifact">
      <h3>
        {artifact.kind} · Bản {artifact.revision} · Lần thực thi{" "}
        {artifact.attempt}
      </h3>
      <small>Artifact: {artifact.id}</small>
      <pre>{JSON.stringify(artifact.content, null, 2)}</pre>
    </article>
  );
}
export function ApprovalPanel({
  run,
  artifact,
  pending,
  error,
  onDecision,
}: {
  run: Run;
  artifact?: Artifact;
  pending: boolean;
  error: unknown;
  onDecision: (data: ApprovalDecision) => void;
}): React.JSX.Element {
  const [comment, setComment] = useState("");
  const [returnTo, setReturnTo] = useState<
    "ba_in_progress" | "plan_in_progress"
  >("plan_in_progress");
  const [validation, setValidation] = useState("");
  const legacy = run.snapshot.version === "deterministic-v1";
  const ready =
    !pending &&
    (legacy || (artifact?.id === run.gate_artifact_id && !!run.gate_id));
  function decide(decision: "approve" | "reject"): void {
    if (decision === "reject" && !comment.trim()) {
      setValidation("Hãy mô tả nội dung cần chỉnh sửa.");
      return;
    }
    setValidation("");
    onDecision({
      step: run.status,
      attempt: run.attempt,
      gate_id: run.gate_id,
      artifact_id: run.gate_artifact_id,
      decision,
      comment: comment.trim() || undefined,
      ...(decision === "reject" && run.status === "pm_review" && !legacy
        ? { return_to: returnTo }
        : {}),
    });
  }
  return (
    <section className="panel content-panel approval-panel">
      <h2>Cần quyết định của PM</h2>
      <p>
        Đọc bằng chứng trước khi phê duyệt. Hoàn tất mô phỏng không có nghĩa là
        code đã được viết hoặc kiểm thử.
      </p>
      {legacy ? (
        <p>
          Run phiên bản cũ: từ chối sẽ kết thúc run ở trạng thái thất bại. Xem
          sự kiện mô phỏng trong timeline trước khi quyết định.
        </p>
      ) : artifact ? (
        <ArtifactView artifact={artifact} />
      ) : (
        <p role="status">Đang tải artifact của phiên duyệt hiện tại…</p>
      )}
      <label htmlFor="review-comment">Nhận xét / nội dung cần sửa</label>
      <textarea
        id="review-comment"
        maxLength={4000}
        value={comment}
        onChange={(e) => setComment(e.target.value)}
      />
      {run.status === "pm_review" && !legacy && (
        <>
          <label htmlFor="return-to">Khi yêu cầu chỉnh sửa, chuyển về</label>
          <select
            id="return-to"
            value={returnTo}
            onChange={(e) => setReturnTo(e.target.value as typeof returnTo)}
          >
            <option value="plan_in_progress">Dev lập lại kế hoạch</option>
            <option value="ba_in_progress">BA làm rõ yêu cầu</option>
          </select>
        </>
      )}
      {validation && <p role="alert">{validation}</p>}
      <ErrorNotice error={error} />
      <div className="actions">
        <Button disabled={!ready} onClick={() => decide("approve")}>
          {pending ? "Đang gửi…" : "Phê duyệt"}
        </Button>
        <Button
          variant="outline"
          disabled={!ready}
          onClick={() => decide("reject")}
        >
          {legacy ? "Từ chối" : "Yêu cầu chỉnh sửa"}
        </Button>
      </div>
    </section>
  );
}
