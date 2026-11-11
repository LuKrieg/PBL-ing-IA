import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { getToken, type Inspection, type StationCode } from "./api";

export type LiveStatus = "connecting" | "live" | "offline";

/** Subscribes to the SSE stream. Keeps the last `max` events (newest first). */
export function useLive(station?: StationCode, max = 30) {
  const [events, setEvents] = useState<Inspection[]>([]);
  const [status, setStatus] = useState<LiveStatus>("connecting");
  const qc = useQueryClient();
  const qcRef = useRef(qc);
  qcRef.current = qc;

  useEffect(() => {
    const token = getToken();
    if (!token) return;
    setEvents([]);
    setStatus("connecting");
    const url = `/api/stream?token=${encodeURIComponent(token)}${station ? `&station=${station}` : ""}`;
    const es = new EventSource(url);
    es.onopen = () => setStatus("live");
    es.onerror = () => setStatus(es.readyState === EventSource.CLOSED ? "offline" : "connecting");
    es.addEventListener("inspection", (e) => {
      const ev = JSON.parse((e as MessageEvent).data) as Inspection;
      setEvents((prev) => [ev, ...prev.filter((p) => p.id !== ev.id)].slice(0, max));
      qcRef.current.invalidateQueries({ queryKey: ["stations"] });
      qcRef.current.invalidateQueries({ queryKey: ["stats"] });
    });
    return () => es.close();
  }, [station, max]);

  return { events, status };
}
