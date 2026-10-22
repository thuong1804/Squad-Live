import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { WorkflowProgress } from "./progress";
import type { Run } from "@/types/contracts";

const run = {
  status: "plan_approval",
  revision: 1,
  failed_step: null,
  snapshot: { mode: "ba_live" },
} as Run;

it("moves the current step back when a revision returns to BA", () => {
  const { container, rerender } = render(<WorkflowProgress run={run} />);
  expect(container.querySelector('[aria-current="step"]')).toHaveTextContent(
    "Duyệt kế hoạch",
  );
  rerender(
    <WorkflowProgress
      run={{ ...run, status: "ba_in_progress", revision: 2 }}
    />,
  );
  expect(container.querySelector('[aria-current="step"]')).toHaveTextContent(
    "Phân tích yêu cầu",
  );
  expect(container.querySelectorAll(".step-done")).toHaveLength(0);
  expect(
    screen.queryByRole("link", { name: /Đến bước cần duyệt/ }),
  ).not.toBeInTheDocument();
});

it("marks a failed step without pretending later steps finished", () => {
  const { container } = render(
    <WorkflowProgress
      run={{ ...run, status: "failed", failed_step: "ba_in_progress" }}
    />,
  );
  expect(container.querySelector('[aria-current="step"]')).toHaveTextContent(
    "Gặp lỗi",
  );
  expect(container.querySelectorAll(".step-done")).toHaveLength(0);
});

it("does not infer completed steps for a cancelled run", () => {
  const { container } = render(
    <WorkflowProgress run={{ ...run, status: "cancelled" }} />,
  );
  expect(container.querySelectorAll(".step-done")).toHaveLength(0);
  expect(container.querySelector('[aria-current="step"]')).toBeNull();
});

it("explains the deliverable limitation when the workflow completes", () => {
  render(<WorkflowProgress run={{ ...run, status: "completed" }} />);
  expect(screen.getByText(/chưa có file HTML/)).toBeVisible();
  expect(
    screen.queryByRole("link", { name: /Đến bước cần duyệt/ }),
  ).not.toBeInTheDocument();
});
