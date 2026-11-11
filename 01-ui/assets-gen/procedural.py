"""Procedural SIMULATED defects for PC08 (Enderezado) and PC12 (Inyectado) demo images.

These stations belong to other subgroups; the images only exist so the UI can show all three stations.
"""

from __future__ import annotations

import argparse
import json
import zlib
from pathlib import Path

import cv2
import numpy as np
from scipy import ndimage as ndi

import common as c

H = W = 1500


def noise(rng, shape, sigma):
    n = ndi.gaussian_filter(rng.normal(size=shape).astype(np.float32), sigma)
    n -= n.min()
    return n / (n.max() + 1e-6)


def blade_mask(layer):
    m = layer.a > 0.5
    m[:, c.JUNCTION_X :] = False
    return m


def handle_mask(layer):
    m = layer.a > 0.5
    m[:, : c.JUNCTION_X] = False
    return m


def col_edges(mask, x):
    ys = np.where(mask[:, x])[0]
    return (int(ys.min()), int(ys.max())) if len(ys) else (None, None)


def region_mask(shape, x0, y0, x1, y1):
    m = np.zeros(shape[:2], np.float32)
    m[max(y0, 0) : y1, max(x0, 0) : x1] = 1
    return m


def blend(p, rgb_new, weight):
    """Blend new color into premultiplied layer, keeping alpha. weight (H,W) in [0,1]."""
    a = p[..., 3:4]
    out = p.copy()
    w = (weight * (a[..., 0] > 0.5))[..., None]
    out[..., :3] = p[..., :3] * (1 - w) + rgb_new * a * w
    return out


# ------------------------------------------------------------------ PC08
def op_bent_blade(layer, rng):
    amp = rng.uniform(14, 34) * rng.choice([-1, 1])
    xs = np.arange(W, dtype=np.float32)
    dy = amp * np.clip((xs - c.TIP_X) / (c.END_X - c.TIP_X), 0, 1) ** 2
    mx, my = np.meshgrid(xs, np.arange(H, dtype=np.float32))
    p = cv2.remap(layer.p, mx.astype(np.float32), (my - dy[None, :]).astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    return p, {"defect": (p[..., 3] > 0.5).astype(np.float32)}, {"deflection_mm": round(abs(amp) / c.PX_PER_MM, 1)}


def op_spine_waviness(layer, rng):
    bm = blade_mask(layer)
    amp, lam, ph = rng.uniform(5, 10), rng.uniform(140, 240), rng.uniform(0, 6.28)
    top = np.full(W, np.nan, np.float32)
    for x in range(200, c.JUNCTION_X - 20):
        t, _ = col_edges(bm, x)
        if t is not None:
            top[x] = t
    yy = np.arange(H, dtype=np.float32)[:, None]
    xs = np.arange(W, dtype=np.float32)[None, :]
    topx = np.nan_to_num(top, nan=0)[None, :]
    env = np.exp(-np.maximum(0, yy - topx) / 22.0) * (topx > 0) * np.clip((yy - (topx - 25)) / 12, 0, 1)
    ramp = np.clip((xs - 200) / 120, 0, 1) * np.clip((c.JUNCTION_X - 20 - xs) / 80, 0, 1)
    dy = amp * np.sin(2 * np.pi * xs / lam + ph) * env * ramp
    p = cv2.remap(layer.p, np.repeat(xs, H, axis=0), np.repeat(yy, W, axis=1) - dy, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    ym = int(np.nanmedian(top[320 : c.JUNCTION_X - 20]))
    return p, {"defect": region_mask(p.shape, 300, ym - 26, c.JUNCTION_X - 15, ym + 34)}, {"amplitude_mm": round(amp / c.PX_PER_MM, 1)}


def op_dents(layer, rng):
    bm = blade_mask(layer)
    n = int(rng.integers(1, 3))
    p = layer.p.copy()
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    boxes = np.zeros((H, W), np.float32)
    for _ in range(n):
        cx = int(rng.integers(260, 960))
        t, b = col_edges(bm, cx)
        cy, R = (t + b) / 2 + rng.uniform(-10, 10), rng.uniform(26, 42)
        d2 = (xx - cx) ** 2 + (yy - cy) ** 2
        f = np.exp(-d2 / (2 * (R / 1.6) ** 2))
        k = 1 + 0.35 * f
        p = cv2.remap(p, cx + (xx - cx) * k, cy + (yy - cy) * k, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        shade = 1 - 0.30 * f + 0.22 * np.exp(-((xx - cx + R * 0.5) ** 2 + (yy - cy + R * 0.5) ** 2) / (2 * (R / 2.2) ** 2))
        p[..., :3] *= shade[..., None]
        boxes[int(cy - R * 1.4) : int(cy + R * 1.4), int(cx - R * 1.4) : int(cx + R * 1.4)] = 1
    return p, {"defect": boxes}, {"count": n}


def op_blistered_blade(layer, rng):
    bm = blade_mask(layer)
    cx, cw, ch = int(rng.integers(380, 880)), rng.uniform(110, 190), rng.uniform(34, 56)
    t, b = col_edges(bm, cx)
    cy = (t + b) / 2
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    ell = np.clip(1 - (((xx - cx) / cw) ** 2 + ((yy - cy) / ch) ** 2), 0, 1)
    n = noise(rng, (H, W), 7)
    heat = np.clip(ell * 1.6 * (0.55 + n), 0, 1)
    straw, brown, blue = np.array([205, 172, 96]), np.array([135, 88, 52]), np.array([72, 92, 150])
    col = np.where((n > 0.62)[..., None], blue, np.where((n > 0.45)[..., None], brown, straw)).astype(np.float32)
    lum = layer.p[..., :3].mean(axis=2, keepdims=True) / 150.0
    p = blend(layer.p, col * np.clip(lum, 0.6, 1.2), np.clip(heat * 0.85, 0, 0.85))
    return p, {"defect": region_mask(p.shape, int(cx - cw), int(cy - ch - 6), int(cx + cw), int(cy + ch + 6))}, {}


def op_poor_polish(layer, rng):
    x0, x1 = int(rng.integers(320, 520)), int(rng.integers(760, 980))
    bm = blade_mask(layer)
    t, b = col_edges(bm, (x0 + x1) // 2)
    n = noise(rng, (H, W), (0.7, 28))
    n2 = noise(rng, (H, W), (0.5, 9))
    streak = (n - 0.5) * 2.2 + (n2 - 0.5) * 1.4
    reg = region_mask((H, W), x0, t, x1, b)
    reg = ndi.gaussian_filter(reg, 10)
    p = layer.p.copy()
    p[..., :3] *= (1 + 0.45 * streak * reg)[..., None]
    return p, {"defect": region_mask(p.shape, x0, t - 4, x1, b + 4)}, {"note": "Hoja: pulido irregular"}


def op_pores(layer, rng):
    bm = blade_mask(layer)
    cx = int(rng.integers(300, 900))
    t, b = col_edges(bm, cx)
    cy = (t + b) // 2 + int(rng.integers(-18, 18))
    p = layer.p.copy()
    k = int(rng.integers(22, 40))
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    for _ in range(k):
        px, py, r = cx + rng.normal(0, 28), cy + rng.normal(0, 14), rng.uniform(1.6, 3.6)
        f = np.exp(-((xx - px) ** 2 + (yy - py) ** 2) / (2 * (r / 1.4) ** 2))
        p[..., :3] *= (1 - 0.7 * f)[..., None]
    return p, {"defect": region_mask(p.shape, cx - 90, cy - 45, cx + 90, cy + 45)}, {"pores": k}


def op_fingerprints(layer, rng):
    bm = blade_mask(layer)
    cx = int(rng.integers(320, 900))
    t, b = col_edges(bm, cx)
    cy = (t + b) // 2 + int(rng.integers(-10, 10))
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    ang = rng.uniform(-0.5, 0.5)
    dx, dy = xx - cx, yy - cy
    u, v = dx * np.cos(ang) + dy * np.sin(ang), -dx * np.sin(ang) + dy * np.cos(ang)
    r = np.sqrt((u / 34) ** 2 + (v / 48) ** 2)
    env = np.clip(1.15 - r, 0, 1)
    ridges = 0.5 + 0.5 * np.sin(r * 38 + 2.2 * np.sin(u / 11))
    p = layer.p.copy()
    p[..., :3] *= (1 + 0.20 * env * (ridges - 0.45))[..., None]
    return p, {"defect": region_mask(p.shape, cx - 48, cy - 62, cx + 48, cy + 62)}, {}


def op_chipping(layer, rng):
    bm = blade_mask(layer)
    p = layer.p.copy()
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    reg = np.zeros((H, W), np.float32)
    xs = sorted(rng.integers(360, 980, size=int(rng.integers(3, 6))))
    for cx in xs:
        _, b = col_edges(bm, int(cx))
        r = rng.uniform(12, 20)
        cut = np.clip(1 - np.sqrt((xx - cx) ** 2 + (yy - (b - 1)) ** 2) / r, 0, 1)
        p *= (1 - np.clip(cut * 3, 0, 1))[..., None]
        reg[int(b - 3 * r) : int(b + r + 4), int(cx - 2 * r) : int(cx + 2 * r)] = 1
    return p, {"defect": reg}, {"chips": len(xs)}


# ------------------------------------------------------------------ PC12
def op_bad_injection(layer, rng):
    hm = handle_mask(layer)
    n = noise(rng, (H, W), 40)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    period = rng.uniform(9, 16)
    flow = np.sin(2 * np.pi * (yy + 40 * (n - 0.5) + 0.04 * xx) / period)
    p = layer.p.copy()
    gain = 1 + 0.16 * flow
    tint = np.array([1.03, 1.0, 0.86]) if rng.random() < 0.5 else np.array([0.93, 0.96, 1.05])
    wmask = ndi.gaussian_filter(hm.astype(np.float32), 2)
    p[..., :3] = p[..., :3] * (1 + (gain[..., None] * tint - 1) * wmask[..., None])
    for _ in range(int(rng.integers(14, 28))):  # moisture specks: short silvery dashes
        ys, xs_ = np.where(hm)
        k = int(rng.integers(len(ys)))
        x, y = int(xs_[k]), int(ys[k])
        cv2.line(p, (x, y), (x + int(rng.integers(3, 9)), y + int(rng.integers(-2, 3))), (235, 235, 235, 0), 1, cv2.LINE_AA)
    ys, xs_ = np.where(hm)
    return p, {"defect": region_mask(p.shape, int(xs_.min()) - 6, int(ys.min()) - 6, int(xs_.max()) + 6, int(ys.max()) + 6)}, {}


def op_blocked_skirt(layer, rng):
    bm = blade_mask(layer)
    p = layer.p.copy()
    x0 = c.JUNCTION_X - int(rng.integers(34, 70))
    t, b = col_edges(bm, x0 - 5)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    edge = noise(rng, (H, W), 5) * 10
    side_top = rng.random() < 0.5
    blob = (xx > x0 + edge) & (xx < c.JUNCTION_X + 3)
    blob &= (yy < (t + 0.62 * (b - t))) if side_top else (yy > (t + 0.38 * (b - t)))
    blob &= bm
    blob_f = ndi.gaussian_filter(blob.astype(np.float32), 1.2)
    col = np.array([196, 160, 112], np.float32)  # injected material flash covering the skirt slot
    shade = 0.85 + 0.25 * noise(rng, (H, W), 3)
    p = blend(p, col * shade[..., None], blob_f)
    ys, xs_ = np.where(blob)
    return p, {"defect": region_mask(p.shape, int(xs_.min()) - 10, int(ys.min()) - 10, c.JUNCTION_X + 12, int(ys.max()) + 10)}, {}


def op_blade_rust(layer, rng):
    bm = blade_mask(layer)
    x0 = int(rng.integers(300, 700))
    x1 = x0 + int(rng.integers(160, 320))
    n = noise(rng, (H, W), 11)
    n2 = noise(rng, (H, W), 3)
    reg = ndi.gaussian_filter(region_mask((H, W), x0, 0, x1, H), 25)
    spots = np.clip((n - 0.58) * 6, 0, 1) * reg
    spots = np.clip(spots * (0.6 + n2), 0, 1)
    rust = np.where((n2 > 0.55)[..., None], np.array([178, 96, 42]), np.array([128, 62, 26])).astype(np.float32)
    p = blend(layer.p, rust, np.clip(spots * 0.9, 0, 0.9))
    ys, xs_ = np.where((spots > 0.25) & bm)
    if len(xs_) == 0:
        return op_blade_rust(layer, rng)
    return p, {"defect": region_mask(p.shape, int(xs_.min()) - 8, int(ys.min()) - 8, int(xs_.max()) + 8, int(ys.max()) + 8)}, {}


def op_poor_deburring(layer, rng):
    hm = handle_mask(layer)
    p = layer.p.copy()
    k = int(rng.integers(8, 15))
    ymin, ymax = H, 0
    xmin, xmax = W, 0
    for _ in range(k):
        x = int(rng.integers(c.JUNCTION_X + 20, c.END_X - 60))
        t, b = col_edges(hm, x)
        top = rng.random() < 0.5
        y = t if top else b
        ang = rng.uniform(-0.5, 0.5)
        ln = rng.uniform(9, 24)
        x2, y2 = int(x + ln * np.sin(ang) * 2), int(y + (-1 if top else 1) * ln * np.cos(ang))
        cv2.line(p, (x, y), (x2, y2), (205 * 1.0, 175 * 1.0, 128 * 1.0, 1.0), int(rng.integers(2, 4)), cv2.LINE_AA)
        xmin, xmax, ymin, ymax = min(xmin, x, x2), max(xmax, x, x2), min(ymin, y, y2), max(ymax, y, y2)
    return p, {"defect": region_mask(p.shape, xmin - 12, ymin - 12, xmax + 12, ymax + 12)}, {"burrs": k}


# ------------------------------------------------------------------ PC10 blade damage (poor_finish on the cuchilla)
def _bbox_of(mask, pad=14):
    ys, xs = np.where(mask)
    return region_mask((H, W), int(xs.min()) - pad, int(ys.min()) - pad, int(xs.max()) + pad, int(ys.max()) + pad)


def op_blade_scratches(layer, rng):
    bm = blade_mask(layer)
    dark, bright = np.zeros((H, W), np.float32), np.zeros((H, W), np.float32)
    x0 = int(rng.integers(330, 640))
    for k in range(int(rng.integers(6, 11))):
        x = x0 + int(rng.integers(0, 260))
        t, b = col_edges(bm, x)
        y = int(rng.uniform(t + 6, b - 6))
        ang = rng.normal(0.0, 0.22)
        ln = rng.uniform(90, 260)
        tgt = dark if k % 3 else bright
        cv2.line(tgt, (x, y), (int(x + ln * np.cos(ang)), int(y + ln * np.sin(ang))), 1.0, int(rng.integers(1, 3)), cv2.LINE_AA)
    dark, bright = ndi.gaussian_filter(dark, 0.7) * bm, ndi.gaussian_filter(bright, 0.7) * bm
    p = layer.p.copy()
    p[..., :3] *= (1 - 0.55 * dark + 0.45 * bright)[..., None]
    return p, {"defect": _bbox_of((dark + bright) > 0.15)}, {"note": "Hoja: rayaduras profundas"}


def op_blade_edge_nicks(layer, rng):
    p, masks, _ = op_chipping(layer, rng)
    bm = blade_mask(layer)
    box = masks["defect"] > 0
    for _ in range(int(rng.integers(5, 10))):  # burrs: thin steel slivers along the cutting edge
        ys, xs = np.where(box)
        x = int(rng.integers(xs.min() + 10, xs.max() - 10))
        _, b = col_edges(bm, x)
        cv2.line(p, (x, b), (x + int(rng.integers(-5, 6)), b + int(rng.integers(7, 16))), (172, 172, 176, 1.0), 2, cv2.LINE_AA)
    return p, masks, {"note": "Hoja: filo con mellas y rebabas"}


def op_blade_pitting(layer, rng):
    bm = blade_mask(layer)
    cx = int(rng.integers(320, 900))
    t, b = col_edges(bm, cx)
    cy = (t + b) // 2 + int(rng.integers(-14, 14))
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    wmap = np.zeros((H, W), np.float32)
    for _ in range(int(rng.integers(18, 34))):
        px, py, r = cx + rng.normal(0, 34), cy + rng.normal(0, 16), rng.uniform(2.2, 5.0)
        wmap = np.maximum(wmap, np.exp(-((xx - px) ** 2 + (yy - py) ** 2) / (2 * (r / 1.3) ** 2)))
    rust = np.array([150, 78, 34], np.float32)
    p = blend(layer.p, rust, np.clip(wmap * 0.9, 0, 0.9))
    p[..., :3] *= (1 - 0.25 * wmap)[..., None]
    return p, {"defect": _bbox_of(wmap > 0.3, 12)}, {"note": "Hoja: picaduras y oxidación"}


def op_blade_gouge(layer, rng):
    bm = blade_mask(layer)
    x = int(rng.integers(340, 880))
    t, b = col_edges(bm, x)
    y = int((t + b) / 2 + rng.uniform(-14, 14))
    dark, bright = np.zeros((H, W), np.float32), np.zeros((H, W), np.float32)
    ln, ang = rng.uniform(50, 110), rng.uniform(-0.5, 0.5)
    p1, p2 = (x, y), (int(x + ln * np.cos(ang)), int(y + ln * np.sin(ang)))
    cv2.line(dark, p1, p2, 1.0, int(rng.integers(4, 7)), cv2.LINE_AA)
    cv2.line(bright, (p1[0], p1[1] - 4), (p2[0], p2[1] - 4), 1.0, 2, cv2.LINE_AA)
    dark, bright = ndi.gaussian_filter(dark, 1.3) * bm, ndi.gaussian_filter(bright, 1.1) * bm
    p = layer.p.copy()
    p[..., :3] *= (1 - 0.6 * dark + 0.5 * bright)[..., None]
    return p, {"defect": _bbox_of((dark + bright) > 0.12, 18)}, {"note": "Hoja: golpe / raspón"}


BLADE_FINISH = {"scratches": op_blade_scratches, "nicks": op_blade_edge_nicks, "pitting": op_blade_pitting, "gouge": op_blade_gouge}


OPS = {
    "PC08": {"bent_blade": op_bent_blade, "spine_waviness": op_spine_waviness, "dents": op_dents,
             "blistered_blade": op_blistered_blade, "poor_polish": op_poor_polish, "pores": op_pores,
             "fingerprints": op_fingerprints, "chipping": op_chipping},
    "PC12": {"bad_injection": op_bad_injection, "blocked_skirt": op_blocked_skirt, "blade_rust": op_blade_rust,
             "poor_deburring": op_poor_deburring},
}
PER_CLASS = 6


def build(out: Path, seed: int) -> list[dict]:
    layer = c.load_layer()
    rows = []
    for station, ops in OPS.items():
        for cls, fn in ops.items():
            (out / station / cls).mkdir(parents=True, exist_ok=True)
            for i in range(PER_CLASS):
                rng = np.random.default_rng([seed, zlib.crc32(f"{station}{cls}".encode()) % 100_000, i])
                p, masks, truth = fn(layer, rng)
                img, boxes = c.compose(p, rng, masks)
                name = f"{station}/{cls}/{cls}-{i:02d}.jpg"
                cv2.imwrite(str(out / name), img, [cv2.IMWRITE_JPEG_QUALITY, 90])
                rows.append({"file": name, "station": station, "defect": cls, "bbox": boxes.get("defect"), "truth": truth,
                             "method": "procedural", "simulated": True})
    return rows


def sheet(out: Path, rows, station, cols=4, tw=480):
    sel = [r for r in rows if r["station"] == station]
    sel = [r for k, r in enumerate(sel) if k % PER_CLASS in (0, 1)]
    th = int(tw * c.CANVAS_H / c.CANVAS_W)
    s = np.full((((len(sel) + cols - 1) // cols) * th, cols * tw, 3), 255, np.uint8)
    for k, r in enumerate(sel):
        im = cv2.imread(str(out / r["file"]))
        if r["bbox"]:
            x0, y0, x1, y1 = r["bbox"]
            cv2.rectangle(im, (x0, y0), (x1, y1), (0, 140, 255), 3)
        cv2.putText(im, r["defect"], (30, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.6, (0, 0, 200), 3)
        s[(k // cols) * th : (k // cols + 1) * th, (k % cols) * tw : (k % cols + 1) * tw] = cv2.resize(im, (tw, th), interpolation=cv2.INTER_AREA)
    p = out / f"sheet-{station}.jpg"
    cv2.imwrite(str(p), s, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return p


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(c.ROOT / "data" / "gen"))
    ap.add_argument("--seed", type=int, default=2026)
    a = ap.parse_args()
    out = Path(a.out)
    rows = build(out, a.seed)
    (out / "manifest-procedural.json").write_text(json.dumps(rows, indent=1))
    for st in OPS:
        print(sheet(out, rows, st))
    print(len(rows), "images")
