import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, it } from "vitest";
import { WorkspaceDiffBrowser } from "./workspace-diff-browser";
import type { WorkspaceFile } from "@/types/contracts";

const files: WorkspaceFile[] = [
  {
    path: "src/components/App.tsx",
    status: "modified",
    diff: "@@ -1 +1 @@\n-old\n+new\n",
    truncated: false,
  },
  {
    path: "src/index.tsx",
    status: "added",
    diff: "+import App from './components/App';\n",
    truncated: false,
  },
  {
    path: "README.md",
    status: "deleted",
    diff: "-Old instructions\n",
    truncated: false,
  },
];

it("groups changed files by folder and switches the displayed diff", () => {
  render(<WorkspaceDiffBrowser files={files} />);
  expect(
    within(
      screen.getByLabelText("Git diff của src/components/App.tsx"),
    ).getByText("+new"),
  ).toBeVisible();

  fireEvent.click(screen.getByRole("button", { name: /src/i }));
  expect(screen.queryByTitle("src/components/App.tsx")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /src/i }));
  fireEvent.click(screen.getByTitle("README.md"));
  expect(
    within(screen.getByLabelText("Git diff của README.md")).getByText(
      "-Old instructions",
    ),
  ).toBeVisible();
  expect(screen.getByText("Đã xóa")).toBeVisible();

  fireEvent.change(
    screen.getByRole("searchbox", { name: "Tìm file thay đổi" }),
    {
      target: { value: "index" },
    },
  );
  expect(screen.queryByTitle("README.md")).not.toBeInTheDocument();
  expect(
    within(screen.getByLabelText("Git diff của src/index.tsx")).getByText(
      "+import App from './components/App';",
    ),
  ).toBeVisible();
});
