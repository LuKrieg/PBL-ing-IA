"""Shared helpers to synthesize PC10 demo images from the IMACASA Classic 980 catalog photo.

Everything here is SIMULATED demo material (no real plant photos exist yet).
Geometric defects are made deterministically so ground truth (bbox, mm values) is exact.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[2]
BASE_PHOTO = ROOT / "data" / "base" / "m980-original.jpg"

# Canvas = crop of the 1500x1500 catalog photo around the machete.
CANVAS_W, CANVAS_H = 1500, 540
CROP_Y0 = 480

# Geometry measured on the catalog photo (layer space, pixels).
TIP_X = 37
END_X = 1439
JUNCTION_X = 1062  # blade / handle (cacha) seam
AXIS_Y = 811  # handle axis
SECTION_X = 700  # blade section where the width is measured
RIVETS = [(1137, 800), (1261, 804), (1379, 813)]

# Calibration. ASSUMPTION: nominal overall length 560 mm (~22 in). Replace with the real IMACASA spec.
NOMINAL_LENGTH_MM = 560.0
PX_PER_MM = (END_X - TIP_X + 1) / NOMINAL_LENGTH_MM
TOL_LENGTH_MM = 5.0
TOL_WIDTH_MM = 2.0  # ASSUMPTION, to confirm with IMACASA
SCALE_BAR_MM = 100
SCALE_BAR_PX0 = (70, 478)  # fixed fixture reference, never jittered


@dataclass
class Layer:
    """Premultiplied RGBA float32 (H, W, 4) in layer space (1500x1500)."""

    p: np.ndarray

    @property
    def a(self) -> np.ndarray:
        return self.p[..., 3]


def load_layer(path: Path | None = None) -> Layer:
    import PIL.Image as Image

    rgb = np.asarray(Image.open(path or BASE_PHOTO).convert("RGB")).astype(np.float32)
    minc = rgb.min(axis=2)
    m = minc < 238
    m = ndi.binary_closing(m, iterations=2)
    m = ndi.binary_fill_holes(m)
    m = ndi.binary_opening(m, iterations=1)
    m = ndi.binary_erosion(m, iterations=1)
    a = ndi.gaussian_filter(m.astype(np.float32), 0.8)
    p = np.dstack([rgb * a[..., None], a])
    return Layer(p)


def over(top: np.ndarray, bottom: np.ndarray) -> np.ndarray:
    return top + (1.0 - top[..., 3:4]) * bottom


def split(layer: Layer) -> tuple[np.ndarray, np.ndarray]:
    blade = layer.p.copy()
    blade[:, JUNCTION_X:] = 0
    handle = layer.p.copy()
    handle[:, :JUNCTION_X] = 0
    return blade, handle


def warp(p: np.ndarray, m23: np.ndarray, size: tuple[int, int] | None = None) -> np.ndarray:
    h, w = p.shape[:2]
    out_size = size or (w, h)
    return cv2.warpAffine(
        p, m23.astype(np.float32), out_size, flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=0
    )


def translate(dx: float, dy: float) -> np.ndarray:
    return np.array([[1, 0, dx], [0, 1, dy]], dtype=np.float32)


def rotate_about(deg: float, cx: float, cy: float) -> np.ndarray:
    return cv2.getRotationMatrix2D((cx, cy), -deg, 1.0).astype(np.float32)


def tang_patch(x0: int, x1: int, y_half: int = 38, shade: float = 1.0) -> np.ndarray:
    """Dark steel tang visible when the handle is not seated; opaque premultiplied patch."""
    h, w = 1500, 1500
    p = np.zeros((h, w, 4), np.float32)
    ys = np.arange(AXIS_Y - y_half, AXIS_Y + y_half)
    t = (ys - (AXIS_Y - y_half)) / (2 * y_half)
    col = (62 + 38 * np.sin(np.pi * t)) * shade  # simple cylindrical shading
    for x in range(x0, x1):
        p[ys, x, 0] = col
        p[ys, x, 1] = col * 1.02
        p[ys, x, 2] = col * 1.08
        p[ys, x, 3] = 1.0
    return p


def mask_bbox(mask: np.ndarray, pad: int = 8, thr: float = 0.3) -> list[int] | None:
    ys, xs = np.where(mask > thr)
    if len(xs) == 0:
        return None
    h, w = mask.shape[:2]
    return [
        int(max(xs.min() - pad, 0)),
        int(max(ys.min() - pad, 0)),
        int(min(xs.max() + pad, w - 1)),
        int(min(ys.max() + pad, h - 1)),
    ]


def jitter_matrix(rng: np.random.Generator, jitter: bool = True) -> np.ndarray:
    """Layer->canvas 2x3 matrix: small camera/fixture variation + crop offset. No scale change."""
    deg = rng.uniform(-1.0, 1.0) if jitter else 0.0
    tx, ty = (rng.uniform(-14, 14), rng.uniform(-14, 14)) if jitter else (0.0, 0.0)
    r = np.vstack([rotate_about(deg, 750, 810), [0, 0, 1]])
    t = np.vstack([translate(tx, ty - CROP_Y0), [0, 0, 1]])
    return (t @ r)[:2]


def _background(rng: np.random.Generator) -> np.ndarray:
    g = rng.uniform(236, 250)
    yy, xx = np.mgrid[0:CANVAS_H, 0:CANVAS_W].astype(np.float32)
    cx, cy = rng.uniform(0.35, 0.65) * CANVAS_W, rng.uniform(0.35, 0.65) * CANVAS_H
    r = np.hypot((xx - cx) / CANVAS_W, (yy - cy) / CANVAS_H)
    grad = 1.0 - rng.uniform(0.02, 0.07) * r / 0.7
    tilt = 1.0 + rng.uniform(-0.015, 0.015) * (xx / CANVAS_W - 0.5)
    return (g * grad * tilt)[..., None].repeat(3, axis=2)


def _scale_bar(img: np.ndarray) -> None:
    x0, y0 = SCALE_BAR_PX0
    seg = int(round(10 * PX_PER_MM))
    n = SCALE_BAR_MM // 10
    for i in range(n):
        c = (25, 25, 25) if i % 2 == 0 else (245, 245, 245)
        cv2.rectangle(img, (x0 + i * seg, y0), (x0 + (i + 1) * seg, y0 + 16), c, -1)
    cv2.rectangle(img, (x0, y0), (x0 + n * seg, y0 + 16), (25, 25, 25), 1)
    cv2.putText(img, f"{SCALE_BAR_MM} mm", (x0 + n * seg + 10, y0 + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (40, 40, 40), 1, cv2.LINE_AA)


def compose(
    p: np.ndarray,
    rng: np.random.Generator,
    masks: dict[str, np.ndarray] | None = None,
    jitter: bool = True,
) -> tuple[np.ndarray, dict[str, list[int] | None]]:
    """Render layer `p` on a studio-like background; returns (uint8 BGR image, bboxes in canvas px)."""
    m = jitter_matrix(rng, jitter)
    pw = warp(p, m, (CANVAS_W, CANVAS_H))
    a = np.clip(pw[..., 3], 0, 1)
    bg = _background(rng)
    shadow = ndi.gaussian_filter(np.roll(np.roll(a, 9, axis=1), 5, axis=0), 9) * 0.16
    bg = bg * (1 - shadow[..., None])
    img = pw[..., :3] + (1 - a[..., None]) * bg
    # photometric variation
    gain, gamma = rng.uniform(0.94, 1.06), rng.uniform(0.92, 1.08)
    img = 255.0 * np.power(np.clip(img * gain / 255.0, 0, 1), gamma)
    sig = rng.uniform(0.0, 0.5)
    if sig > 0.05:
        img = cv2.GaussianBlur(img, (0, 0), sig)
    img = np.clip(img, 0, 255).astype(np.uint8)
    img = np.ascontiguousarray(img[..., ::-1])  # RGB -> BGR for cv2 drawing/saving
    _scale_bar(img)
    noise = rng.normal(0, 1.5, img.shape).astype(np.float32)
    img = np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    boxes = {}
    for k, mk in (masks or {}).items():
        boxes[k] = mask_bbox(warp(mk[..., None].astype(np.float32), m, (CANVAS_W, CANVAS_H)).squeeze())
    return img, boxes


def blade_height_px(layer: Layer, x: int = SECTION_X) -> int:
    col = np.where(layer.a[:, x] > 0.5)[0]
    return int(col.max() - col.min() + 1)
