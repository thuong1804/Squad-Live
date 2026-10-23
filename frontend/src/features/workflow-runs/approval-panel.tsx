import { useState } from "react";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { ErrorNotice } from "@/components/shared/business-ui";
import type { Artifact, ApprovalDecision, Run } from "@/types/contracts";
import { specificationSchema } from "@/types/contracts";
import { guidanceFor } from "./progress";
import { QualityReport } from "./quality-report";

export function ArtifactView({
  artifact,
}: {
  artifact: Artifact;
}): React.JSX.Element {
  const specification = specificationSchema.safeParse(
    artifact.content.specification,
  );
  const plan =
    artifact.kind === "plan"
      ? z
          .object({
            title: z.string(),
            summary: z.string(),
            steps: z.array(z.string()),
            acceptance_checks: z.array(z.string()),
            limitations: z.array(z.string()),
          })
          .safeParse(artifact.content.specification)
      : null;
  return (
    <article className="artifact document-view">
      <h3>
        {artifact.kind} · Bản {artifact.revision} · Lần thực thi{" "}
        {artifact.attempt}
      </h3>
      <small>Artifact: {artifact.id}</small>
      <p>
        {artifact.content.simulated === false
          ? artifact.kind === "requirements"
            ? "BA tạo bằng AI · Cần PM kiểm tra"
            : "Kết quả thật · Cần PM kiểm tra"
          : "Nội dung mô phỏng"}
      </p>
      {specification.success && (
        <>
          <h4 className="document-title">{specification.data.title}</h4>
          <p className="pre-wrap document-summary">
            {specification.data.summary}
          </p>
          <h4>User stories</h4>
          {specification.data.user_stories.map((story) => (
            <div className="story-card" key={story.id}>
              <span className="document-tag">{story.id}</span>
              <strong>{story.role}</strong>
              <p>{story.goal}</p>
              <p className="story-benefit">Mục đích: {story.benefit}</p>
            </div>
          ))}
          <h4>Tiêu chí nghiệm thu (Gherkin)</h4>
          {specification.data.acceptance_criteria.map((ac) => (
            <div className="acceptance-card" key={ac.id}>
              <div className="acceptance-heading">
                <strong>{ac.id}</strong>
                <span className="document-tag">{ac.story_id}</span>
              </div>
              <dl className="gherkin-rows">
                <div>
                  <dt>Given</dt>
                  <dd>{ac.given}</dd>
                </div>
                <div>
                  <dt>When</dt>
                  <dd>{ac.when}</dd>
                </div>
                <div>
                  <dt>Then</dt>
                  <dd>{ac.then}</dd>
                </div>
              </dl>
            </div>
          ))}
          {(
            [
              ["Tình huống biên", specification.data.edge_cases],
              [
                "Yêu cầu phi chức năng",
                specification.data.non_functional_requirements,
              ],
              ["Câu hỏi cần làm rõ", specification.data.open_questions],
              ["Giả định", specification.data.assumptions],
            ] as const
          ).map(([title, entries]) => (
            <section className="document-section" key={title}>
              <h4>{title}</h4>
              {entries.length ? (
                <ul>
                  {entries.map((entry, index) => (
                    <li key={index}>{entry}</li>
                  ))}
                </ul>
              ) : (
                <p>Không có.</p>
              )}
            </section>
          ))}
        </>
      )}
      {plan?.success && (
        <>
          <h4 className="document-title">{plan.data.title}</h4>
          <p className="document-summary">{plan.data.summary}</p>
          <h4>Kế hoạch thực hiện</h4>
          <ol>
            {plan.data.steps.map((step, index) => (
              <li key={index}>{step}</li>
            ))}
          </ol>
          <h4>Cần kiểm tra khi xem Preview</h4>
          <ul>
            {plan.data.acceptance_checks.map((step, index) => (
              <li key={index}>{step}</li>
            ))}
          </ul>
          {plan.data.limitations.length > 0 && (
            <>
              <h4>Giới hạn</h4>
              <ul>
                {plan.data.limitations.map((step, index) => (
                  <li key={index}>{step}</li>
                ))}
              </ul>
            </>
          )}
        </>
      )}
      {artifact.content.source === "static_site" && (
        <p>
          Mã nguồn website đã được tạo. Mở phần Kết quả website để xem Preview
          và tải ZIP. Đọc bằng chứng trình duyệt cùng báo cáo Tester/Reviewer
          bên dưới trước khi duyệt.
        </p>
      )}
      <details
        open={
          !specification.success &&
          !plan?.success &&
          artifact.content.source !== "static_site" &&
          !artifact.content.reviewer_report &&
          artifact.kind !== "tester_report"
        }
      >
        <summary>Dữ liệu artifact</summary>
        <pre>{JSON.stringify(artifact.content, null, 2)}</pre>
      </details>
      <QualityReport
        title="Tester AI"
        browserChecked={!!artifact.content.browser_report}
        value={
          artifact.kind === "tester_report"
            ? artifact.content.specification
            : artifact.content.tester_report
        }
      />
      <QualityReport
        title="Reviewer AI"
        browserChecked={!!artifact.content.browser_report}
        value={artifact.content.reviewer_report}
      />
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
    <section
      id="current-review"
      className="panel content-panel approval-panel"
      aria-busy={pending}
    >
      <p className="review-kicker">{guidanceFor(run)?.title}</p>
      <h2>Cần quyết định của PM</h2>
      <p className="review-next">{guidanceFor(run)?.next}</p>
      <p>
        {run.snapshot.mode === "static_site"
          ? "Đọc tài liệu, báo cáo hiện có và kiểm tra Preview trước khi duyệt. Nhận xét AI không thay thế kiểm thử trình duyệt."
          : "Đọc bằng chứng trước khi phê duyệt. Hoàn tất mô phỏng không có nghĩa là code đã được viết hoặc kiểm thử."}
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
