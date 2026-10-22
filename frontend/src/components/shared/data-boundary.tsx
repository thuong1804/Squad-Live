import { Component, Suspense } from "react";
import type { ReactNode } from "react";
import { QueryErrorResetBoundary } from "@tanstack/react-query";
import { errorMessage } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
class Boundary extends Component<
  { children: ReactNode; reset: () => void },
  { error: unknown }
> {
  state: { error: unknown } = { error: null };
  static getDerivedStateFromError(error: unknown): { error: unknown } {
    return { error };
  }
  render(): ReactNode {
    return this.state.error ? (
      <div className="panel content-panel" role="alert">
        <p>{errorMessage(this.state.error)}</p>
        <Button
          onClick={() => {
            this.props.reset();
            this.setState({ error: null });
          }}
        >
          Thử lại
        </Button>
      </div>
    ) : (
      this.props.children
    );
  }
}
export function DataBoundary({
  children,
}: {
  children: ReactNode;
}): React.JSX.Element {
  return (
    <QueryErrorResetBoundary>
      {({ reset }) => (
        <Boundary reset={reset}>
          <Suspense
            fallback={
              <div className="panel content-panel" role="status">
                Đang tải dữ liệu…
              </div>
            }
          >
            {children}
          </Suspense>
        </Boundary>
      )}
    </QueryErrorResetBoundary>
  );
}
