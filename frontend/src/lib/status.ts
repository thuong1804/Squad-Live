export const statuses = {
  draft: ["Bản nháp", "neutral"],
  queued: ["Đang chờ", "neutral"],
  ba_in_progress: ["BA đang phân tích", "active"],
  requirements_approval: ["Chờ duyệt yêu cầu", "approval"],
  plan_in_progress: ["Đang lập kế hoạch", "active"],
  plan_approval: ["Chờ duyệt kế hoạch", "approval"],
  implementation_in_progress: ["Đang triển khai", "active"],
  checks_in_progress: ["Đang chạy kiểm tra", "active"],
  repair_in_progress: ["Đang sửa lỗi", "active"],
  pr_created: ["Đã tạo PR", "active"],
  testing_in_progress: ["Đang kiểm thử", "active"],
  pm_review: ["Chờ PM đánh giá", "approval"],
  completed: ["Hoàn tất", "success"],
  failed: ["Thất bại", "error"],
  cancelled: ["Đã hủy", "neutral"],
} as const;
export type WorkflowStatus = keyof typeof statuses;
export function statusPresentation(status: string): readonly [string, string] {
  return Object.hasOwn(statuses, status)
    ? statuses[status as WorkflowStatus]
    : ["Trạng thái chưa được hỗ trợ", "neutral"];
}
export function shouldPoll(status: string): boolean {
  return (
    Object.hasOwn(statuses, status) &&
    !["draft", "completed", "failed", "cancelled"].includes(status)
  );
}
