import { describe, expect, it } from "vitest";
import { shouldPoll, statusPresentation } from "./status";
describe("workflow presentation", () => {
  it.each(["completed", "failed", "cancelled", "draft", "unknown"])(
    "does not poll %s",
    (status) => {
      expect(shouldPoll(status)).toBe(false);
    },
  );
  it.each([
    "queued",
    "requirements_approval",
    "plan_approval",
    "implementation_in_progress",
    "pm_review",
  ])("refreshes nonterminal %s", (status) => {
    expect(shouldPoll(status)).toBe(true);
  });
  it("distinguishes approval, success and failure", () => {
    expect(statusPresentation("plan_approval")[1]).toBe("approval");
    expect(statusPresentation("completed")[1]).toBe("success");
    expect(statusPresentation("failed")[1]).toBe("error");
    expect(statusPresentation("constructor")[1]).toBe("neutral");
  });
});
