import clsx from "clsx";
import { ClipboardList, LayoutDashboard, LogOut, Moon, ScanLine, Sun, Tags } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { STATION_COLOR, STATION_NAME } from "../lib/format";
import { useTheme } from "../lib/theme";
import type { StationCode } from "../lib/api";
import { Button } from "./ui";

const STATIONS: StationCode[] = ["PC08", "PC10", "PC12"];

const link = ({ isActive }: { isActive: boolean }) =>
  clsx(
    "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
    isActive ? "bg-raised text-ink font-medium shadow-[inset_2px_0_0_var(--accent)]" : "text-muted hover:text-ink hover:bg-raised/60",
  );

export function Logo() {
  return (
    <div className="flex items-center gap-2.5">
      <svg viewBox="0 0 32 32" className="size-8" aria-hidden><rect width="32" height="32" rx="7" fill="var(--raised)" /><path d="M5 22c4-1 9-3 14-6l8-6-1 6-6 5-15 4z" fill="var(--accent)" /></svg>
      <div className="leading-none">
        <div className="font-display text-xl font-bold tracking-wide" translate="no">IMACASA</div>
        <div className="text-[10px] uppercase tracking-[0.2em] text-muted mt-0.5">Inspección visual</div>
      </div>
    </div>
  );
}

export default function Shell() {
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();

  return (
    <div className="relative min-h-full lg:grid lg:grid-cols-[248px_1fr]">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[60] focus:rounded-md focus:bg-accent focus:px-3 focus:py-2 focus:text-accent-ink">Saltar al contenido</a>
      <aside className="hidden lg:flex flex-col gap-6 border-r border-line bg-surface px-4 py-5 sticky top-0 h-screen">
        <Logo />
        <nav className="flex flex-col gap-1" aria-label="Principal">
          <NavLink to="/" end className={link}><LayoutDashboard className="size-4" aria-hidden />Tablero general</NavLink>
          <div className="mt-4 mb-1 px-3 font-display text-[11px] font-semibold uppercase tracking-[0.18em] text-muted">Estaciones</div>
          {STATIONS.map((s) => (
            <NavLink key={s} to={`/station/${s}`} className={link}>
              <span className="size-2 rounded-full" style={{ background: STATION_COLOR[s] }} aria-hidden />
              <span className="num">{s}</span>
              <span className="text-muted text-[13px]">{STATION_NAME[s]}</span>
            </NavLink>
          ))}
          <div className="mt-4 mb-1 px-3 font-display text-[11px] font-semibold uppercase tracking-[0.18em] text-muted">Registro</div>
          <NavLink to="/history" className={link}><ClipboardList className="size-4" aria-hidden />Historial</NavLink>
          <NavLink to="/catalog" className={link}><Tags className="size-4" aria-hidden />Catálogo de defectos</NavLink>
        </nav>
        <div className="mt-auto space-y-3">
          <div className="rounded-lg border border-line bg-raised p-3">
            <div className="text-sm font-medium">{user?.name}</div>
            <div className="text-xs text-muted">{user?.role === "admin" ? "Administrador" : "Operador"} · <span className="num">{user?.username}</span></div>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" className="flex-1" onClick={toggle} aria-label={theme === "dark" ? "Cambiar a tema claro" : "Cambiar a tema oscuro"}>
              {theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}{theme === "dark" ? "Claro" : "Oscuro"}
            </Button>
            <Button variant="outline" size="sm" className="flex-1" onClick={logout}><LogOut className="size-4" />Salir</Button>
          </div>
        </div>
      </aside>

      <div className="min-w-0 pb-20 lg:pb-0">
        <header className="lg:hidden sticky top-0 z-20 flex items-center justify-between border-b border-line bg-surface/90 px-4 py-3 backdrop-blur">
          <Logo />
          <div className="flex gap-1">
            <Button variant="ghost" size="sm" onClick={toggle} aria-label="Cambiar tema">{theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}</Button>
            <Button variant="ghost" size="sm" onClick={logout} aria-label="Salir"><LogOut className="size-4" /></Button>
          </div>
        </header>
        <div className="grid-bg pointer-events-none absolute inset-x-0 top-0 h-[420px] lg:left-[248px]" aria-hidden />
        <main id="main" tabIndex={-1} className="relative mx-auto w-full max-w-[1400px] px-4 py-6 sm:px-8 sm:py-8">
          <Outlet />
        </main>
      </div>

      <nav className="lg:hidden fixed bottom-0 inset-x-0 z-20 grid grid-cols-5 border-t border-line bg-surface/95 backdrop-blur" aria-label="Móvil">
        {[
          { to: "/", icon: LayoutDashboard, label: "Tablero", end: true },
          { to: "/station/PC08", icon: ScanLine, label: "PC08" },
          { to: "/station/PC10", icon: ScanLine, label: "PC10" },
          { to: "/station/PC12", icon: ScanLine, label: "PC12" },
          { to: "/history", icon: ClipboardList, label: "Historial" },
        ].map(({ to, icon: Icon, label, end }) => (
          <NavLink key={to} to={to} end={end} className={({ isActive }) => clsx("flex flex-col items-center gap-0.5 py-2 text-[11px]", isActive ? "text-accent" : "text-muted")}>
            <Icon className="size-5" aria-hidden />{label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
