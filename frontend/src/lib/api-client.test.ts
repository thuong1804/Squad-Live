import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, createApiClient, errorMessage } from "./api-client";

afterEach(() => vi.unstubAllGlobals());
describe("API boundary", () => {
  it.each([401, 403, 404, 409, 422, 500])(
    "handles %i without leaking backend errors",
    async (status) => {
      vi.stubGlobal(
        "fetch",
        vi
          .fn()
          .mockResolvedValue(new Response("secret stack trace", { status })),
      );
      const error = await createApiClient("http://localhost:8000")
        .request("/health", (body) => body)
        .catch((e) => e as unknown);
      expect(error).toBeInstanceOf(ApiError);
      expect(errorMessage(error)).not.toContain("secret");
      if (status === 409)
        expect(errorMessage(error)).toContain("Trạng thái đã thay đổi");
    },
  );
  it("uses configured base and includes session cookies", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(Response.json({ status: "ok" }));
    vi.stubGlobal("fetch", fetchMock);
    await createApiClient("https://api.example.test/").request(
      "/health",
      (body) => body,
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "https://api.example.test/health",
      expect.objectContaining({ credentials: "include" }),
    );
  });
  it("rejects invalid JSON without exposing the response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("<html>private</html>")),
    );
    await expect(
      createApiClient("http://localhost:8000").request(
        "/health",
        (body) => body,
      ),
    ).rejects.toThrow("định dạng");
  });
  it("explains network errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("Failed to fetch")),
    );
    await expect(
      createApiClient("http://localhost:8000").request(
        "/health",
        (body) => body,
      ),
    ).rejects.toThrow("Không kết nối");
  });
  it("rejects credential-bearing and non-HTTP base URLs", () => {
    expect(() => createApiClient("https://user:secret@example.test")).toThrow();
    expect(() => createApiClient("javascript:alert(1)")).toThrow();
  });
});
