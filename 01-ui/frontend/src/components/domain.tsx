import clsx from "clsx";
import { CheckCircle2, Gauge, Hand, OctagonAlert, Ruler } from "lucide-react";
import { useState } from "react";
import type { Inspection, StationCode, Viability } from "../lib/api";
import { STATION_COLOR, STATION_NAME, VIABILITY_LABEL } from "../lib/format";

export function StationTag({ code, withName }: { code: StationCode; withName?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded border border-line-strong px-1.5 py-0.5 text-xs">
      <span className="size-1.5 rounded-full" style={{ background: STATION_COLOR[code] }} aria-hidden />
      <span className="num font-medium">{code}</span>
      {withName && <span className="text-muted">{STATION_NAME[code]}</span>}
    </span>
  );
}

export function VerdictBadge({ verdict, big }: { verdict: "OK" | "DEFECT"; big?: boolean }) {
  const ok = verdict === "OK";
  const Icon = ok ? CheckCircle2 : OctagonAlert;
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-md font-display font-semibold uppercase tracking-wider",
        big ? "px-4 py-2 text-3xl" : "px-2 py-0.5 text-sm",
        ok ? "bg-ok/15 text-ok" : "bg-defect/15 text-defect",
      )}
    >
      <Icon className={big ? "size-7" : "size-4"} aria-hidden />
      {ok ? "OK" : "Defecto"}
    </span>
  );
}

export function SourceIcon({ source }: { source: "cv" | "manual" }) {
  return source === "manual" ? (
    <span title="Registro manual (instrumento)" className="inline-flex items-center gap-1 text-xs text-muted"><Hand className="size-3.5" aria-hidden />Manual</span>
  ) : (
    <span title="Inferencia automática" className="inline-flex items-center gap-1 text-xs text-muted"><Gauge className="size-3.5" aria-hidden />CV</span>
  );
}

export function ConfidenceMeter({ value, verdict }: { value: number | null; verdict: "OK" | "DEFECT" }) {
  if (value === null) return <span className="text-sm text-muted">No aplica (medición manual)</span>;
  const color = verdict === "OK" ? "var(--ok)" : "var(--defect)";
  const low = value < 0.7;
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <span className="num text-3xl font-medium">{(value * 100).toFixed(1)}<span className="text-lg text-muted">%</span></span>
        {low && <span className="text-xs text-accent">Confianza baja · revisar</span>}
      </div>
      <div className="mt-2 h-2 rounded-full bg-raised overflow-hidden" role="meter" aria-valuenow={Math.round(value * 100)} aria-valuemin={0} aria-valuemax={100} aria-label="Confianza">
        <div className="h-full rounded-full transition-[width] duration-500" style={{ width: `${value * 100}%`, background: color }} />
      </div>
    </div>
  );
}

export function ViabilityBadge({ v }: { v: Viability }) {
  if (!v) return <span className="text-xs text-muted">Pendiente (otro subgrupo)</span>;
  const cls = v === "cv_2d" ? "text-ok border-ok/40 bg-ok/10" : v === "special_capture" ? "text-info border-info/40 bg-info/10" : "text-accent border-accent/40 bg-accent/10";
  return <span className={clsx("inline-block rounded border px-2 py-0.5 text-xs font-medium", cls)}>{VIABILITY_LABEL[v]}</span>;
}

/** Image with the detection box drawn in the image's own pixel space (exact, resolution independent). */
export function InspectionImage({ i, scan, className, rounded = true }: { i: Inspection; scan?: boolean; className?: string; rounded?: boolean }) {
  const [failed, setFailed] = useState(false);
  const w = i.image_w ?? 1500, h = i.image_h ?? 540;
  const defect = i.verdict === "DEFECT";
  return (
    <div className={clsx("relative overflow-hidden bg-raised", rounded && "rounded-lg", className)} style={{ aspectRatio: `${w} / ${h}` }}>
      {i.image_url && !failed ? (
        <img src={i.image_url} alt={`Machete ${i.serial}`} width={w} height={h} loading={scan === undefined ? "lazy" : "eager"} decoding="async" className="absolute inset-0 size-full object-contain" onError={() => setFailed(true)} draggable={false} />
      ) : (
        <div className="absolute inset-0 grid place-items-center text-xs text-muted">{i.source === "manual" ? "Registro por instrumento · sin imagen" : "Sin imagen representativa (simulado)"}</div>
      )}
      {defect && i.bbox && (
        <svg className="absolute inset-0 size-full" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="xMidYMid meet" aria-hidden>
          <rect x={i.bbox[0]} y={i.bbox[1]} width={i.bbox[2] - i.bbox[0]} height={i.bbox[3] - i.bbox[1]} fill="rgba(255,93,93,0.12)" stroke="#ff5d5d" strokeWidth={Math.max(2, w / 450)} rx={4} />
        </svg>
      )}
      {scan && <div className="scanline" key={i.id} aria-hidden />}
    </div>
  );
}

/** Measured value against nominal ± tolerance. */
export function MeasurementGauge({ label, value, nominal, tol, unit = "mm" }: { label: string; value: number; nominal: number; tol: number; unit?: string }) {
  const span = tol * 4;
  const lo = nominal - span, hi = nominal + span;
  const pos = Math.min(100, Math.max(0, ((value - lo) / (hi - lo)) * 100));
  const bandL = ((nominal - tol - lo) / (hi - lo)) * 100;
  const bandW = ((2 * tol) / (hi - lo)) * 100;
  const out = Math.abs(value - nominal) > tol;
  const delta = value - nominal;
  return (
    <div>
      <div className="flex items-baseline justify-between text-sm">
        <span className="flex items-center gap-1.5 text-muted"><Ruler className="size-3.5" aria-hidden />{label}</span>
        <span className={clsx("num font-medium", out ? "text-defect" : "text-ok")}>{value.toFixed(1)} {unit} <span className="text-muted">({delta >= 0 ? "+" : ""}{delta.toFixed(1)})</span></span>
      </div>
      <div className="relative mt-2 h-2.5 rounded-full bg-raised">
        <div className="absolute top-0 h-full rounded-full bg-ok/30" style={{ left: `${bandL}%`, width: `${bandW}%` }} />
        <div className="absolute -top-1 h-4.5 w-1 rounded-full" style={{ left: `calc(${pos}% - 2px)`, background: out ? "var(--defect)" : "var(--ok)", height: "18px" }} />
      </div>
      <div className="num mt-1 flex justify-between text-[11px] text-muted">
        <span>{(nominal - tol).toFixed(1)}</span><span>nominal {nominal.toFixed(1)} ± {tol}</span><span>{(nominal + tol).toFixed(1)}</span>
      </div>
    </div>
  );
}

export function Measurements({ i }: { i: Inspection }) {
  const m = i.measurement;
  if (!m) return null;
  return (
    <div className="space-y-4">
      {m.length_mm !== undefined && <MeasurementGauge label="Largo total" value={m.length_mm} nominal={m.nominal_length_mm} tol={m.tol_length_mm} />}
      {m.width_mm !== undefined && <MeasurementGauge label="Ancho de hoja" value={m.width_mm} nominal={m.nominal_width_mm} tol={m.tol_width_mm} />}
      {m.thickness_mm !== undefined && <MeasurementGauge label="Espesor (calibrador)" value={m.thickness_mm} nominal={m.nominal_mm} tol={m.tol_mm} />}
    </div>
  );
}
