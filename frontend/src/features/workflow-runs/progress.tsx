import { Check, CircleAlert, LoaderCircle } from "lucide-react";
import type { Run } from "@/types/contracts";

const baseSteps = [
  ["ba_in_progress", "Phân tích yêu cầu", "BA"],
  ["requirements_approval", "Duyệt yêu cầu", "PM · Lần duyệt 1/3"],
  ["plan_in_progress", "Lập kế hoạch", "Dev · Mô phỏng"],
  ["plan_approval", "Duyệt kế hoạch", "PM · Lần duyệt 2/3"],
  ["implementation_in_progress", "Triển khai", "Dev · Mô phỏng"],
  ["checks_in_progress", "Kiểm tra", "Mô phỏng"],
  ["testing_in_progress", "Kiểm thử", "Tester · Mô phỏng"],
  ["pm_review", "Đánh giá cuối", "PM · Lần duyệt 3/3"],
] as const;

export const reviewGuidance: Record<string, { title: string; next: string }> = {
  requirements_approval: {
    title: "Lần duyệt 1/3 · Yêu cầu của BA",
    next: "Phê duyệt để Dev lập kế hoạch mô phỏng. Yêu cầu chỉnh sửa để BA phân tích lại.",
  },
  plan_approval: {
    title: "Lần duyệt 2/3 · Kế hoạch của Dev",
    next: "Phê duyệt để tiếp tục triển khai và kiểm thử mô phỏng. Yêu cầu chỉnh sửa để Dev lập lại kế hoạch.",
  },
  pm_review: {
    title: "Lần duyệt 3/3 · Đánh giá cuối của PM",
    next: "Phê duyệt để kết thúc workflow. Nếu cần sửa, chọn quay về BA hoặc bước lập kế hoạch.",
  },
};

export function guidanceFor(run: Run) {
  const guidance = reviewGuidance[run.status];
  if (!guidance || run.snapshot.mode !== "static_site") return guidance;
  return {
    ...guidance,
    next:
      run.status === "requirements_approval"
        ? "Phê duyệt để Dev dùng AI lập kế hoạch website. Yêu cầu chỉnh sửa để BA phân tích lại."
        : run.status === "plan_approval"
          ? "Phê duyệt để Dev dùng AI sinh HTML/CSS/JS. Kết quả sẽ có Preview và tải ZIP."
          : "Xem Preview và mã nguồn trong Kết quả website trước khi phê duyệt. Chưa chạy kiểm thử trình duyệt; bạn có thể yêu cầu Dev lập lại kế hoạch và tạo bản mới.",
  };
}

export function WorkflowProgress({ run }: { run: Run }): React.JSX.Element {
  const steps: ReadonlyArray<readonly [string, string, string]> = run.snapshot
    .quality_prompt_version
    ? [
        ...baseSteps.slice(0, 6),
        ["testing_in_progress", "Tester AI", "Phân tích mã nguồn"],
        ["reviewing_in_progress", "Reviewer AI", "Đánh giá độc lập"],
        baseSteps[7],
      ]
    : baseSteps;
  const liveSite = run.snapshot.mode === "static_site";
  const completed = run.status === "completed";
  const failed = run.status === "failed";
  const cancelled = run.status === "cancelled";
  const current = steps.findIndex(
    ([status]) => status === (failed ? run.failed_step : run.status),
  );
  const gate = guidanceFor(run);
  const title = completed
    ? "Workflow đã được phê duyệt"
    : cancelled
      ? "Workflow đã hủy"
      : failed
        ? "Workflow cần xử lý lỗi"
        : gate
          ? gate.title
          : current >= 0
            ? `Bước ${current + 1}/${steps.length} · ${steps[current][1]}`
            : "Đang chờ worker bắt đầu";
  return (
    <section
      className="panel workflow-progress"
      aria-labelledby="workflow-progress-title"
    >
      <div className="workflow-progress-heading">
        <div>
          <p className="eyebrow">TIẾN ĐỘ WORKFLOW · BẢN {run.revision}</p>
          <h2 id="workflow-progress-title" aria-live="polite">
            {title}
          </h2>
          <p>
            {completed
              ? liveSite
                ? "Website đã được PM duyệt. Xem Preview hoặc tải mã nguồn trong Kết quả website. Chưa xác minh bằng kiểm thử trình duyệt."
                : "Kết quả hiện có là tài liệu và lịch sử duyệt. Dev/Tester mô phỏng nên chưa có file HTML, code hoặc trang preview."
              : cancelled
                ? "Luồng đã dừng. Tài liệu và quyết định trước đó vẫn được giữ trong lịch sử."
                : failed
                  ? "Xem nguyên nhân bên dưới, kiểm tra kết nối AI rồi thử lại bước lỗi."
                  : gate
                    ? "Workflow đang tạm dừng để bạn đọc tài liệu và đưa ra quyết định."
                    : "Hệ thống đang xử lý. Nếu dịch vụ AI trả lỗi 503, hệ thống tự thử lại tối đa 2 lần trong thời gian cho phép. Trạng thái tự cập nhật."}
          </p>
        </div>
        {gate && (
          <a className="button" href="#current-review">
            Đến bước cần duyệt ↓
          </a>
        )}
      </div>
      <ol className="workflow-steps" aria-label="Các bước workflow">
        {steps.map(([status, label, owner], index) => {
          const isCurrent = index === current && !completed && !cancelled;
          const done =
            completed || (current >= 0 && index < current && !cancelled);
          const state = done
            ? "done"
            : isCurrent
              ? failed
                ? "failed"
                : gate
                  ? "review"
                  : "running"
              : "waiting";
          const stateLabel = done
            ? "Đã qua bước"
            : isCurrent
              ? failed
                ? "Gặp lỗi"
                : gate
                  ? "Cần bạn duyệt"
                  : "Đang xử lý"
              : cancelled
                ? "Đã dừng"
                : "Chưa tới bước";
          return (
            <li
              key={status}
              className={`workflow-step step-${state}`}
              aria-current={isCurrent ? "step" : undefined}
            >
              <span className="step-number" aria-hidden="true">
                {done ? (
                  <Check size={18} />
                ) : isCurrent && failed ? (
                  <CircleAlert size={18} />
                ) : isCurrent && !gate ? (
                  <LoaderCircle className="spin" size={18} />
                ) : (
                  index + 1
                )}
              </span>
              <div>
                <strong>{label}</strong>
                <small>
                  {index === 0
                    ? `BA · ${run.snapshot.mode !== "mock" ? "AI thật" : "Mô phỏng"}`
                    : liveSite && [2, 4].includes(index)
                      ? "Dev · AI thật"
                      : liveSite && index === 5
                        ? "Kiểm tra cấu trúc file"
                        : owner}
                </small>
                <span className="step-state">{stateLabel}</span>
              </div>
            </li>
          );
        })}
      </ol>
      {run.revision > 1 && (
        <p className="workflow-revision-note">
          Tiến độ của bản chỉnh sửa hiện tại. Các quyết định của bản trước nằm
          trong Lịch sử phê duyệt.
        </p>
      )}
    </section>
  );
}
