import { Component, Suspense } from "react";
import type { ReactNode } from "react";
import {
  QueryErrorResetBoundary,
  useSuspenseQuery,
} from "@tanstack/react-query";
import { RefreshCw, Server, CheckCircle2, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { errorMessage } from "@/lib/api-client";
import { healthOptions } from "./api";

class HealthErrorBoundary extends Component<
  { children: ReactNode; onReset: () => void },
  { error: unknown }
> {
  state: { error: unknown } = { error: null };
  static getDerivedStateFromError(error: unknown): { error: unknown } {
    return { error };
  }
  render(): ReactNode {
    return this.state.error ? (
      <div className="connection-content">
        <AlertCircle className="error-icon" size={22} />
        <div role="alert">
          <strong>Chưa thể xác minh kết nối</strong>
          <p>{errorMessage(this.state.error)}</p>
        </div>
        <Button
          variant="outline"
          onClick={() => {
            this.props.onReset();
            this.setState({ error: null });
          }}
        >
          <RefreshCw size={15} />
          Thử lại
        </Button>
      </div>
    ) : (
      this.props.children
    );
  }
}

function HealthResult(): React.JSX.Element {
  const { isFetching, refetch, dataUpdatedAt, error } =
    useSuspenseQuery(healthOptions);
  return (
    <div className="connection-content">
      <CheckCircle2 className="success-icon" size={22} />
      <div aria-live="polite">
        <strong>
          {error ? "Lần kiểm tra mới nhất thất bại" : "Đã kết nối máy chủ"}
        </strong>
        <p>
          {error
            ? errorMessage(error)
            : `Kiểm tra lúc ${new Date(dataUpdatedAt).toLocaleTimeString("vi-VN")}. Kết nối thành công chưa xác nhận các tính năng nghiệp vụ.`}
        </p>
      </div>
      <Button
        variant="outline"
        disabled={isFetching}
        onClick={() => {
          void refetch();
        }}
      >
        <RefreshCw size={15} className={isFetching ? "spin" : ""} />
        {isFetching ? "Đang kiểm tra…" : "Kiểm tra lại"}
      </Button>
    </div>
  );
}

export default function HealthPanel(): React.JSX.Element {
  return (
    <section className="connection panel" aria-labelledby="connection-heading">
      <div className="panel-heading">
        <h2 id="connection-heading">
          <Server size={18} />
          Kết nối hệ thống
        </h2>
        <span className="subtle">Backend API</span>
      </div>
      <QueryErrorResetBoundary>
        {({ reset }) => (
          <HealthErrorBoundary onReset={reset}>
            <Suspense
              fallback={
                <div className="connection-content" role="status">
                  <RefreshCw size={20} className="spin" />
                  <p>Đang kiểm tra kết nối máy chủ…</p>
                </div>
              }
            >
              <HealthResult />
            </Suspense>
          </HealthErrorBoundary>
        )}
      </QueryErrorResetBoundary>
    </section>
  );
}
