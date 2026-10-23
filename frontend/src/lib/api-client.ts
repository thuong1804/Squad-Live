import { getCsrfToken, setSession } from "./session";
const messages: Record<number, string> = {
  401: "Phiên đăng nhập chưa có hoặc đã hết hạn. Vui lòng đăng nhập lại.",
  403: "Bạn chưa có quyền thực hiện thao tác này.",
  404: "Không tìm thấy tài nguyên hoặc endpoint chưa được triển khai.",
  409: "Trạng thái đã thay đổi. Hãy tải lại dữ liệu trước khi thử lại.",
  413: "Repository quá lớn để xem trong phiên bản này.",
  415: "Chỉ có thể xem file văn bản UTF-8 nhỏ hơn 256 KiB.",
  422: "Dữ liệu chưa hợp lệ. Vui lòng kiểm tra các trường đã nhập.",
};
const codeMessages: Record<string, string> = {
  connection_required:
    "Hãy thêm API key và chọn model trong Cài đặt AI trước khi chạy BA thật.",
  key_storage_unavailable:
    "Backend chưa sẵn sàng lưu/đọc API key. Kiểm tra cấu hình mã hóa.",
  connection_disabled: "Kết nối đã bị tắt. Hãy chọn kết nối khác.",
  provider_authentication: "API key không hợp lệ hoặc không có quyền truy cập.",
  provider_quota_exhausted:
    "Nhà cung cấp báo hết quota hoặc số dư. Kiểm tra tài khoản API.",
  provider_rate_limit:
    "Nhà cung cấp đang giới hạn yêu cầu. Kiểm tra quota hoặc thử lại sau.",
  provider_timeout: "Nhà cung cấp phản hồi quá lâu. Vui lòng thử lại.",
  provider_unavailable: "Chưa kết nối được nhà cung cấp AI. Vui lòng thử lại.",
  provider_service_unavailable:
    "Nhà cung cấp AI tạm thời không sẵn sàng (HTTP 503). Chờ rồi thử lại hoặc chọn model khác.",
  model_unavailable:
    "Model không khả dụng hoặc không hỗ trợ API đang dùng. Hãy chọn model khác trong Cài đặt AI.",
  invalid_repository_path:
    "Hãy nhập đường dẫn tuyệt đối tới thư mục gốc Git trên máy chạy backend.",
  invalid_repository:
    "Thư mục cần là một Git working tree đã có ít nhất một commit.",
  repository_unavailable:
    "Không đọc được repository đã kết nối. Kiểm tra thư mục và thử lại.",
  repository_too_large:
    "Repository có quá nhiều file tracked để xem trong phiên bản này.",
  file_not_text:
    "Chỉ có thể xem file văn bản UTF-8 nhỏ hơn 256 KiB.",
  folder_picker_unavailable:
    "Không mở được hộp thoại chọn thư mục trên máy chạy backend. Hãy nhập đường dẫn thủ công.",
  local_only:
    "Chỉ có thể chọn thư mục khi dùng web trên cùng máy với backend.",
};

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function errorMessage(error: unknown): string {
  return error instanceof ApiError
    ? error.message
    : "Không thể tải dữ liệu. Vui lòng thử lại.";
}

export function createApiClient(baseUrl: string) {
  const base = new URL(baseUrl);
  if (
    !["http:", "https:"].includes(base.protocol) ||
    base.username ||
    base.password ||
    base.search ||
    base.hash
  ) {
    throw new Error(
      "VITE_API_BASE_URL phải là URL HTTP(S) không chứa thông tin đăng nhập, query hoặc fragment.",
    );
  }
  return {
    async request<T>(
      path: string,
      parse: (body: unknown) => T,
      init: RequestInit & { timeoutMs?: number } = {},
    ): Promise<T> {
      if (!path.startsWith("/") || path.startsWith("//") || path.includes("\\"))
        throw new ApiError(0, "Đường dẫn API không hợp lệ.");
      let response: Response;
      const { timeoutMs = 15000, ...fetchInit } = init;
      const headers = new Headers(init.headers);
      headers.set("Accept", "application/json");
      if (init.body) headers.set("Content-Type", "application/json");
      if (
        !["GET", "HEAD"].includes((init.method || "GET").toUpperCase()) &&
        getCsrfToken()
      )
        headers.set("X-CSRF-Token", getCsrfToken());
      try {
        response = await fetch(`${baseUrl.replace(/\/$/, "")}${path}`, {
          ...fetchInit,
          credentials: "include",
          signal: init.signal
            ? AbortSignal.any([init.signal, AbortSignal.timeout(timeoutMs)])
            : AbortSignal.timeout(timeoutMs),
          headers,
        });
      } catch (error) {
        if (init.signal?.aborted) throw error;
        throw new ApiError(
          0,
          "Không kết nối được máy chủ. Kiểm tra backend, mạng và cấu hình CORS rồi thử lại.",
        );
      }
      if (!response.ok) {
        if (response.status === 401) setSession("");
        let safeMessage: string | undefined;
        try {
          const body: unknown = await response.json();
          if (
            body &&
            typeof body === "object" &&
            "error" in body &&
            body.error &&
            typeof body.error === "object" &&
            "code" in body.error &&
            typeof body.error.code === "string"
          )
            safeMessage = Object.hasOwn(codeMessages, body.error.code)
              ? codeMessages[body.error.code]
              : undefined;
        } catch {
          /* Fall back to status; never display provider error bodies. */
        }
        throw new ApiError(
          response.status,
          safeMessage ??
            messages[response.status] ??
            (response.status >= 500
              ? "Máy chủ đang gặp sự cố. Vui lòng thử lại sau."
              : "Yêu cầu chưa được chấp nhận. Vui lòng thử lại."),
        );
      }
      try {
        return parse(await response.json());
      } catch {
        throw new ApiError(
          response.status,
          "Phản hồi máy chủ chưa đúng định dạng mong đợi.",
        );
      }
    },
  };
}

const apiBase = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
export const websiteDownloadUrl = (runId: string, artifactId: string): string =>
  `${apiBase.replace(/\/$/, "")}/api/v1/workflow-runs/${encodeURIComponent(runId)}/websites/${encodeURIComponent(artifactId)}/download`;
export const api = createApiClient(apiBase);
export const googleLoginUrl = `${apiBase.replace(/\/$/, "")}/auth/google/start`;
