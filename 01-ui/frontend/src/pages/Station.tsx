import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { Pause, Play, Radio, Ruler } from "lucide-react";
import { useMemo, useState, type FormEvent } from "react";
import { Navigate, useParams } from "react-router-dom";
import { ConfidenceMeter, InspectionImage, Measurements, SourceIcon, StationTag, VerdictBadge, ViabilityBadge } from "../components/domain";
import { Button, Card, ErrorState, Input, Label, SectionTitle, Skeleton } from "../components/ui";
import { api, qs, type Inspection, type Page, type Station, type StationCode } from "../lib/api";
import { useAuth } from "../lib/auth";
import { ago, fmtDateTime, fmtTime, STATION_NAME, TASK_LABEL } from "../lib/format";
import { useLive } from "../lib/live";

const CODES = ["PC08", "PC10", "PC12"];

function SimulatorControl() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["sim"], queryFn: () => api<{ running: boolean; interval_s: number; model: string }>("/simulator") });
  const m = useMutation({
    mutationFn: (run: boolean) => api(`/simulator/${run ? "start" : "stop"}`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sim"] }),
  });
  if (!q.data) return null;
  return (
    <Button variant="outline" size="sm" loading={m.isPending} onClick={() => m.mutate(!q.data!.running)} title="Solo administrador">
      {q.data.running ? <Pause className="size-4" /> : <Play className="size-4" />}
      Simulador {q.data.running ? `activo · ${q.data.interval_s}s` : "detenido"}
    </Button>
  );
}

function ManualEntry({ station }: { station: StationCode }) {
  const qc = useQueryClient();
  const [thk, setThk] = useState("");
  const [serial, setSerial] = useState("");
  const [notes, setNotes] = useState("");
  const m = useMutation({
    mutationFn: () => api<Inspection>("/inspections/manual", { method: "POST", json: { station, thickness_mm: Number(thk), serial: serial || undefined, notes: notes || undefined } }),
    onSuccess: () => {
      setThk(""); setSerial(""); setNotes("");
      qc.invalidateQueries({ queryKey: ["recent", station] });
      qc.invalidateQueries({ queryKey: ["stations"] });
    },
  });
  const valid = thk !== "" && Number(thk) > 0 && Number(thk) < 50;
  return (
    <Card className="p-5">
      <SectionTitle>Registro por instrumento</SectionTitle>
      <p className="mb-4 text-sm text-muted">El <strong className="text-ink">espesor</strong> no se resuelve con visión por computadora desde una vista superior. Se mide con calibrador y se registra aquí.</p>
      <form onSubmit={(e: FormEvent) => { e.preventDefault(); if (valid) m.mutate(); }} className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div><Label htmlFor="thk">Espesor (mm)</Label><Input id="thk" name="thickness_mm" autoComplete="off" inputMode="decimal" type="number" step="0.01" min="0.1" max="49" value={thk} onChange={(e) => setThk(e.target.value)} placeholder="Ej. 3.50…" className="num" /></div>
          <div><Label htmlFor="ser">Serie (opcional)</Label><Input id="ser" name="serial" autoComplete="off" spellCheck={false} value={serial} maxLength={24} onChange={(e) => setSerial(e.target.value)} placeholder="Ej. M980-001234…" className="num" /></div>
        </div>
        <div><Label htmlFor="nt">Nota</Label><Input id="nt" name="notes" autoComplete="off" value={notes} maxLength={400} onChange={(e) => setNotes(e.target.value)} placeholder="Opcional…" /></div>
        <p className="num text-xs text-muted">Nominal 3.5 mm ± 0.3 mm (supuesto; confirmar con la ficha de IMACASA)</p>
        {m.error && <p role="alert" className="text-sm text-defect">{(m.error as Error).message}</p>}
        {m.data && <p role="status" className={clsx("text-sm", m.data.verdict === "OK" ? "text-ok" : "text-defect")}>Registrado: {m.data.verdict === "OK" ? "dentro de tolerancia" : "FUERA de tolerancia"} · {m.data.serial}</p>}
        <Button type="submit" className="w-full" loading={m.isPending} disabled={!valid}><Ruler className="size-4" />Registrar medición</Button>
      </form>
    </Card>
  );
}

export default function StationPage() {
  const { code } = useParams();
  const { user } = useAuth();
  if (!code || !CODES.includes(code)) return <Navigate to="/" replace />;
  return <StationView key={code} code={code as StationCode} isAdmin={user?.role === "admin"} />;
}

function StationView({ code, isAdmin }: { code: StationCode; isAdmin: boolean }) {
  const [selected, setSelected] = useState<Inspection | null>(null);
  const stations = useQuery({ queryKey: ["stations"], queryFn: () => api<Station[]>("/stations"), refetchInterval: 30000 });
  const recent = useQuery({ queryKey: ["recent", code], queryFn: () => api<Page<Inspection>>(`/inspections${qs({ station: code, page_size: 14 })}`) });
  const { events, status } = useLive(code, 14);
  const station = stations.data?.find((s) => s.code === code);

  const feed = useMemo(() => {
    const seen = new Set<number>();
    return [...events, ...(recent.data?.items ?? [])].filter((i) => !seen.has(i.id) && seen.add(i.id)).sort((a, b) => b.ts.localeCompare(a.ts)).slice(0, 14);
  }, [events, recent.data]);
  const latest = feed[0];
  const current = selected ?? latest;
  const following = !selected;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="flex items-center gap-2"><StationTag code={code} /><span className="text-sm text-muted">Vista en tiempo real</span></div>
          <h1 className="mt-1 font-display text-5xl font-semibold tracking-tight">{STATION_NAME[code]}</h1>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {isAdmin && <SimulatorControl />}
          <Button variant="outline" size="sm" onClick={() => setSelected(following ? current ?? null : null)} disabled={!current}>
            {following ? <><Pause className="size-4" />Congelar</> : <><Play className="size-4" />Volver a en vivo</>}
          </Button>
          <span className="flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1.5 text-sm" aria-live="polite">
            <span className={clsx("size-2 rounded-full", status === "live" ? "bg-ok live-dot" : status === "connecting" ? "bg-accent" : "bg-defect")} aria-hidden />
            {status === "live" ? "En vivo" : status === "connecting" ? "Conectando…" : "Sin conexión"}
          </span>
        </div>
      </div>

      {station && !station.implemented && (
        <p className="rounded-lg border border-line bg-surface px-4 py-3 text-sm text-muted">Esta estación la trabaja otro subgrupo. Aquí se muestran datos simulados para validar el diseño de las tres estaciones.</p>
      )}

      <div className="grid gap-6 xl:grid-cols-[1.7fr_1fr]">
        <div className="space-y-6">
          <Card className="overflow-hidden">
            {recent.isLoading ? <Skeleton className="m-5 h-80" /> : recent.error ? <ErrorState message={(recent.error as Error).message} onRetry={() => recent.refetch()} /> : !current ? (
              <div className="grid h-80 place-items-center text-muted"><Radio className="size-6" aria-hidden /><p>Esperando la primera pieza…</p></div>
            ) : (
              <>
                <div className="relative bg-raised p-3 sm:p-4">
                  <InspectionImage i={current} scan={following} />
                  <div className="absolute left-6 top-6 sm:left-7 sm:top-7 stamp" key={current.id}><VerdictBadge verdict={current.verdict} big /></div>
                </div>
                <div className="grid gap-6 p-5 md:grid-cols-[1fr_1fr]">
                  <dl className="space-y-3">
                    <div><dt className="text-xs text-muted">Tipo de defecto</dt><dd className={clsx("font-display text-3xl font-semibold leading-tight", current.verdict === "OK" ? "text-ok" : "text-defect")}>{current.defect_label ?? "Sin defectos"}</dd></div>
                    <div className="grid grid-cols-2 gap-3 text-sm">
                      <div><dt className="text-xs text-muted">Estación</dt><dd><StationTag code={current.station} withName /></dd></div>
                      <div><dt className="text-xs text-muted">Pieza</dt><dd className="num">{current.serial}</dd></div>
                      <div><dt className="text-xs text-muted">Hora</dt><dd className="num">{fmtDateTime(current.ts)}</dd></div>
                      <div><dt className="text-xs text-muted">Origen</dt><dd><SourceIcon source={current.source} /> <span className="num text-xs text-muted">{current.model}{current.latency_ms ? ` · ${current.latency_ms} ms` : ""}</span></dd></div>
                    </div>
                  </dl>
                  <div className="space-y-5">
                    <div><div className="mb-1 text-xs text-muted">Confianza</div><ConfidenceMeter value={current.confidence} verdict={current.verdict} /></div>
                    <Measurements i={current} />
                    {current.notes && <p className="text-sm text-muted">{current.notes}</p>}
                  </div>
                </div>
              </>
            )}
          </Card>

          {station && (
            <Card className="p-5">
              <SectionTitle>Puntos a evaluar · {station.defects.length}</SectionTitle>
              <ul className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
                {station.defects.map((d) => (
                  <li key={d.code} className="flex items-start justify-between gap-3 border-b border-line pb-3">
                    <div className="min-w-0">
                      <div className="text-sm font-medium">{d.label}{d.stations.length > 1 && <span className="ml-2 rounded bg-raised px-1.5 py-0.5 text-[10px] text-muted">también en {d.stations.filter((s) => s !== code).join(", ")}</span>}</div>
                      {d.task && <div className="text-xs text-muted">{TASK_LABEL[d.task]}</div>}
                    </div>
                    <ViabilityBadge v={d.viability} />
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>

        <div className="space-y-6">
          <Card className="p-5">
            <SectionTitle right={<span className="num text-xs text-muted">{station ? `${station.total_24h} en 24 h` : ""}</span>}>Últimas piezas</SectionTitle>
            {feed.length === 0 ? <p className="py-6 text-center text-sm text-muted">Sin piezas todavía.</p> : (
              <ul className="-mx-2 space-y-1">
                {feed.map((i) => (
                  <li key={i.id} className="row-in">
                    <button onClick={() => setSelected(i)} aria-pressed={current?.id === i.id} className={clsx("flex w-full items-center gap-3 rounded-md px-2 py-2 text-left transition-colors hover:bg-raised", current?.id === i.id && "bg-raised")}>
                      <span className={clsx("h-8 w-1 rounded-full", i.verdict === "OK" ? "bg-ok" : "bg-defect")} aria-hidden />
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm">{i.defect_label ?? "OK · sin defectos"}</div>
                        <div className="num text-xs text-muted">{i.serial} · {fmtTime(i.ts)} · {ago(i.ts)}</div>
                      </div>
                      <span className="num text-sm text-muted">{i.confidence !== null ? `${Math.round(i.confidence * 100)}%` : "—"}</span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          {code === "PC10" && <ManualEntry station={code} />}
        </div>
      </div>
    </div>
  );
}
