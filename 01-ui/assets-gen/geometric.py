"""Deterministic PC10 images: OK, handle misalignment, fit gap, length and width out of tolerance.

Usage: uv run python geometric.py [--out OUT_DIR] [--seed N]
"""

from __future__ import annotations

import argparse
import json
import zlib
from pathlib import Path

import cv2
import numpy as np

import common as c


def alpha_mask(p: np.ndarray) -> np.ndarray:
    return (p[..., 3] > 0.5).astype(np.float32)


def op_ok(layer: c.Layer, rng):
    """Within tolerance: tiny length/width variation only."""
    blade, handle = c.split(layer)
    d_len = rng.uniform(-2.0, 2.0)
    d_w = rng.uniform(-0.7, 0.7)
    return _length_width(layer, blade, handle, d_len, d_w, rng, defect=None)


def _length_width(layer, blade, handle, d_len_mm, d_w_mm, rng, defect):
    h0 = c.blade_height_px(layer)
    s = 1.0 + d_len_mm * c.PX_PER_MM / (c.JUNCTION_X - c.TIP_X)
    t = 1.0 + d_w_mm * c.PX_PER_MM / h0
    m_blade = np.array([[s, 0, c.TIP_X * (1 - s)], [0, t, c.AXIS_Y * (1 - t)]], np.float32)
    jx = c.TIP_X + (c.JUNCTION_X - c.TIP_X) * s
    dx = jx - c.JUNCTION_X
    blade_w = c.warp(blade, m_blade)
    handle_w = c.warp(handle, c.translate(dx, 0))
    seam = c.tang_patch(int(round(jx)) - 4, int(round(jx)) + 4, y_half=36)
    p = c.over(handle_w, c.over(seam, blade_w))
    length_mm = (c.END_X + dx - c.TIP_X + 1) / c.PX_PER_MM
    width_mm = h0 * t / c.PX_PER_MM
    truth = {
        "length_mm": round(float(length_mm), 1),
        "width_mm": round(float(width_mm), 1),
        "nominal_length_mm": c.NOMINAL_LENGTH_MM,
        "nominal_width_mm": round(h0 / c.PX_PER_MM, 1),
        "tol_length_mm": c.TOL_LENGTH_MM,
        "tol_width_mm": c.TOL_WIDTH_MM,
        "px_per_mm": round(c.PX_PER_MM, 3),
    }
    masks = {}
    if defect == "length_out_of_tolerance":
        masks["defect"] = alpha_mask(p)
    elif defect == "width_out_of_tolerance":
        masks["defect"] = alpha_mask(blade_w)
    return p, masks, truth


def op_length(layer, rng):
    blade, handle = c.split(layer)
    mag = rng.uniform(8.0, 22.0) * rng.choice([-1, 1])
    return _length_width(layer, blade, handle, mag, rng.uniform(-0.5, 0.5), rng, "length_out_of_tolerance")


def op_width(layer, rng):
    blade, handle = c.split(layer)
    mag = rng.uniform(3.5, 7.0) * rng.choice([-1, 1])
    return _length_width(layer, blade, handle, rng.uniform(-2, 2), mag, rng, "width_out_of_tolerance")


def op_handle_misalignment(layer, rng):
    """Desface de cacha: handle rotated / offset with respect to the blade axis."""
    blade, handle = c.split(layer)
    deg = rng.uniform(1.6, 4.2) * rng.choice([-1, 1])
    dy = rng.uniform(2.0, 7.0) * np.sign(deg) * -1
    m = np.vstack([c.rotate_about(deg, c.JUNCTION_X + 6, c.AXIS_Y), [0, 0, 1]])
    m = (np.vstack([c.translate(0, dy), [0, 0, 1]]) @ m)[:2]
    handle_w = c.warp(handle, m)
    tang = c.tang_patch(c.JUNCTION_X - 4, c.JUNCTION_X + 18, y_half=36)
    p = c.over(handle_w, c.over(tang, blade))
    mask = alpha_mask(handle_w)
    mask[:, : c.JUNCTION_X - 25] = 0
    truth = {"offset_deg": round(float(deg), 2), "offset_px": round(float(dy), 1)}
    return p, {"defect": mask}, truth


def op_fit_gap(layer, rng):
    """Mal ajuste: handle not fully seated, visible gap at the seam."""
    blade, handle = c.split(layer)
    gap = int(rng.integers(7, 19))
    handle_w = c.warp(handle, c.translate(gap, rng.uniform(-1.5, 1.5)))
    tang = c.tang_patch(c.JUNCTION_X - 6, c.JUNCTION_X + gap + 6, y_half=36, shade=float(rng.uniform(0.85, 1.1)))
    p = c.over(handle_w, c.over(tang, blade))
    mask = np.zeros(blade.shape[:2], np.float32)
    mask[c.AXIS_Y - 50 : c.AXIS_Y + 50, c.JUNCTION_X - 14 : c.JUNCTION_X + gap + 14] = 1
    truth = {"gap_mm": round(gap / c.PX_PER_MM, 1)}
    return p, {"defect": mask}, truth


OPS = {
    "ok": op_ok,
    "length_out_of_tolerance": op_length,
    "width_out_of_tolerance": op_width,
    "handle_misalignment": op_handle_misalignment,
    "poor_assembly_fit": op_fit_gap,
}
COUNTS = {"ok": 24, "length_out_of_tolerance": 10, "width_out_of_tolerance": 10, "handle_misalignment": 10, "poor_assembly_fit": 10}


def build(out: Path, seed: int) -> list[dict]:
    layer = c.load_layer()
    rows = []
    for cls, n in COUNTS.items():
        (out / cls).mkdir(parents=True, exist_ok=True)
        for i in range(n):
            rng = np.random.default_rng([seed, zlib.crc32(cls.encode()) % 10_000, i])
            p, masks, truth = OPS[cls](layer, rng)
            img, boxes = c.compose(p, rng, masks)
            name = f"{cls}/{cls}-{i:02d}.jpg"
            cv2.imwrite(str(out / name), img, [cv2.IMWRITE_JPEG_QUALITY, 90])
            rows.append(
                {
                    "file": name,
                    "station": "PC10",
                    "defect": None if cls == "ok" else cls,
                    "bbox": boxes.get("defect"),
                    "truth": truth,
                    "method": "deterministic",
                    "simulated": True,
                }
            )
    return rows


def contact_sheet(out: Path, rows: list[dict], cls: str, cols: int = 4, tw: int = 600) -> Path:
    sel = [r for r in rows if (r["defect"] or "ok") == cls][: cols * 3]
    th = int(tw * c.CANVAS_H / c.CANVAS_W)
    sheet = np.full((((len(sel) + cols - 1) // cols) * th, cols * tw, 3), 255, np.uint8)
    for k, r in enumerate(sel):
        im = cv2.imread(str(out / r["file"]))
        if r["bbox"]:
            x0, y0, x1, y1 = r["bbox"]
            cv2.rectangle(im, (x0, y0), (x1, y1), (0, 140, 255), 3)
        im = cv2.resize(im, (tw, th), interpolation=cv2.INTER_AREA)
        sheet[(k // cols) * th : (k // cols + 1) * th, (k % cols) * tw : (k % cols + 1) * tw] = im
    path = out / f"sheet-{cls}.jpg"
    cv2.imwrite(str(path), sheet, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(c.ROOT / "data" / "gen" / "pc10"))
    ap.add_argument("--seed", type=int, default=2026)
    a = ap.parse_args()
    out = Path(a.out)
    rows = build(out, a.seed)
    (out / "manifest-geometric.json").write_text(json.dumps(rows, indent=1))
    for cls in COUNTS:
        print(contact_sheet(out, rows, cls))
    print(len(rows), "images")
