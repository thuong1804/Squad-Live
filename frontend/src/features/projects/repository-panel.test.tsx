import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { RepositoryPanel } from "./repository-panel";
import type { Project } from "@/types/contracts";

const project: Project = {
  id: "project-1",
  name: "Demo",
  description: "",
  owner: "pm",
  status: "active",
  repository_path: "D:\\demo",
  created_at: "2026-10-23T00:00:00Z",
  updated_at: "2026-10-23T00:00:00Z",
};

afterEach(() => vi.unstubAllGlobals());

it("navigates nested Git files and shows readable source lines", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string) => {
      if (url.includes("/repository/file?")) {
        return Promise.resolve(
          Response.json({
            path: "src/components/App.tsx",
            content:
              "export default function App() {\n  return <main>Hello</main>;\n}\n",
          }),
        );
      }
      return Promise.resolve(
        Response.json({
          path: "D:\\demo",
          branch: "main",
          head: "1234567890abcdef",
          dirty: false,
          files: ["src/components/App.tsx", "src/index.tsx"],
        }),
      );
    }),
  );
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <RepositoryPanel project={project} />
    </QueryClientProvider>,
  );

  expect(await screen.findByText("Working tree sạch")).toBeVisible();
  expect(
    screen.queryByRole("button", { name: "App.tsx" }),
  ).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "components" }));
  fireEvent.click(screen.getByRole("button", { name: "App.tsx" }));

  const code = await screen.findByLabelText("Mã nguồn src/components/App.tsx");
  expect(
    within(code).getByText("export default function App() {"),
  ).toBeVisible();
  expect(within(code).getByText("2")).toBeVisible();
  expect(screen.getByText("3 dòng · UTF-8 · Chỉ đọc")).toBeVisible();

  fireEvent.change(screen.getByPlaceholderText("Tìm file…"), {
    target: { value: "index" },
  });
  expect(
    await screen.findByRole("button", { name: /index\.tsx/ }),
  ).toBeVisible();
});
