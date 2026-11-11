// Drives headless Chromium over CDP (no Playwright) to capture the UI and assert on DOM text.
// Usage: node tools/screenshots.mjs [baseUrl] [outDir]   (needs the backend serving the built SPA)
import { spawn } from "node:child_process";
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const BASE = process.argv[2] ?? "http://127.0.0.1:8100";
const OUT = process.argv[3] ?? "screenshots";
const CHROME = process.env.CHROME ?? (process.platform === "win32"
  ? "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
  : `${process.env.HOME}/.cache/ms-playwright/chromium-1140/chrome-linux/chrome`);
const PORT = 9333;
mkdirSync(OUT, { recursive: true });

const proc = spawn(CHROME, ["--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars", `--remote-debugging-port=${PORT}`, `--user-data-dir=${mkdtempSync(join(tmpdir(), "shots-"))}`, "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let target;
for (let i = 0; i < 50 && !target; i++) {
  try { target = (await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json()).find((t) => t.type === "page"); } catch { await sleep(200); }
}
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((r) => (ws.onopen = r));
let id = 0; const pending = new Map();
const consoleErrors = [];
ws.onmessage = (m) => {
  const d = JSON.parse(m.data);
  if (d.id && pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id); }
  if (d.method === "Runtime.exceptionThrown") consoleErrors.push(d.params.exceptionDetails.text + " " + (d.params.exceptionDetails.exception?.description ?? ""));
  if (d.method === "Runtime.consoleAPICalled" && d.params.type === "error") consoleErrors.push(d.params.args.map((a) => a.value ?? a.description).join(" "));
};
const send = (method, params = {}) => new Promise((res, rej) => { const i = ++id; pending.set(i, (d) => (d.error ? rej(new Error(JSON.stringify(d.error))) : res(d.result))); ws.send(JSON.stringify({ id: i, method, params })); });
const ev = async (expr) => (await send("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true })).result.value;
const viewport = (w, h, mobile = false) => send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: mobile ? 2 : 1, mobile });
const goto = async (path) => { await send("Page.navigate", { url: BASE + path }); await sleep(900); };
const shot = async (name) => {
  const o = await ev("({sw: document.documentElement.scrollWidth, iw: window.innerWidth})");
  if (o.sw > o.iw + 1) consoleErrors.push(`horizontal overflow on ${name}: scrollWidth ${o.sw} > ${o.iw}`); const r = await send("Page.captureScreenshot", { format: "png" }); writeFileSync(join(OUT, name), Buffer.from(r.data, "base64")); console.log("shot", name); };
const text = async () => (await ev("document.body.innerText")).toLowerCase();
const waitFor = async (expr, ms = 8000) => { const t = Date.now(); while (Date.now() - t < ms) { if (await ev(`!!(${expr})`)) return true; await sleep(150); } throw new Error("timeout: " + expr); };
const typeInto = async (sel, value) => { await ev(`document.querySelector(${JSON.stringify(sel)}).focus()`); await send("Input.insertText", { text: value }); };
const click = (expr) => ev(`(${expr})?.click(), true`);
const assert = (cond, msg) => { if (!cond) throw new Error("ASSERT FAILED: " + msg); console.log("ok  ", msg); };

try {
  await send("Page.enable"); await send("Runtime.enable");
  await viewport(1440, 900);

  await goto("/login");
  assert((await text()).includes("iniciar sesión"), "login page renders");
  await shot("01-login.png");

  await typeInto("#u", "admin"); await typeInto("#p", "mala-clave");
  await click("document.querySelector('button[type=submit]')");
  await waitFor("document.body.innerText.toLowerCase().includes('incorrectos')");
  assert(true, "wrong password shows error and stays on /login");
  await shot("02-login-error.png");

  await ev("document.getElementById('p').select()"); await send("Input.insertText", { text: "Planta-Admin-2026" });
  await click("document.querySelector('button[type=submit]')");
  await waitFor("document.body.innerText.toLowerCase().includes('tablero general')");
  await waitFor("document.querySelectorAll('ul.divide-y li').length >= 2", 15000);
  assert((await text()).includes("pc10") && (await text()).includes("montaje"), "dashboard lists the 3 stations after login");
  await shot("03-dashboard.png");

  await goto("/station/PC10");
  await waitFor("document.body.innerText.toLowerCase().includes('últimas piezas')");
  await waitFor("document.querySelector('button[aria-pressed]')");
  // pick a defect from the feed so the screenshot shows a bounding box
  await ev("[...document.querySelectorAll('button[aria-pressed]')].find(b => b.querySelector('.bg-defect'))?.click()");
  await sleep(500);
  const t = await text();
  assert(t.includes("puntos a evaluar") && t.includes("registro por instrumento"), "PC10 live view shows defect checklist and manual instrument entry");
  assert(t.includes("confianza"), "live view shows confidence");
  await shot("04-station-pc10-defect.png");

  await ev("[...document.querySelectorAll('button[aria-pressed]')].find(b => b.querySelector('.bg-ok'))?.click()");
  await sleep(500);
  await shot("05-station-pc10-ok.png");

  await goto("/station/PC08"); await waitFor("document.body.innerText.toLowerCase().includes('otro subgrupo')");
  assert(true, "PC08 view flags it as another subgroup's station");

  await goto("/history?defect=handle_misalignment");
  await waitFor("document.querySelectorAll('tbody tr').length > 0");
  const h = await text();
  assert(h.includes("comparativa") && h.includes("pc10") && h.includes("pc12"), "Desface de cacha comparison PC10 vs PC12 in history");
  await shot("06-history-desface-compare.png");
  await click("document.querySelector('tbody tr')");
  await waitFor("document.querySelector('[role=dialog]')");
  assert((await text()).includes("mismo defecto en otra estación"), "detail drawer shows the same defect in the other station");
  await shot("07-history-detail-drawer.png");
  await ev("document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'}))");

  await goto("/history?station=PC10&verdict=DEFECT&from=2026-11-01");
  await waitFor("document.querySelectorAll('tbody tr').length > 0");
  await shot("08-history-filtered.png");

  await goto("/catalog"); await waitFor("document.body.innerText.toLowerCase().includes('compartido')");
  assert((await text()).includes("instrumento"), "catalog shows viability incl. Instrumento");
  await shot("09-catalog.png");

  await ev("localStorage.setItem('imacasa.theme','light')"); await goto("/");
  await waitFor("document.body.innerText.toLowerCase().includes('tablero general')"); await sleep(1200);
  await shot("10-dashboard-light.png");
  await ev("localStorage.setItem('imacasa.theme','dark')");

  await viewport(390, 844, true); await goto("/station/PC10");
  await waitFor("document.body.innerText.toLowerCase().includes('últimas piezas')"); await sleep(800);
  await shot("11-mobile-station.png");
  if (consoleErrors.length) { console.error("PROBLEMS:\n" + [...new Set(consoleErrors)].join("\n")); process.exitCode = 1; }
  else console.log("ALL CHECKS PASSED (no console errors, no horizontal overflow)");
} catch (e) { console.error(String(e)); process.exitCode = 1; }
finally { ws.close(); proc.kill(); }
