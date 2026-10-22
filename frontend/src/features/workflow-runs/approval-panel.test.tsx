import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { ApprovalPanel } from "./approval-panel";
import { ApiError } from "@/lib/api-client";
import type { Artifact, Run } from "@/types/contracts";
const run: Run = {
  id: "run",
  created_at: "",
  work_item_id: "item",
  status: "requirements_approval",
  current_step: "requirements_approval",
  attempt: 1,
  revision: 2,
  repair_count: 0,
  retryable: false,
  failed_step: null,
  gate_id: "gate-2",
  gate_artifact_id: "artifact-2",
  started_at: null,
  ended_at: null,
  failure_reason: null,
  cancellation_reason: null,
  snapshot: { version: "deterministic-v2", mode: "mock" },
};
const artifact: Artifact = {
  id: "artifact-2",
  run_id: "run",
  gate_id: "gate-2",
  kind: "requirements",
  revision: 2,
  attempt: 1,
  created_at: "",
  content: { description: "<script>alert(1)</script>", simulated: true },
};
it("binds an approval to the reviewed session and artifact", () => {
  const onDecision = vi.fn();
  render(
    <ApprovalPanel
      run={run}
      artifact={artifact}
      pending={false}
      error={null}
      onDecision={onDecision}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Phê duyệt" }));
  expect(onDecision).toHaveBeenCalledWith(
    expect.objectContaining({
      decision: "approve",
      gate_id: "gate-2",
      artifact_id: "artifact-2",
      attempt: 1,
    }),
  );
  expect(document.querySelector("script")).toBeNull();
});
it("requires feedback and sends the explicit final revision target", () => {
  const onDecision = vi.fn();
  render(
    <ApprovalPanel
      run={{ ...run, status: "pm_review" }}
      artifact={artifact}
      pending={false}
      error={null}
      onDecision={onDecision}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Yêu cầu chỉnh sửa" }));
  expect(onDecision).not.toHaveBeenCalled();
  expect(screen.getByRole("alert")).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Nhận xét / nội dung cần sửa"), {
    target: { value: "Clarify scope" },
  });
  fireEvent.change(screen.getByRole("combobox"), {
    target: { value: "ba_in_progress" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Yêu cầu chỉnh sửa" }));
  expect(onDecision).toHaveBeenCalledWith(
    expect.objectContaining({
      decision: "reject",
      return_to: "ba_in_progress",
      comment: "Clarify scope",
    }),
  );
});
it("disables decisions without evidence and while pending", () => {
  const { rerender } = render(
    <ApprovalPanel
      run={run}
      pending={false}
      error={null}
      onDecision={vi.fn()}
    />,
  );
  expect(screen.getByRole("button", { name: "Phê duyệt" })).toBeDisabled();
  rerender(
    <ApprovalPanel
      run={run}
      artifact={artifact}
      pending
      error={null}
      onDecision={vi.fn()}
    />,
  );
  expect(screen.getByRole("button", { name: "Đang gửi…" })).toBeDisabled();
});
it("explains conflicts instead of claiming success", () => {
  render(
    <ApprovalPanel
      run={run}
      artifact={artifact}
      pending={false}
      error={new ApiError(409, "Trạng thái đã thay đổi. Tải lại.")}
      onDecision={vi.fn()}
    />,
  );
  expect(screen.getByRole("alert")).toHaveTextContent("Trạng thái đã thay đổi");
});
