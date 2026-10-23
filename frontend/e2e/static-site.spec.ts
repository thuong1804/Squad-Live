import { test, expect } from "@playwright/test";
import { googleLogin } from "./google-login";
import { execFileSync } from "node:child_process";
import { resolve, join } from "node:path";
import { pathToFileURL } from "node:url";

test("static site requires both approvals, previews isolated JS, downloads and keeps revisions", async ({
  page,
  request,
}, testInfo) => {
  const api = "http://127.0.0.1:8001/api/v1";
  const headers = { Authorization: `Bearer ${process.env.E2E_TOKEN!}` };
  const connection = await (
    await request.post(`${api}/ai-connections`, {
      headers,
      data: {
        name: "Website model",
        provider: "gemini",
        model: "test-model",
        api_key: "browser-only-fake-key",
      },
    })
  ).json();
  const project = await (
    await request.post(`${api}/projects`, {
      headers,
      data: { name: "Static demo" },
    })
  ).json();
  const item = await (
    await request.post(`${api}/projects/${project.id}/work-items`, {
      headers,
      data: {
        title: "Create a counter website",
        description: "A page with a working counter button",
      },
    })
  ).json();
  await page.goto(`/work-items/${item.id}`);
  await googleLogin(page);
  await page.getByLabel("Chế độ workflow").selectOption("static_site");
  await expect(
    page.getByRole("button", { name: "Bắt đầu tạo website" }),
  ).toBeDisabled();
  await page.getByLabel("Nguồn AI").selectOption(connection.id);
  await page.getByRole("button", { name: "Bắt đầu tạo website" }).click();
  await expect(page.locator(".review-kicker")).toHaveText(
    "Lần duyệt 1/3 · Yêu cầu của BA",
  );
  await expect(
    page.getByRole("tab", { name: "Preview", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Phê duyệt", exact: true }).click();
  await expect(page.locator(".review-kicker")).toHaveText(
    "Lần duyệt 2/3 · Kế hoạch của Dev",
  );
  await expect(page.locator(".approval-panel")).toContainText(
    "Click increments counter",
  );
  await expect(
    page.getByRole("tab", { name: "Preview", exact: true }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Phê duyệt", exact: true }).click();
  await expect(page.locator(".review-kicker")).toHaveText(
    "Lần duyệt 3/3 · Đánh giá cuối của PM",
  );
  await expect(
    page.getByRole("heading", { name: "Tester AI", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Reviewer AI", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("region", { name: "Reviewer AI" })).toContainText(
    "kết quả Chromium",
  );
  await expect(
    page.getByRole("region", { name: "Kiểm thử trình duyệt" }),
  ).toBeVisible();
  await expect(page.getByAltText(/Ảnh chụp desktop/)).toBeVisible();
  await expect(page.getByAltText(/Ảnh chụp mobile/)).toBeVisible();
  await page.getByRole("tab", { name: "Danh sách file", exact: true }).focus();
  await page.keyboard.press("ArrowRight");
  await expect(
    page.getByRole("tab", { name: "Preview", exact: true }),
  ).toHaveAttribute("aria-selected", "true");
  const frame = page.frameLocator('iframe[title="Preview website"]');
  await expect(
    frame.getByRole("heading", { name: "Static website" }),
  ).toBeVisible();
  await frame.getByRole("button", { name: "Count 0" }).click();
  await expect(frame.getByRole("button", { name: "Count 1" })).toBeVisible();
  await expect(frame.locator("body")).toHaveCSS(
    "background-color",
    "rgb(243, 246, 250)",
  );
  const isolated = await frame.locator("body").evaluate(() => {
    try {
      return window.parent.document.body === document.body;
    } catch {
      return "isolated";
    }
  });
  expect(isolated).toBe("isolated");
  expect(
    await frame.locator("body").evaluate(async () => {
      try {
        await fetch("http://127.0.0.1:8001/health");
        return false;
      } catch {
        return true;
      }
    }),
  ).toBe(true);
  await page.getByRole("button", { name: "Xem mobile", exact: true }).click();
  await expect(page.locator("iframe")).toHaveCSS("max-width", "390px");
  const downloaded = page.waitForEvent("download");
  await page.getByRole("link", { name: "Tải ZIP" }).click();
  const download = await downloaded;
  expect(download.suggestedFilename()).toMatch(/^website-.*\.zip$/);
  const zipPath = testInfo.outputPath("website.zip");
  const sitePath = testInfo.outputPath("standalone");
  await download.saveAs(zipPath);
  execFileSync(resolve("../backend/.venv/Scripts/python.exe"), [
    "-c",
    "import sys,zipfile; z=zipfile.ZipFile(sys.argv[1]); assert set(z.namelist()) == {'index.html','styles.css','script.js'}; z.extractall(sys.argv[2])",
    zipPath,
    sitePath,
  ]);
  const standalone = await page.context().newPage();
  const errors: string[] = [];
  standalone.on("pageerror", (error) => errors.push(error.message));
  await standalone.goto(pathToFileURL(join(sitePath, "index.html")).href);
  await expect(
    standalone.getByRole("heading", { name: "Static website" }),
  ).toBeVisible();
  await standalone.getByRole("button", { name: "Count 0" }).click();
  await expect(
    standalone.getByRole("button", { name: "Count 1" }),
  ).toBeVisible();
  await expect(standalone.locator("body")).toHaveCSS(
    "background-color",
    "rgb(243, 246, 250)",
  );
  await standalone.setViewportSize({ width: 390, height: 844 });
  expect(
    await standalone.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect(errors).toEqual([]);
  await standalone.close();
  await page.screenshot({
    path: "test-results/static-site-preview.png",
    fullPage: true,
  });
  await page.getByLabel("Nhận xét / nội dung cần sửa").fill("Add a footer");
  await page
    .getByRole("button", { name: "Yêu cầu chỉnh sửa", exact: true })
    .click();
  await expect(page.locator(".review-kicker")).toHaveText(
    "Lần duyệt 2/3 · Kế hoạch của Dev",
  );
  await expect(page.locator(".website-results")).toContainText("Bản cũ");
  await page.getByRole("button", { name: "Phê duyệt", exact: true }).click();
  await expect(page.locator(".review-kicker")).toHaveText(
    "Lần duyệt 3/3 · Đánh giá cuối của PM",
  );
  await expect(
    page.getByLabel("Phiên bản website").locator("option"),
  ).toHaveCount(2);
  await page.getByRole("button", { name: "Phê duyệt", exact: true }).click();
  await expect(page.locator(".page-heading .status-badge")).toHaveText(
    "Hoàn tất",
  );
  await page.reload();
  await expect(page.getByRole("link", { name: "Tải ZIP" })).toBeVisible();
  await expect(page.locator(".workflow-progress")).toContainText(
    "Website đã được PM duyệt",
  );
});
