import { Link, Outlet, useLocation } from "react-router-dom";

const NAV_ITEMS = [
  { path: "/", label: "Dashboard" },
  { path: "/providers", label: "Providers" },
  { path: "/topics", label: "Topics" },
];

export default function AppLayout() {
  const location = useLocation();
  const backendUrl =
    import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

  return (
    <div className="layout">
      <header className="header">
        <Link to="/" className="header-title">
          LongNovelInsight
        </Link>
        <span className="header-version">v0.1.0</span>
      </header>

      <nav className="nav">
        {NAV_ITEMS.map((item) => (
          <Link
            key={item.path}
            to={item.path}
            className={`nav-link${location.pathname === item.path ? " nav-link--active" : ""}`}
          >
            {item.label}
          </Link>
        ))}
      </nav>

      <main className="main">
        <Outlet />
      </main>

      <footer className="footer">
        API: <code>{backendUrl}</code>
      </footer>
    </div>
  );
}
