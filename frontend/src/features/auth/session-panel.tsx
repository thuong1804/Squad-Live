import { useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { api, errorMessage } from "@/lib/api-client";
import { setSession, useIdentity } from "@/lib/session";
import { Button } from "@/components/ui/button";
import HealthPanel from "@/features/dashboard/health-panel";

export function SessionControl(): React.JSX.Element | null {
  const identity = useIdentity();
  const client = useQueryClient();
  return identity ? (
    <div className="session-control">
      <span>{identity}</span>
      <Button
        variant="outline"
        onClick={() => {
          setSession("");
          void client.cancelQueries();
          client.clear();
        }}
      >
        Đăng xuất
      </Button>
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
  const [token, setToken] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>(null);
  async function login(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      const result = await api.request(
        "/api/v1/session",
        z.object({ identity: z.string() }).parse,
        { headers: { Authorization: `Bearer ${token.trim()}` } },
      );
      await client.cancelQueries();
      client.clear();
      setSession(token.trim(), result.identity);
      setToken("");
    } catch (reason) {
      setError(reason);
    } finally {
      setPending(false);
    }
  }
  return identity ? (
    <>{children}</>
  ) : (
    <>
      <section className="panel content-panel login-panel">
        <p className="eyebrow">SQUAD LIVE</p>
        <h1>Kết nối không gian PM</h1>
        <p>
          Nhập token PM do quản trị viên cung cấp. Token chỉ được giữ trong bộ
          nhớ của tab, không lưu trên trình duyệt.
        </p>
        <form
          onSubmit={(e) => {
            void login(e);
          }}
        >
          <label htmlFor="pm-token">Token truy cập</label>
          <input
            id="pm-token"
            type="password"
            autoComplete="off"
            required
            value={token}
            onChange={(e) => setToken(e.target.value)}
          />
          <Button type="submit" disabled={pending || !token.trim()}>
            {pending ? "Đang xác thực…" : "Kết nối"}
          </Button>
          {error ? <p role="alert">{errorMessage(error)}</p> : null}
        </form>
      </section>
      <HealthPanel />
    </>
  );
}
