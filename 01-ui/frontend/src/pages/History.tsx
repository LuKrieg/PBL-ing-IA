import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { ArrowDownUp, ChevronLeft, ChevronRight, FilterX, Search } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Drawer } from "../components/Drawer";
import { ConfidenceMeter, InspectionImage, Measurements, SourceIcon, StationTag, VerdictBadge } from "../components/domain";
import { Button, Card, EmptyState, ErrorState, Input, Label, Select, Skeleton } from "../components/ui";
import { api, qs, type DefectDef, type Inspection, type Page, type Station, type StationCode } from "../lib/api";
import { fmtDateTime, pct, STATION_NAME } from "../lib/format";

const PAGE_SIZE = 20;
const STATIONS: StationCode[] = ["PC08", "PC10", "PC12"];

function CompareStrip({ defect, exclude }: { defect: DefectDef; exclude?: StationCode }) {
  const stations = defect.stations.filter((s) => s !== exclude);
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {stations.map((s) => <CompareColumn key={s} defect={defect} station={s} />)}
    </div>
  );
}
function CompareColumn({ defect, station }: { defect: DefectDef; station: StationCode }) {
  const q = useQuery({ queryKey: ["compare", defect.code, station], queryFn: () => api<Page<Inspection>>(`/inspections${qs({ defect: defect.code, station, page_size: 2 })}`) });
  return (
    <div>
      <div className="mb-2 flex items-center gap-2"><StationTag code={station} withName /></div>
      {q.isLoading ? <Skeleton className="h-28" /> : (q.data?.items.length ? (
        <div className="space-y-2">{q.data.items.map((i) => <div key={i.id}><InspectionImage i={i} /><div className="num mt-1 text-xs text-muted">{i.serial} · {fmtDateTime(i.ts)} · {i.confidence !== null ? pct(i.confidence, 0) : "—"}</div></div>)}</div>
      ) : <p className="text-sm text-muted">Sin registros en esta estación.</p>)}
    </div>
  );
}

function Detail({ i, defects }: { i: Inspection; defects: DefectDef[] }) {
  const def = defects.find((d) => d.code === i.defect_code);
  const shared = def && def.stations.length > 1;
  return (
    <div className="space-y-6">
      <InspectionImage i={i} />
      <div className="flex flex-wrap items-center gap-3"><VerdictBadge verdict={i.verdict} big /><StationTag code={i.station} withName /></div>
      <dl className="grid grid-cols-2 gap-4 text-sm">
        <div className="col-span-2"><dt className="text-xs text-muted">Defecto</dt><dd className="font-display text-2xl font-semibold">{i.defect_label ?? "Sin defectos"}</dd></div>
        <div><dt className="text-xs text-muted">Pieza</dt><dd className="num">{i.serial}</dd></div>
        <div><dt className="text-xs text-muted">Fecha y hora</dt><dd className="num">{fmtDateTime(i.ts)}</dd></div>
        <div><dt className="text-xs text-muted">Origen</dt><dd><SourceIcon source={i.source} /></dd></div>
        <div><dt className="text-xs text-muted">Modelo · latencia</dt><dd className="num">{i.model}{i.latency_ms ? ` · ${i.latency_ms} ms` : ""}</dd></div>
        {def?.capture && <div className="col-span-2"><dt className="text-xs text-muted">Captura recomendada</dt><dd className="text-muted">{def.capture}</dd></div>}
        {i.notes && <div className="col-span-2"><dt className="text-xs text-muted">Nota</dt><dd>{i.notes}</dd></div>}
      </dl>
      <div><div className="mb-1 text-xs text-muted">Confianza</div><ConfidenceMeter value={i.confidence} verdict={i.verdict} /></div>
      <Measurements i={i} />
      {def && shared && (
        <section className="border-t border-line pt-5">
          <h3 className="font-display text-lg font-semibold">Mismo defecto en otra estación</h3>
          <p className="mb-3 text-sm text-muted">«{def.label}» existe en {def.stations.join(" y ")}. Así se ve en la otra estación:</p>
          <CompareStrip defect={def} exclude={i.station} />
        </section>
      )}
    </div>
  );
}

export default function History() {
  const [sp, setSp] = useSearchParams();
  const [open, setOpen] = useState<Inspection | null>(null);
  const [qText, setQText] = useState(sp.get("q") ?? "");
  const f = { station: sp.get("station") ?? "", defect: sp.get("defect") ?? "", verdict: sp.get("verdict") ?? "", from: sp.get("from") ?? "", to: sp.get("to") ?? "", q: sp.get("q") ?? "", sort: sp.get("sort") ?? "desc", page: Number(sp.get("page") ?? 1) || 1 };
  const set = useCallback((patch: Record<string, string>) => {
    const n = new URLSearchParams(sp);
    for (const [k, v] of Object.entries(patch)) v ? n.set(k, v) : n.delete(k);
    if (!("page" in patch)) n.delete("page");
    setSp(n, { replace: true });
  }, [sp, setSp]);

  useEffect(() => {
    const t = setTimeout(() => qText !== f.q && set({ q: qText }), 300);
    return () => clearTimeout(t);
  }, [qText]); // eslint-disable-line react-hooks/exhaustive-deps

  const stations = useQuery({ queryKey: ["stations"], queryFn: () => api<Station[]>("/stations") });
  const defects = (() => {
    const m = new Map<string, DefectDef>();
    stations.data?.forEach((s) => s.defects.forEach((d) => m.set(d.code, d)));
    return [...m.values()];
  })();
  const defectOptions = defects.filter((d) => !f.station || d.stations.includes(f.station as StationCode));
  const sel = defects.find((d) => d.code === f.defect);

  const list = useQuery({
    queryKey: ["history", f],
    queryFn: () => api<Page<Inspection>>(`/inspections${qs({ station: f.station, defect: f.defect, verdict: f.verdict, date_from: f.from, date_to: f.to, q: f.q, sort: f.sort, page: f.page, page_size: PAGE_SIZE })}`),
    placeholderData: (p) => p,
  });
  const pages = Math.max(1, Math.ceil((list.data?.total ?? 0) / PAGE_SIZE));
  const active = [f.station, f.defect, f.verdict, f.from, f.to, f.q].some(Boolean);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-5xl font-semibold tracking-tight">Historial</h1>
        <p className="mt-1 text-muted">Todas las inspecciones, filtrables por estación, fecha y tipo de defecto.</p>
      </div>

      <Card className="p-4 sm:p-5">
        <div className="mb-4 flex flex-wrap items-center gap-2" role="group" aria-label="Estación">
          {[{ v: "", label: "Todas" }, ...STATIONS.map((s) => ({ v: s, label: `${s} · ${STATION_NAME[s]}` }))].map((o) => (
            <button key={o.v} onClick={() => set({ station: o.v, defect: "" })} aria-pressed={f.station === o.v}
              className={clsx("rounded-full border px-3.5 py-1.5 text-sm transition-colors", f.station === o.v ? "border-accent bg-accent/15 text-accent" : "border-line-strong text-muted hover:text-ink")}>{o.label}</button>
          ))}
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-[1.4fr_1fr_1fr_1fr_1.2fr]">
          <div><Label htmlFor="fd">Defecto</Label>
            <Select id="fd" value={f.defect} onChange={(e) => set({ defect: e.target.value, verdict: e.target.value ? "DEFECT" : f.verdict })}>
              <option value="">Todos</option>
              {defectOptions.map((d) => <option key={d.code} value={d.code}>{d.label}{d.stations.length > 1 ? " (PC10 + PC12)" : ""}</option>)}
            </Select></div>
          <div><Label htmlFor="fv">Veredicto</Label>
            <Select id="fv" value={f.verdict} onChange={(e) => set({ verdict: e.target.value })}>
              <option value="">Todos</option><option value="OK">OK</option><option value="DEFECT">Defecto</option>
            </Select></div>
          <div><Label htmlFor="ff">Desde</Label><Input id="ff" type="date" value={f.from} max={f.to || undefined} onChange={(e) => set({ from: e.target.value })} /></div>
          <div><Label htmlFor="ft">Hasta</Label><Input id="ft" type="date" value={f.to} min={f.from || undefined} onChange={(e) => set({ to: e.target.value })} /></div>
          <div><Label htmlFor="fq">Pieza</Label>
            <div className="relative"><Search className="pointer-events-none absolute left-3 top-3 size-4 text-muted" aria-hidden /><Input id="fq" name="q" autoComplete="off" spellCheck={false} className="num pl-9" placeholder="M980-…" value={qText} onChange={(e) => setQText(e.target.value)} /></div></div>
        </div>
        <div className="mt-4 flex flex-wrap items-center justify-between gap-2 text-sm text-muted">
          <span aria-live="polite"><span className="num text-ink">{list.data?.total ?? "…"}</span> resultados</span>
          <div className="flex gap-2">
            <Button variant="ghost" size="sm" onClick={() => set({ sort: f.sort === "desc" ? "asc" : "desc" })}><ArrowDownUp className="size-4" />{f.sort === "desc" ? "Más recientes primero" : "Más antiguos primero"}</Button>
            {active && <Button variant="ghost" size="sm" onClick={() => { setQText(""); setSp({}, { replace: true }); }}><FilterX className="size-4" />Limpiar filtros</Button>}
          </div>
        </div>
      </Card>

      {sel && sel.stations.length > 1 && !f.station && (
        <Card className="p-5">
          <h2 className="font-display text-xl font-semibold">Comparativa: «{sel.label}» por estación</h2>
          <p className="mb-4 text-sm text-muted">El mismo defecto se registra en {sel.stations.join(" y ")}; las imágenes cambian porque la pieza está en otra etapa.</p>
          <CompareStrip defect={sel} />
        </Card>
      )}

      <Card className="overflow-hidden">
        {list.isLoading ? <div className="space-y-2 p-4">{Array.from({ length: 8 }).map((_, k) => <Skeleton key={k} className="h-14" />)}</div>
          : list.error ? <ErrorState message={(list.error as Error).message} onRetry={() => list.refetch()} />
          : list.data!.items.length === 0 ? <EmptyState title="Sin resultados" hint="Prueba con otro rango de fechas o quita algún filtro." action={active ? <Button variant="outline" size="sm" onClick={() => setSp({}, { replace: true })}>Limpiar filtros</Button> : undefined} />
          : (
            <div className={clsx("overflow-x-auto transition-opacity", list.isPlaceholderData && "opacity-60")}>
              <table className="w-full min-w-[820px] text-sm">
                <thead className="border-b border-line text-left text-xs uppercase tracking-wider text-muted">
                  <tr><th className="px-4 py-3 font-medium">Imagen</th><th className="px-3 font-medium">Fecha</th><th className="px-3 font-medium">Estación</th><th className="px-3 font-medium">Pieza</th><th className="px-3 font-medium">Veredicto</th><th className="px-3 font-medium">Defecto</th><th className="px-3 text-right font-medium">Confianza</th><th className="px-4 font-medium">Origen</th></tr>
                </thead>
                <tbody>
                  {list.data!.items.map((i) => (
                    <tr key={i.id} className="cursor-pointer border-b border-line/60 transition-colors hover:bg-raised focus-within:bg-raised" onClick={() => setOpen(i)}>
                      <td className="px-4 py-2"><InspectionImage i={i} className="w-24" /></td>
                      <td className="num px-3 whitespace-nowrap text-muted">{fmtDateTime(i.ts)}</td>
                      <td className="px-3"><StationTag code={i.station} /></td>
                      <td className="px-3"><button className="num underline-offset-4 hover:underline" onClick={(e) => { e.stopPropagation(); setOpen(i); }}>{i.serial}</button></td>
                      <td className="px-3"><VerdictBadge verdict={i.verdict} /></td>
                      <td className="px-3">{i.defect_label ?? <span className="text-muted">—</span>}</td>
                      <td className="num px-3 text-right">{i.confidence !== null ? pct(i.confidence) : "—"}</td>
                      <td className="px-4"><SourceIcon source={i.source} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        <div className="flex items-center justify-between border-t border-line px-4 py-3 text-sm">
          <span className="num text-muted">Página {f.page} de {pages}</span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={f.page <= 1} onClick={() => set({ page: String(f.page - 1) })}><ChevronLeft className="size-4" />Anterior</Button>
            <Button variant="outline" size="sm" disabled={f.page >= pages} onClick={() => set({ page: String(f.page + 1) })}>Siguiente<ChevronRight className="size-4" /></Button>
          </div>
        </div>
      </Card>

      <Drawer open={!!open} onClose={() => setOpen(null)} title={open ? `Inspección ${open.serial}` : ""}>
        {open && <Detail i={open} defects={defects} />}
      </Drawer>
    </div>
  );
}
