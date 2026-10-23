import { z } from "zod";

const assessment = z.object({
  summary: z.string(),
  verdict: z.enum(["ready_for_pm", "changes_requested"]),
  browser_tests_executed: z.literal(false),
  findings: z.array(
    z.object({
      severity: z.string(),
      file: z.string(),
      evidence: z.string(),
      recommendation: z.string(),
    }),
  ),
  manual_checks: z.array(z.string()),
  limitations: z.array(z.string()),
});

export function QualityReport({
  title,
  value,
  browserChecked = false,
}: {
  title: string;
  value: unknown;
  browserChecked?: boolean;
}): React.JSX.Element | null {
  const parsed = assessment.safeParse(value);
  if (!parsed.success) return null;
  const report = parsed.data;
  return (
    <section className="quality-report document-view" aria-label={title}>
      <header className="quality-heading">
        <div>
          <span className="eyebrow">BÁO CÁO ĐÁNH GIÁ</span>
          <h3>{title}</h3>
        </div>
        <span
          className={`status-badge ${report.verdict === "changes_requested" ? "status-error" : "status-approval"}`}
        >
          {report.verdict === "changes_requested"
            ? "AI đề nghị chỉnh sửa"
            : "Sẵn sàng để PM đánh giá"}
        </span>
      </header>
      <p className="document-summary">{report.summary}</p>
      <p className="simulation-notice">
        {browserChecked
          ? "AI phân tích mã nguồn và đọc kết quả Chromium. AI không tự chạy trình duyệt; PM cần xác minh tương tác trong Preview."
          : "AI phân tích mã nguồn. Chưa chạy kiểm thử trình duyệt; PM cần xác minh trong Preview."}
      </p>
      <h4>Phát hiện ({report.findings.length})</h4>
      {report.findings.map((finding, index) => (
        <article className="finding-card" key={index}>
          <header className="finding-heading">
            <span
              className={`status-badge ${finding.severity === "minor" ? "status-approval" : "status-error"}`}
            >
              {(
                {
                  critical: "Nghiêm trọng",
                  major: "Quan trọng",
                  minor: "Nhẹ",
                } as Record<string, string>
              )[finding.severity] ?? finding.severity}
            </span>
            <code>{finding.file}</code>
            <span className="finding-index">#{index + 1}</span>
          </header>
          <div className="finding-body">
            <h5>Bằng chứng trong mã nguồn</h5>
            <p className="pre-wrap">{finding.evidence}</p>
          </div>
          <div className="finding-recommendation">
            <h5>Đề xuất chỉnh sửa</h5>
            <p className="pre-wrap">{finding.recommendation}</p>
          </div>
        </article>
      ))}
      {!report.findings.length && (
        <p>
          AI chưa phát hiện vấn đề; đây không phải bằng chứng website không có
          lỗi.
        </p>
      )}
      <h4>Cần kiểm tra thủ công</h4>
      <ol className="manual-checks">
        {report.manual_checks.map((check, index) => (
          <li key={index}>{check}</li>
        ))}
      </ol>
      <h4>Giới hạn đánh giá</h4>
      <ul>
        {report.limitations.map((limit, index) => (
          <li key={index}>{limit}</li>
        ))}
      </ul>
    </section>
  );
}
