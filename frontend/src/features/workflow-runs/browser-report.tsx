import { useSuspenseQuery } from "@tanstack/react-query";
import { z } from "zod";
import { api } from "@/lib/api-client";
import type { Run } from "@/types/contracts";

const viewportSchema = z.object({
  viewport: z.enum(["desktop", "mobile"]),
  width: z.number(),
  height: z.number(),
  loaded: z.boolean(),
  horizontal_overflow: z.boolean(),
  broken_images: z.number(),
  javascript_errors: z.array(z.string()),
  resource_errors: z.array(z.string()),
  screenshot_base64: z.string(),
});
const responseSchema = z.object({
  report: z
    .object({
      browser_tests_executed: z.literal(true),
      engine: z.literal("chromium"),
      viewports: z.array(viewportSchema),
      scope: z.string(),
    })
    .nullable(),
});

export function BrowserEvidence({
  run,
  websiteId,
  revision,
}: {
  run: Run;
  websiteId: string;
  revision: number;
}): React.JSX.Element {
  const { data } = useSuspenseQuery({
    queryKey: ["browser-report", run.id, websiteId],
    queryFn: ({ signal }) =>
      api.request(
        `/api/v1/workflow-runs/${run.id}/websites/${websiteId}/browser-report`,
        responseSchema.parse,
        { signal },
      ),
    refetchInterval: (query) =>
      !query.state.data?.report &&
      revision === run.revision &&
      !["failed", "cancelled"].includes(run.status)
        ? 3000
        : false,
  });
  if (!data.report)
    return (
      <p className="browser-evidence-pending" role="status">
        {revision === run.revision
          ? "Bằng chứng trình duyệt chưa sẵn sàng."
          : "Bản website này chưa có bằng chứng trình duyệt."}
      </p>
    );
  return (
    <section className="browser-evidence" aria-label="Kiểm thử trình duyệt">
      <div className="section-heading">
        <div>
          <h3>Kiểm thử trình duyệt</h3>
          <p>Chromium đã mở bản website này ở desktop và mobile.</p>
        </div>
        <span className="status-badge status-success">Đã chạy</span>
      </div>
      <div className="browser-evidence-grid">
        {data.report.viewports.map((view) => {
          const passed =
            view.loaded &&
            !view.horizontal_overflow &&
            !view.broken_images &&
            !view.javascript_errors.length &&
            !view.resource_errors.length;
          return (
            <article className="browser-viewport" key={view.viewport}>
              <header>
                <div>
                  <strong>
                    {view.viewport === "desktop" ? "Desktop" : "Mobile"}
                  </strong>
                  <small>
                    {view.width} × {view.height}
                  </small>
                </div>
                <span
                  className={`status-badge ${passed ? "status-success" : "status-error"}`}
                >
                  {passed ? "Không phát hiện lỗi" : "Có vấn đề"}
                </span>
              </header>
              <img
                alt={`Ảnh chụp ${view.viewport === "desktop" ? "desktop" : "mobile"} của website phiên bản ${revision}`}
                src={`data:image/jpeg;base64,${view.screenshot_base64}`}
                loading="lazy"
              />
              <details className="browser-image-detail">
                <summary>Xem ảnh lớn</summary>
                <img
                  alt="Ảnh chụp kích thước lớn"
                  src={`data:image/jpeg;base64,${view.screenshot_base64}`}
                  loading="lazy"
                />
              </details>
              <ul>
                <li>Tải trang: {view.loaded ? "Thành công" : "Thất bại"}</li>
                <li>Tràn ngang: {view.horizontal_overflow ? "Có" : "Không"}</li>
                <li>Ảnh lỗi: {view.broken_images}</li>
                <li>Lỗi JavaScript: {view.javascript_errors.length}</li>
                <li>Lỗi tài nguyên: {view.resource_errors.length}</li>
              </ul>
              {[...view.javascript_errors, ...view.resource_errors].length >
                0 && (
                <details>
                  <summary>Chi tiết lỗi</summary>
                  <ul>
                    {[...view.javascript_errors, ...view.resource_errors].map(
                      (error, index) => (
                        <li key={index}>{error}</li>
                      ),
                    )}
                  </ul>
                </details>
              )}
            </article>
          );
        })}
      </div>
      <p className="field-hint">
        Bộ kiểm tra cố định: tải trang, JavaScript, tài nguyên, ảnh và tràn
        ngang. Chưa tự kiểm tra tương tác hoặc toàn bộ tiêu chí nghiệm thu; PM
        vẫn cần xem Preview.
      </p>
    </section>
  );
}
