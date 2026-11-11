import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, Radio } from "lucide-react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { InspectionImage, StationTag, VerdictBadge } from "../components/domain";
import { Card, ErrorState, SectionTitle, Skeleton } from "../components/ui";
import { api, type Station, type Stats, type StationCode } from "../lib/api";
import { ago, fmtDay, pct, STATION_COLOR, STATION_NAME } from "../lib/format";
import { useLive } from "../lib/live";

function StationCard({ s }: { s: Station }) {
  const hot = s.defect_rate_24h > 0.12;
  return (
    <Link to={`/station/${s.code}`} className="group block focus-visible:outline-offset-4">
      <Card className="h-full p-5 transition-colors group-hover:border-line-strong">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2"><span className="size-2.5 rounded-full" style={{ background: STATION_COLOR[s.code] }} aria-hidden /><span className="num text-sm text-muted">{s.code}</span></div>
            <h3 className="font-display text-3xl font-semibold leading-tight">{s.name}</h3>
          </div>
          <ArrowUpRight className="size-5 text-muted transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-accent" aria-hidden />
        </div>
        <div className="mt-5 grid grid-cols-2 gap-4">
          <div>
            <div className="num text-3xl font-medium">{s.total_24h}</div>
            <div className="text-xs text-muted">inspecciones · 24 h</div>
          </div>
          <div>
            <div className={`num text-3xl font-medium ${hot ? "text-defect" : ""}`}>{pct(s.defect_rate_24h)}</div>
            <div className="text-xs text-muted">defectos · {s.defects_24h} piezas</div>
          </div>
        </div>
        <div className="mt-5 border-t border-line pt-4">
          {s.last ? (
            <div className="flex items-center gap-3">
              <InspectionImage i={s.last} className="w-28 shrink-0" />
              <div className="min-w-0">
                <VerdictBadge verdict={s.last.verdict} />
                <div className="mt-1 truncate text-sm">{s.last.defect_label ?? "Sin defectos"}</div>
                <div className="num text-xs text-muted">{s.last.serial} · {ago(s.last.ts)}</div>
              </div>
            </div>
          ) : <p className="text-sm text-muted">Sin inspecciones todavía.</p>}
        </div>
        {!s.implemented && <p className="mt-3 text-[11px] text-muted">Estación de otro subgrupo · datos simulados</p>}
      </Card>
    </Link>
  );
}

export default function Dashboard() {
  const stations = useQuery({ queryKey: ["stations"], queryFn: () => api<Station[]>("/stations"), refetchInterval: 30000 });
  const stats = useQuery({ queryKey: ["stats", "all", 7], queryFn: () => api<Stats>("/stats?days=7") });
  const { events, status } = useLive(undefined, 12);

  const days = [...new Set(stats.data?.series.map((r) => r.day))].sort();
  const chart = days.map((d) => {
    const row: Record<string, string | number> = { day: fmtDay(d) };
    for (const c of ["PC08", "PC10", "PC12"] as StationCode[]) row[c] = stats.data!.series.find((r) => r.day === d && r.station === c)?.defects ?? 0;
    return row;
  });
  const top = stats.data?.by_defect.slice(0, 7) ?? [];
  const maxTop = Math.max(1, ...top.map((t) => t.count));

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-5xl font-semibold tracking-tight">Tablero general</h1>
          <p className="mt-1 text-muted">Estado de las tres estaciones de la línea de machetes.</p>
        </div>
        <div className="flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1.5 text-sm" aria-live="polite">
          <span className={`size-2 rounded-full ${status === "live" ? "bg-ok live-dot" : status === "connecting" ? "bg-accent" : "bg-defect"}`} aria-hidden />
          {status === "live" ? "En vivo" : status === "connecting" ? "Conectando…" : "Sin conexión"}
        </div>
      </div>

      <section aria-label="Estaciones" className="grid gap-4 md:grid-cols-3">
        {stations.isLoading && [0, 1, 2].map((k) => <Skeleton key={k} className="h-72" />)}
        {stations.error && <div className="md:col-span-3"><ErrorState message={(stations.error as Error).message} onRetry={() => stations.refetch()} /></div>}
        {stations.data?.map((s) => <StationCard key={s.code} s={s} />)}
      </section>

      <div className="grid gap-6 xl:grid-cols-[1.6fr_1fr]">
        <Card className="p-5">
          <SectionTitle right={stats.data && <span className="num text-xs text-muted">{stats.data.defects} defectos / {stats.data.total} piezas · 7 d</span>}>Defectos por día</SectionTitle>
          {stats.isLoading ? <Skeleton className="h-64" /> : (
            <div className="h-64" role="img" aria-label="Gráfico de barras apiladas de defectos por día y estación">
              <ResponsiveContainer>
                <BarChart data={chart} margin={{ left: -18, right: 4, top: 4 }}>
                  <CartesianGrid stroke="var(--line)" vertical={false} />
                  <XAxis dataKey="day" stroke="var(--muted)" tickLine={false} axisLine={false} fontSize={12} />
                  <YAxis stroke="var(--muted)" tickLine={false} axisLine={false} fontSize={12} allowDecimals={false} />
                  <Tooltip cursor={{ fill: "var(--raised)" }} contentStyle={{ background: "var(--raised)", border: "1px solid var(--line-strong)", borderRadius: 8, color: "var(--text)" }} />
                  <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                  {(["PC08", "PC10", "PC12"] as StationCode[]).map((c) => <Bar key={c} dataKey={c} stackId="a" fill={STATION_COLOR[c]} name={`${c} ${STATION_NAME[c]}`} radius={c === "PC12" ? [3, 3, 0, 0] : 0} />)}
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>

        <Card className="p-5">
          <SectionTitle>Defectos más frecuentes · 7 d</SectionTitle>
          {stats.isLoading ? <Skeleton className="h-64" /> : top.length === 0 ? <p className="text-sm text-muted">Sin defectos en el periodo.</p> : (
            <ol className="space-y-3">
              {top.map((t) => (
                <li key={t.code}>
                  <div className="flex justify-between text-sm"><span>{t.label}</span><span className="num text-muted">{t.count}</span></div>
                  <div className="mt-1 h-1.5 rounded-full bg-raised"><div className="h-full rounded-full bg-accent" style={{ width: `${(t.count / maxTop) * 100}%` }} /></div>
                </li>
              ))}
            </ol>
          )}
        </Card>
      </div>

      <Card className="p-5">
        <SectionTitle right={<span className="flex items-center gap-1.5 text-xs text-muted"><Radio className="size-3.5" aria-hidden />Últimas inspecciones</span>}>Actividad en vivo</SectionTitle>
        {events.length === 0 ? <p className="py-6 text-center text-sm text-muted">Esperando inspecciones… llegan cada pocos segundos.</p> : (
          <ul className="divide-y divide-line">
            {events.map((e) => (
              <li key={e.id} className="row-in flex items-center gap-4 py-2.5">
                <span className="num w-16 text-xs text-muted">{new Date(e.ts).toLocaleTimeString("es-SV", { hour12: false })}</span>
                <StationTag code={e.station} />
                <VerdictBadge verdict={e.verdict} />
                <span className="min-w-0 flex-1 truncate text-sm">{e.defect_label ?? "—"}</span>
                <span className="num hidden text-xs text-muted sm:block">{e.serial}</span>
                <span className="num w-14 text-right text-sm">{e.confidence !== null ? pct(e.confidence, 0) : "—"}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
