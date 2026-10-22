import { test, expect } from "@playwright/test";
import { googleLogin } from "./google-login";

test("PM creates, requests changes, approves all gates, and sees durable evidence", async ({
  page,
  request,
}) => {
  const token = process.env.E2E_TOKEN!;
  const headers = { Authorization: `Bearer ${token}` };
  const api = "http://127.0.0.1:8001/api/v1";
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/dashboard");
  await googleLogin(page);
  await expect(
    page.getByRole("heading", { name: "Điều phối cùng nhau." }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Quản lý dự án" }).click();
  await page.getByRole("link", { name: "Tạo dự án" }).click();
  await page.getByLabel("Tên dự án").fill("Browser verification");
  await page
    .getByLabel("Mô tả", { exact: true })
    .fill("Real backend, isolated PostgreSQL schema");
  await page.getByRole("button", { name: "Tạo dự án", exact: true }).click();
  await page.getByRole("link", { name: "Tạo công việc" }).click();
  await page
    .getByLabel("Tiêu đề", { exact: true })
    .fill("Review revised requirements");
  await page
    .getByLabel("Mô tả yêu cầu")
    .fill("Verify PM feedback reaches the next review artifact.");
  await page
    .getByLabel("Tiêu chí nghiệm thu")
    .fill("Old approvals must be rejected.");
  await page
    .getByRole("button", { name: "Tạo công việc", exact: true })
    .click();
  await page.getByRole("button", { name: "Bắt đầu workflow mô phỏng" }).click();
  await expect(
    page.getByRole("button", { name: "Phê duyệt", exact: true }),
  ).toBeEnabled();
  const runId = page.url().split("/").pop()!;
  await expect(page.locator('[aria-current="step"]')).toContainText(
    "Duyệt yêu cầu",
  );
  await expect(page.locator(".review-kicker")).toHaveText(
    "Lần duyệt 1/3 · Yêu cầu của BA",
  );
  await page.screenshot({
    path: "test-results/run-review.png",
    fullPage: true,
  });
  const first = await (
    await request.get(`${api}/workflow-runs/${runId}`, { headers })
  ).json();
  await page
    .getByLabel("Nhận xét / nội dung cần sửa")
    .fill("Add a negative case");
  await page
    .getByRole("button", { name: "Yêu cầu chỉnh sửa", exact: true })
    .click();
  await expect(page.locator(".approval-panel")).toContainText("Bản 2");
  await expect(page.locator(".approval-panel")).toContainText(
    "Add a negative case",
  );
  const stale = await request.post(`${api}/workflow-runs/${runId}/approvals`, {
    headers,
    data: {
      step: first.status,
      attempt: first.attempt,
      gate_id: first.gate_id,
      artifact_id: first.gate_artifact_id,
      decision: "approve",
    },
  });
  expect(stale.status()).toBe(409);
  // Deliberately act from another client while the UI still shows the previous gate.
  const current = await (
    await request.get(`${api}/workflow-runs/${runId}`, { headers })
  ).json();
  await request.post(`${api}/workflow-runs/${runId}/approvals`, {
    headers,
    data: {
      step: current.status,
      attempt: current.attempt,
      gate_id: current.gate_id,
      artifact_id: current.gate_artifact_id,
      decision: "approve",
    },
  });
  await page.getByRole("button", { name: "Phê duyệt", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Trạng thái đã thay đổi");
  await expect(page.locator(".approval-panel h3")).toContainText("plan");
  await expect(page.locator('[aria-current="step"]')).toContainText(
    "Duyệt kế hoạch",
  );
  await page.getByRole("button", { name: "Phê duyệt", exact: true }).click();
  await expect(page.locator(".approval-panel h3")).toContainText("delivery");
  await expect(page.locator('[aria-current="step"]')).toContainText(
    "Đánh giá cuối",
  );
  await page.getByRole("button", { name: "Phê duyệt", exact: true }).click();
  await expect(page.locator(".page-heading .status-badge")).toHaveText(
    "Hoàn tất",
  );
  await expect(page.locator(".workflow-progress")).toContainText(
    "chưa có file HTML",
  );
  await expect(page.locator('[aria-current="step"]')).toHaveCount(0);
  await page
    .getByText("Chi tiết thực thi và lịch sử workflow", { exact: true })
    .click();
  await page
    .getByRole("tab", { name: "Lịch sử phê duyệt", exact: true })
    .click();
  await expect(page.locator(".run-columns")).toContainText(
    "Add a negative case",
  );
  await expect(page.locator(".run-columns .artifact")).toHaveCount(4);
  await expect(page.locator(".run-columns .artifact").first()).toContainText(
    "google:browseruser",
  );
  expect(
    (
      await (
        await request.get(`${api}/workflow-runs/${runId}/approvals`, {
          headers,
        })
      ).json()
    ).items,
  ).toHaveLength(4);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "test-results/run-mobile.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({
    path: "test-results/run-desktop.png",
    fullPage: true,
  });
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Đăng xuất", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".page-heading .status-badge")).toHaveText(
    "Hoàn tất",
  );
  expect(errors).toEqual([]);
});

test("cancel requires confirmation and archived project cannot create work", async ({
  page,
  request,
}) => {
  const headers = { Authorization: `Bearer ${process.env.E2E_TOKEN!}` };
  const api = "http://127.0.0.1:8001/api/v1";
  const project = await (
    await request.post(`${api}/projects`, {
      headers,
      data: { name: "Cancellation test" },
    })
  ).json();
  const item = await (
    await request.post(`${api}/projects/${project.id}/work-items`, {
      headers,
      data: { title: "Cancel", description: "Cancel verification" },
    })
  ).json();
  const run = await (
    await request.post(`${api}/work-items/${item.id}/workflow-runs`, {
      headers: { ...headers, "Idempotency-Key": "cancel-test" },
    })
  ).json();
  await page.goto(`/workflow-runs/${run.id}`);
  await googleLogin(page);
  await page.getByRole("button", { name: "Hủy workflow", exact: true }).click();
  await expect(page.getByRole("alertdialog")).toBeVisible();
  await page.getByRole("button", { name: "Tiếp tục công việc" }).click();
  await expect(
    page.getByRole("button", { name: "Hủy workflow", exact: true }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "Hủy workflow", exact: true }).click();
  await page.getByRole("button", { name: "Xác nhận hủy" }).click();
  await expect(page.locator(".page-heading .status-badge")).toHaveText(
    "Đã hủy",
  );
  await request.patch(`${api}/projects/${project.id}`, {
    headers,
    data: { status: "archived" },
  });
  await page.goto(`/projects/${project.id}/work-items/new`);
  await expect(
    page.getByRole("button", { name: "Tạo công việc", exact: true }),
  ).toBeDisabled();
});
