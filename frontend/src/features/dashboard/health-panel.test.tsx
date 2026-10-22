import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import HealthPanel from "./health-panel";

afterEach(() => vi.unstubAllGlobals());
function renderWithClient(element: React.ReactNode): void {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  render(<QueryClientProvider client={client}>{element}</QueryClientProvider>);
}
it("shows loading before confirmation and disables refresh during a request", async () => {
  let resolveResponse!: (response: Response) => void;
  const fetchMock = vi.fn().mockImplementation(
    () =>
      new Promise<Response>((resolve) => {
        resolveResponse = resolve;
      }),
  );
  vi.stubGlobal("fetch", fetchMock);
  renderWithClient(<HealthPanel />);
  expect(screen.getByRole("status")).toHaveTextContent("Đang kiểm tra");
  expect(screen.queryByText("Đã kết nối máy chủ")).not.toBeInTheDocument();
  resolveResponse(Response.json({ status: "ok" }));
  await screen.findByText("Đã kết nối máy chủ");
  fireEvent.click(screen.getByRole("button", { name: "Kiểm tra lại" }));
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Đang kiểm tra…" }),
    ).toBeDisabled(),
  );
  resolveResponse(Response.json({ status: "ok" }));
  await waitFor(() =>
    expect(screen.getByRole("button", { name: "Kiểm tra lại" })).toBeEnabled(),
  );
});
it("recovers from network failure with an explicit retry", async () => {
  vi.spyOn(console, "error").mockImplementation(() => undefined);
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockRejectedValueOnce(new TypeError("offline"))
      .mockResolvedValue(Response.json({ status: "ok" })),
  );
  renderWithClient(<HealthPanel />);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Không kết nối được máy chủ",
  );
  fireEvent.click(screen.getByRole("button", { name: "Thử lại" }));
  expect(await screen.findByText("Đã kết nối máy chủ")).toBeInTheDocument();
});
it("reports an invalid health response safely", async () => {
  vi.spyOn(console, "error").mockImplementation(() => undefined);
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(Response.json("private raw response")),
  );
  renderWithClient(<HealthPanel />);
  expect(await screen.findByRole("alert")).toHaveTextContent("định dạng");
  expect(screen.queryByText("private raw response")).not.toBeInTheDocument();
});
