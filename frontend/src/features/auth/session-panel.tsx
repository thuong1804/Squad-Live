import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { api, errorMessage, googleLoginUrl } from "@/lib/api-client";
import { setSession, useIdentity } from "@/lib/session";
import { Button } from "@/components/ui/button";
import HealthPanel from "@/features/dashboard/health-panel";

const sessionSchema = z.discriminatedUnion("authenticated", [
  z.object({ authenticated: z.literal(false) }),
  z.object({
    authenticated: z.literal(true),
    identity: z.string(),
    display_name: z.string(),
    email: z.string(),
    csrf_token: z.string(),
  }),
]);
const sessionOptions = {
  queryKey: ["browser-session"],
  queryFn: ({ signal }: { signal: AbortSignal }) =>
    api.request("/auth/session", sessionSchema.parse, { signal }),
  retry: false,
  staleTime: 10000,
  refetchInterval: 30000,
};

export function SessionControl(): React.JSX.Element | null {
  const identity = useIdentity();
  const client = useQueryClient();
  const { data } = useQuery(sessionOptions);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>(null);
  async function logout(): Promise<void> {
    setPending(true);
    setError(null);
    try {
      await api.request("/auth/logout", z.object({ ok: z.boolean() }).parse, {
        method: "POST",
      });
      await client.cancelQueries();
      setSession("");
      client.clear();
    } catch (reason) {
      setError(reason);
    } finally {
      setPending(false);
    }
  }
  return identity ? (
    <div className="session-control">
      <span>
        {data?.authenticated ? data.display_name || data.email : identity}
      </span>
      <Button
        variant="outline"
        disabled={pending}
        onClick={() => void logout()}
      >
        {pending ? "Đang đăng xuất…" : "Đăng xuất"}
      </Button>
      {error ? <p role="alert">{errorMessage(error)}</p> : null}
    </div>
  ) : null;
}

export function AuthGate({
  children,
}: {
  children: ReactNode;
}): React.JSX.Element {
  const identity = useIdentity();
  const client = useQueryClient();
  const session = useQuery(sessionOptions);
  const config = useQuery({
    queryKey: ["auth-config"],
    queryFn: ({ signal }) =>
      api.request(
        "/auth/config",
        z.object({ google_enabled: z.boolean() }).parse,
        { signal },
      ),
    retry: false,
  });
  useEffect(() => {
    if (!session.data) return;
    const next = session.data.authenticated ? session.data.identity : "";
    if (identity !== next) {
      client.removeQueries({
        predicate: (query) =>
          !["browser-session", "auth-config"].includes(
            String(query.queryKey[0]),
          ),
      });
    }
    setSession(session.data.authenticated ? session.data.csrf_token : "", next);
  }, [session.data, client]);
  const authError = new URLSearchParams(window.location.search).get(
    "auth_error",
  );
  const loginErrors: Record<string, string> = {
    not_configured: "Đăng nhập Google chưa được cấu hình trên máy chủ.",
    invalid_session:
      "Phiên đăng nhập đã hết hạn hoặc không hợp lệ. Hãy thử lại.",
    cancelled: "Bạn đã hủy đăng nhập Google. Có thể thử lại bất cứ lúc nào.",
    login_failed: "Không xác thực được tài khoản Google. Vui lòng thử lại.",
  };
  if (session.isPending)
    return <p role="status">Đang kiểm tra phiên đăng nhập…</p>;
  if (identity && session.data?.authenticated) return <>{children}</>;
  return (
    <>
      <section className="panel content-panel login-panel">
        <p className="eyebrow">SQUAD LIVE</p>
        <h1>Đăng nhập không gian PM</h1>
        <p>
          Dùng tài khoản Google để quản lý dự án, lịch sử công việc và các kết
          nối AI của bạn.
        </p>
        <Button
          disabled={!config.data?.google_enabled}
          onClick={() => window.location.assign(googleLoginUrl)}
        >
          Đăng nhập bằng Google
        </Button>
        <p>
          API key của model được cấu hình riêng trong Cài đặt AI sau khi đăng
          nhập.
        </p>
        {config.data && !config.data.google_enabled && (
          <p role="alert">
            Chưa cấu hình Google OAuth. Cần Client ID và Client Secret trên
            backend để bật đăng nhập.
          </p>
        )}
        {authError && Object.hasOwn(loginErrors, authError) && (
          <p role="alert">{loginErrors[authError]}</p>
        )}
        {(session.error || config.error) && (
          <>
            <p role="alert">{errorMessage(session.error || config.error)}</p>
            <Button
              variant="outline"
              onClick={() => {
                void session.refetch();
                void config.refetch();
              }}
            >
              Thử lại kết nối
            </Button>
          </>
        )}
      </section>
      <HealthPanel />
    </>
  );
}
