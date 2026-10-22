import {
  createRootRoute,
  Link,
  Outlet,
  useRouterState,
} from "@tanstack/react-router";
import {
  LayoutDashboard,
  Layers3,
  FolderKanban,
  ShieldCheck,
} from "lucide-react";
import { AuthGate, SessionControl } from "@/features/auth/session-panel";
import { DataBoundary } from "@/components/shared/data-boundary";

function Shell(): React.JSX.Element {
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  });
  return (
    <div className="app-shell">
      <a href="#main" className="skip-link">
        Đến nội dung chính
      </a>
      <aside className="sidebar">
        <Link to="/dashboard" className="brand">
          <span className="brand-icon">
            <Layers3 size={23} />
          </span>
          Squad<span className="brand-light">Live</span>
        </Link>
        <div className="workspace">
          <span className="workspace-avatar">PM</span>
          <div>
            Không gian làm việc<small>AI Agent Team</small>
          </div>
        </div>
        <nav aria-label="Điều hướng chính">
          <p className="nav-label">ĐIỀU PHỐI</p>
          <Link to="/dashboard" activeProps={{ className: "nav-active" }}>
            <LayoutDashboard size={18} />
            Tổng quan
          </Link>
        </nav>
        <nav aria-label="Dự án">
          <Link to="/projects" activeProps={{ className: "nav-active" }}>
            <FolderKanban size={18} />
            Dự án
          </Link>
        </nav>
        <div className="sidebar-footer">
          <ShieldCheck size={18} />
          <p>
            Con người quyết định.
            <br />
            <span>AI hỗ trợ thực thi.</span>
          </p>
        </div>
      </aside>
      <div className="main-wrap">
        <header className="topbar">
          <span>
            Không gian làm việc <span className="separator">/</span>{" "}
            <strong>PM Console</strong>
          </span>
          <SessionControl />
        </header>
        <main id="main" tabIndex={-1}>
          <AuthGate>
            <DataBoundary key={pathname}>
              <Outlet />
            </DataBoundary>
          </AuthGate>
        </main>
        <footer className="footer">
          SQUAD LIVE <span>Không gian điều phối AI Agent</span>
        </footer>
      </div>
    </div>
  );
}
export const Route = createRootRoute({
  component: Shell,
  notFoundComponent: () => (
    <section className="panel">
      <h1>Không tìm thấy trang</h1>
      <p>Trang này chưa tồn tại hoặc chưa được hỗ trợ.</p>
      <Link to="/dashboard">Về tổng quan</Link>
    </section>
  ),
  errorComponent: () => (
    <section className="panel" role="alert">
      <h1>Không thể mở trang</h1>
      <p>Vui lòng tải lại trang để thử lại.</p>
      <a href="/dashboard">Tải lại tổng quan</a>
    </section>
  ),
});
