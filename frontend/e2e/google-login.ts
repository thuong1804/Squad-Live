import { expect, type Page } from "@playwright/test";

// Google consent and token I/O are offline fixtures; OAuth state, cookies and DB are real.
export async function googleLogin(page: Page): Promise<void> {
  const returnPath = new URL(page.url()).pathname;
  await page.route(
    "**/auth/google/start",
    async (route) => {
      const response = await route.fetch({ maxRedirects: 0 });
      const url = new URL(response.headers().location!);
      const callback = new URL(url.searchParams.get("redirect_uri")!);
      callback.searchParams.set("state", url.searchParams.get("state")!);
      callback.searchParams.set(
        "code",
        `fixture-${url.searchParams.get("nonce")}`,
      );
      await route.fulfill({
        response,
        status: 302,
        headers: { ...response.headers(), location: callback.href },
      });
    },
  );
  await page.getByRole("button", { name: "Đăng nhập bằng Google" }).click();
  await expect(
    page.getByRole("button", { name: "Đăng xuất", exact: true }),
  ).toBeVisible();
  if (returnPath !== "/dashboard") await page.goto(returnPath);
}
