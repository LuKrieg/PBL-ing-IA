import { useQuery } from "@tanstack/react-query";
import { Link2 } from "lucide-react";
import { StationTag, ViabilityBadge } from "../components/domain";
import { Card, ErrorState, Skeleton } from "../components/ui";
import { api, type DefectDef, type Station, type StationCode } from "../lib/api";
import { STATION_NAME, TASK_LABEL } from "../lib/format";

export default function Catalog() {
  const q = useQuery({ queryKey: ["stations"], queryFn: () => api<Station[]>("/stations") });
  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-5xl font-semibold tracking-tight">Catálogo de defectos</h1>
        <p className="mt-1 max-w-2xl text-muted">Puntos a evaluar por estación. La viabilidad (CV en 2D, CV con captura especial o instrumento) está definida para <strong className="text-ink">PC10 Montaje</strong>; el resto lo completan sus subgrupos.</p>
      </div>
      {q.isLoading && <Skeleton className="h-96" />}
      {q.error && <ErrorState message={(q.error as Error).message} onRetry={() => q.refetch()} />}
      {q.data?.map((s) => (
        <Card key={s.code} className="overflow-hidden">
          <div className="flex items-center justify-between border-b border-line px-5 py-4">
            <div className="flex items-center gap-3"><StationTag code={s.code as StationCode} /><h2 className="font-display text-2xl font-semibold">{STATION_NAME[s.code]}</h2></div>
            <span className="num text-sm text-muted">{s.defects.length} puntos</span>
          </div>
          <ul className="divide-y divide-line">
            {s.defects.map((d: DefectDef) => (
              <li key={d.code} className="grid gap-2 px-5 py-4 md:grid-cols-[1.2fr_1fr_2fr] md:items-start">
                <div>
                  <div className="font-medium">{d.label}</div>
                  <div className="num text-xs text-muted">{d.code}</div>
                  {d.stations.length > 1 && <div className="mt-1 inline-flex items-center gap-1 rounded bg-raised px-1.5 py-0.5 text-[11px] text-muted"><Link2 className="size-3" aria-hidden />Compartido: {d.stations.join(" + ")}</div>}
                </div>
                <div className="space-y-1"><ViabilityBadge v={d.viability} />{d.task && <div className="text-xs text-muted">Tarea: {TASK_LABEL[d.task]}</div>}</div>
                <p className="text-sm text-muted">{d.capture ?? "—"}</p>
              </li>
            ))}
          </ul>
        </Card>
      ))}
    </div>
  );
}
