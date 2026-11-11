import { Navigate, Outlet, Route, Routes, useLocation } from "react-router-dom";
import Shell from "./components/Shell";
import { Skeleton } from "./components/ui";
import { useAuth } from "./lib/auth";
import Catalog from "./pages/Catalog";
import Dashboard from "./pages/Dashboard";
import History from "./pages/History";
import Login from "./pages/Login";
import StationPage from "./pages/Station";

function Protected() {
  const { user, loading } = useAuth();
  const loc = useLocation();
  if (loading) return <div className="p-10"><Skeleton className="h-10 w-60" /></div>;
  if (!user) return <Navigate to="/login" state={{ from: loc.pathname + loc.search }} replace />;
  return <Outlet />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<Protected />}>
        <Route element={<Shell />}>
          <Route index element={<Dashboard />} />
          <Route path="station/:code" element={<StationPage />} />
          <Route path="history" element={<History />} />
          <Route path="catalog" element={<Catalog />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
