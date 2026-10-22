import { test, expect } from "@playwright/test";
import { googleLogin } from "./google-login";

test("workspace pages fit desktop and mobile and keep AI key controls accessible", async ({
  page,
}) => {
  await page.goto("/ai-settings");
  await expect(
    page.getByRole("heading", { name: "Đăng nhập không gian PM" }),
  ).toBeVisible();
  await page.screenshot({ path: "test-results/ui-login.png", fullPage: true });
  await googleLogin(page);
  const key = page.getByLabel("API key", { exact: true });
  await key.fill("layout-fixture-key");
  await page.getByRole("button", { name: "Hiện API key", exact: true }).click();
  await expect(key).toHaveAttribute("type", "text");
  await page.getByRole("button", { name: "Ẩn API key", exact: true }).click();
  await expect(key).toHaveAttribute("type", "password");
  await page.getByLabel("Nhà cung cấp").selectOption("gemini");
  await expect(key).toBeEmpty();
  await expect(
    page.getByRole("button", { name: "Lưu kết nối", exact: true }),
  ).toBeDisabled();
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 });
    for (const [path, heading, name] of [
      ["/ai-settings", "Cài đặt AI", "settings"],
      ["/dashboard", "Điều phối cùng nhau.", "dashboard"],
      ["/projects", "Dự án", "projects"],
      ["/projects/new", "Tạo dự án", "new-project"],
    ]) {
      await page.goto(path);
      await expect(
        page.getByRole("heading", { name: heading, exact: true }),
      ).toBeVisible();
      await expect(
        page.getByRole("navigation", { name: "Điều hướng chính" }),
      ).toBeVisible();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      ).toBe(true);
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.screenshot({
        path: `test-results/ui-${name}-${width}.png`,
        fullPage: true,
      });
    }
  }
});
