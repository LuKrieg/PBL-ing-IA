export type StationCode = "PC08" | "PC10" | "PC12";
export type Verdict = "OK" | "DEFECT";
export type Viability = "cv_2d" | "special_capture" | "instrument" | null;

export interface Inspection {
  id: number;
  station: StationCode;
  ts: string;
  serial: string;
  verdict: Verdict;
  defect_code: string | null;
  defect_label: string | null;
  confidence: number | null;
  bbox: number[] | null;
  image_url: string | null;
  image_w: number | null;
  image_h: number | null;
  source: "cv" | "manual";
  model: string;
  latency_ms: number | null;
  measurement: Record<string, number> | null;
  notes: string | null;
}
export interface DefectDef {
  code: string;
  label: string;
  stations: StationCode[];
  viability: Viability;
  task: string | null;
  capture: string | null;
}
export interface Station {
  code: StationCode;
  name: string;
  name_en: string;
  implemented: boolean;
  defects: DefectDef[];
  total_24h: number;
  defects_24h: number;
  defect_rate_24h: number;
  last: Inspection | null;
}
export interface User {
  id: number;
  username: string;
  name: string;
  role: "admin" | "operator";
}
export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}
export interface Stats {
  total: number;
  defects: number;
  defect_rate: number;
  by_defect: { code: string; label: string; count: number }[];
  series: { day: string; station: StationCode; total: number; defects: number }[];
}

const KEY = "imacasa.token";
export const getToken = () => localStorage.getItem(KEY);
export const setToken = (t: string | null) => (t ? localStorage.setItem(KEY, t) : localStorage.removeItem(KEY));

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}
let onUnauthorized: () => void = () => {};
export const setUnauthorizedHandler = (fn: () => void) => (onUnauthorized = fn);

export async function api<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const t = getToken();
  if (t) headers.set("Authorization", `Bearer ${t}`);
  if (init.json !== undefined) {
    headers.set("Content-Type", "application/json");
    init.body = JSON.stringify(init.json);
  }
  const res = await fetch(`/api${path}`, { ...init, headers });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const b = await res.json();
      msg = typeof b.detail === "string" ? b.detail : JSON.stringify(b.detail ?? b);
    } catch {
      /* ignore */
    }
    if (res.status === 401 && !path.startsWith("/auth/login")) onUnauthorized();
    throw new ApiError(res.status, msg);
  }
  return res.json() as Promise<T>;
}

export const qs = (o: Record<string, string | number | undefined | null>) => {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(o)) if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  const s = p.toString();
  return s ? `?${s}` : "";
};
