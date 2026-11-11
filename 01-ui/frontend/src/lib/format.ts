import type { StationCode, Viability } from "./api";

const dtf = new Intl.DateTimeFormat("es-SV", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
const tf = new Intl.DateTimeFormat("es-SV", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
const df = new Intl.DateTimeFormat("es-SV", { day: "2-digit", month: "short" });

export const fmtDateTime = (iso: string) => dtf.format(new Date(iso));
export const fmtTime = (iso: string) => tf.format(new Date(iso));
export const fmtDay = (iso: string) => df.format(new Date(iso + "T12:00:00"));
export const pct = (n: number, d = 1) => `${(n * 100).toFixed(d)}%`;

export function ago(iso: string): string {
  const s = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 60) return `hace ${s}s`;
  if (s < 3600) return `hace ${Math.floor(s / 60)} min`;
  if (s < 86400) return `hace ${Math.floor(s / 3600)} h`;
  return `hace ${Math.floor(s / 86400)} d`;
}

export const STATION_NAME: Record<StationCode, string> = { PC08: "Enderezado", PC10: "Montaje", PC12: "Inyectado" };
export const STATION_COLOR: Record<StationCode, string> = { PC08: "var(--info)", PC10: "var(--accent)", PC12: "var(--violet)" };

export const VIABILITY_LABEL: Record<Exclude<Viability, null>, string> = {
  cv_2d: "CV en foto 2D",
  special_capture: "CV + captura especial",
  instrument: "Instrumento",
};
export const TASK_LABEL: Record<string, string> = {
  classification: "Clasificación",
  detection: "Detección",
  segmentation: "Segmentación",
  anomaly: "Detección de anomalías",
  measurement: "Medición",
};
export const dateInput = (d: Date) => d.toISOString().slice(0, 10);
