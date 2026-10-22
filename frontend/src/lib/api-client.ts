import { getToken } from "./session";
const messages: Record<number, string> = {
  401: "Phiên đăng nhập chưa có hoặc đã hết hạn. Vui lòng đăng nhập lại.",
  403: "Bạn chưa có quyền thực hiện thao tác này.",
  404: "Không tìm thấy tài nguyên hoặc endpoint chưa được triển khai.",
  409: "Trạng thái đã thay đổi. Hãy tải lại dữ liệu trước khi thử lại.",
  422: "Dữ liệu chưa hợp lệ. Vui lòng kiểm tra các trường đã nhập.",
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
      init: RequestInit = {},
    ): Promise<T> {
      if (!path.startsWith("/") || path.startsWith("//") || path.includes("\\"))
        throw new ApiError(0, "Đường dẫn API không hợp lệ.");
      let response: Response;
      const headers = new Headers(init.headers);
      headers.set("Accept", "application/json");
      if (init.body) headers.set("Content-Type", "application/json");
      if (
        path.startsWith("/api/v1/") &&
        getToken() &&
        !headers.has("Authorization")
      )
        headers.set("Authorization", `Bearer ${getToken()}`);
      try {
        response = await fetch(`${baseUrl.replace(/\/$/, "")}${path}`, {
          ...init,
          credentials: "include",
          signal: init.signal
            ? AbortSignal.any([init.signal, AbortSignal.timeout(15000)])
            : AbortSignal.timeout(15000),
          headers,
        });
      } catch (error) {
        if (init.signal?.aborted) throw error;
        throw new ApiError(
          0,
          "Không kết nối được máy chủ. Kiểm tra backend, mạng và cấu hình CORS rồi thử lại.",
        );
      }
      if (!response.ok)
        throw new ApiError(
          response.status,
          messages[response.status] ??
            (response.status >= 500
              ? "Máy chủ đang gặp sự cố. Vui lòng thử lại sau."
              : "Yêu cầu chưa được chấp nhận. Vui lòng thử lại."),
        );
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

export const api = createApiClient(
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000",
);
