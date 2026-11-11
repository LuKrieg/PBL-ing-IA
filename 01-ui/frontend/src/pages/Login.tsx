import { Eye, EyeOff, Lock, User as UserIcon } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { Logo } from "../components/Shell";
import { Button, Input, Label } from "../components/ui";
import { useAuth } from "../lib/auth";

export default function Login() {
  const { user, login } = useAuth();
  const loc = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={(loc.state as { from?: string } | null)?.from ?? "/"} replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(username.trim().toLowerCase(), password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo iniciar sesión");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid min-h-full lg:grid-cols-[1.1fr_1fr]">
      <section className="relative hidden overflow-hidden border-r border-line bg-surface lg:flex lg:flex-col lg:justify-between p-12">
        <div className="grid-bg absolute inset-0" aria-hidden />
        <Logo />
        <div className="relative">
          <p className="font-display text-[11px] font-semibold uppercase tracking-[0.3em] text-accent">Línea de machetes · 3 estaciones</p>
          <h1 className="mt-4 font-display text-7xl font-bold leading-[0.95] tracking-tight">Cada machete,<br />inspeccionado<br /><span className="text-accent">antes de salir.</span></h1>
          <p className="mt-6 max-w-md text-muted">Veredicto OK / Defecto en tiempo real para Enderezado, Montaje e Inyectado, con historial trazable por estación, fecha y tipo de defecto.</p>
        </div>
        <svg viewBox="0 0 600 70" className="relative w-full max-w-xl text-line-strong" aria-hidden>
          {Array.from({ length: 41 }).map((_, i) => (
            <line key={i} x1={i * 14 + 2} x2={i * 14 + 2} y1={i % 5 === 0 ? 8 : 24} y2={40} stroke="currentColor" strokeWidth="1.5" />
          ))}
          <text x="2" y="60" fill="currentColor" fontSize="11" fontFamily="IBM Plex Mono">0 mm</text>
          <text x="548" y="60" fill="currentColor" fontSize="11" fontFamily="IBM Plex Mono">100 mm</text>
        </svg>
      </section>

      <section className="flex items-center justify-center px-6 py-12">
        <form onSubmit={submit} className="w-full max-w-sm" noValidate>
          <div className="lg:hidden mb-10"><Logo /></div>
          <h2 className="font-display text-4xl font-semibold">Iniciar sesión</h2>
          <p className="mt-1 text-sm text-muted">Acceso para personal de planta autorizado.</p>

          <div className="mt-8 space-y-4">
            <div>
              <Label htmlFor="u">Usuario</Label>
              <div className="relative">
                <UserIcon className="pointer-events-none absolute left-3 top-3 size-4 text-muted" aria-hidden />
                <Input id="u" name="username" spellCheck={false} className="pl-9" autoComplete="username" autoCapitalize="none" value={username} onChange={(e) => setUsername(e.target.value)} required autoFocus />
              </div>
            </div>
            <div>
              <Label htmlFor="p">Contraseña</Label>
              <div className="relative">
                <Lock className="pointer-events-none absolute left-3 top-3 size-4 text-muted" aria-hidden />
                <Input id="p" name="password" className="pl-9 pr-10" type={show ? "text" : "password"} autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
                <button type="button" onClick={() => setShow((s) => !s)} className="absolute right-2 top-2 grid size-6 place-items-center rounded text-muted hover:text-ink" aria-label={show ? "Ocultar contraseña" : "Mostrar contraseña"}>
                  {show ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </div>
            </div>
            {error && <p role="alert" className="rounded-md border border-defect/40 bg-defect/10 px-3 py-2 text-sm text-defect">{error}</p>}
            <Button type="submit" className="w-full" loading={busy} disabled={!username || !password}>Entrar</Button>
          </div>
          <p className="mt-8 text-xs text-muted">Demo del checkpoint · equipo Planta · estación PC10. Imágenes simuladas a partir de fotos del catálogo IMACASA.</p>
        </form>
      </section>
    </div>
  );
}
