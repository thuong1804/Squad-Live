import { test, expect } from "@playwright/test";
import { googleLogin } from "./google-login";

test("BYOK requires a saved model, survives login, runs BA and preserves history after disabling key", async ({
  page,
  request,
}) => {
  const token = process.env.E2E_TOKEN!;
  const headers = { Authorization: `Bearer ${token}` };
  const api = "http://127.0.0.1:8001/api/v1";
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/ai-settings");
  await googleLogin(page);
  await page.getByLabel("Tên kết nối").fill("Saved Gemini model");
  await page.getByLabel("Nhà cung cấp").selectOption("gemini");
  await page
    .getByLabel("API key", { exact: true })
    .fill("browser-only-fake-key");
  await page.getByRole("button", { name: "Kiểm tra key và lấy model" }).click();
  await expect(page.getByLabel("Model", { exact: true })).toHaveValue(
    "test-model",
  );
  await page.getByRole("button", { name: "Lưu kết nối", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Saved Gemini model" }),
  ).toBeVisible();
  await expect(page.getByLabel("API key", { exact: true })).toBeEmpty();
  const connections = await (
    await request.get(`${api}/ai-connections`, { headers })
  ).json();
  expect(JSON.stringify(connections)).not.toContain("browser-only-fake-key");
  const connection = connections.items.find(
    (entry: { name: string }) => entry.name === "Saved Gemini model",
  );
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Đăng xuất", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Saved Gemini model" }),
  ).toBeVisible();
  const project = await (
    await request.post(`${api}/projects`, {
      headers,
      data: { name: "BYOK browser" },
    })
  ).json();
  const item = await (
    await request.post(`${api}/projects/${project.id}/work-items`, {
      headers,
      data: { title: "BYOK requirement", description: "A reviewable feature" },
    })
  ).json();
  const missing = await request.post(
    `${api}/work-items/${item.id}/workflow-runs`,
    {
      headers: { ...headers, "Idempotency-Key": "missing-key" },
      data: { mode: "ba_live" },
    },
  );
  expect(missing.status()).toBe(422);
  // Client navigation keeps the in-memory PM session.
  await page.getByRole("link", { name: "Dự án", exact: true }).click();
  await page.getByRole("link", { name: /BYOK browser/ }).click();
  await page.getByRole("link", { name: /BYOK requirement/ }).click();
  await page.getByLabel("Chế độ workflow").selectOption("ba_live");
  await expect(
    page.getByRole("button", { name: "Bắt đầu BA thật" }),
  ).toBeDisabled();
  await page.getByLabel("Nguồn AI").selectOption(connection.id);
  await page.getByRole("button", { name: "Bắt đầu BA thật" }).click();
  await expect(
    page.getByRole("button", { name: "Phê duyệt", exact: true }),
  ).toBeEnabled();
  await expect(
    page.getByText("BA tạo bằng AI · Cần PM kiểm tra").first(),
  ).toBeVisible();
  const runId = page.url().split("/").pop();
  await page.getByLabel("Nhận xét / nội dung cần sửa").fill("Clarify roles");
  await page
    .getByRole("button", { name: "Yêu cầu chỉnh sửa", exact: true })
    .click();
  await expect(page.locator(".approval-panel h3")).toContainText("Bản 2");
  await page
    .getByRole("link", { name: "Cài đặt AI", exact: true })
    .first()
    .click();
  await page.getByText("Tắt kết nối", { exact: true }).click();
  await expect(page.getByRole("alertdialog")).toBeVisible();
  await expect(page.getByRole("button", { name: "Giữ kết nối" })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("alertdialog")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Tắt kết nối", exact: true }),
  ).toBeFocused();
  await page.getByRole("button", { name: "Tắt kết nối", exact: true }).click();
  await page.getByRole("button", { name: "Xác nhận tắt" }).click();
  await expect(page.getByText(/gemini \/ test-model · Đã tắt/)).toBeVisible();
  const artifacts = await (
    await request.get(`${api}/workflow-runs/${runId}/artifacts`, { headers })
  ).json();
  expect(artifacts.items).toHaveLength(2);
  expect(
    await page.evaluate(() =>
      JSON.stringify({ ...localStorage, ...sessionStorage }),
    ),
  ).not.toContain("browser-only-fake-key");
  await page.screenshot({
    path: "test-results/byok-settings.png",
    fullPage: true,
  });
  expect(errors).toEqual([]);
});
