"""Assemble the demo image pool used by the UI backend (backend/seed/).

Inputs : data/base photo, data/gen/patched (diffusion crops from ia-local).
Output : ../backend/seed/images/** (JPEG 1200x432) + ../backend/seed/manifest.json
All images are SIMULATED demo material.
"""
import json
import shutil
import zlib
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

import common as c
import geometric as g
import procedural as pr

SEED = ROOT = c.ROOT
OUT = c.ROOT / "01-ui" / "backend" / "seed"
OUT_W, OUT_H = 1200, 432
SCALE = OUT_W / c.CANVAS_W
PATCHED = c.ROOT / "data" / "gen" / "patched"
BASE = np.asarray(Image.open(c.BASE_PHOTO).convert("L")).astype(np.int16)

# finish_blade was generated but rejected in review (unrealistic serrations); blade finish uses the procedural op below.
DIFF_KINDS = {"rust": "rusty_rivets", "badrivet": "bad_riveting", "finish_handle": "poor_finish"}
VARIANTS_PER_PATCH = 2


def save(img, rel):
    p = OUT / "images" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(p), cv2.resize(img, (OUT_W, OUT_H), interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 86])


def scaled(b):
    return [int(round(v * SCALE)) for v in b] if b else None


def row(rel, station, defect, bbox, truth, method):
    return {"file": rel, "station": station, "defect": defect, "bbox": scaled(bbox), "truth": truth, "method": method,
            "simulated": True, "w": OUT_W, "h": OUT_H}


def silhouette_ok(meta):
    """Reject diffusion patches that changed the machete outline (white background vs object)."""
    patched = np.asarray(Image.open(PATCHED / f"{meta['name']}.png").convert("L")).astype(np.int16)
    x0, y0, x1, y1 = meta["bbox_layer"]
    pad = 70
    sl = (slice(max(y0 - pad, 0), y1 + pad), slice(max(x0 - pad, 0), x1 + pad))
    diff = (BASE[sl] < 235) != (patched[sl] < 235)
    return diff.mean() < 0.006


def main():
    if OUT.exists():
        shutil.rmtree(OUT / "images", ignore_errors=True)
    rows = []
    layer = c.load_layer()

    # PC10 geometric + OK
    for cls, n in g.COUNTS.items():
        for i in range(n):
            rng = np.random.default_rng([2026, zlib.crc32(cls.encode()) % 10_000, i])
            p, masks, truth = g.OPS[cls](layer, rng)
            img, boxes = c.compose(p, rng, masks)
            rows.append(row(f"PC10/{cls}/{cls}-{i:02d}.jpg", "PC10", None if cls == "ok" else cls, boxes.get("defect"), truth, "deterministic"))
            save(img, rows[-1]["file"])

    # PC10 diffusion texture defects (silhouette-checked), with jitter variants
    kept, dropped = {}, {}
    for kind, defect in DIFF_KINDS.items():
        mf = PATCHED / f"meta-{kind}.json"
        if not mf.exists():
            print("missing", kind)
            continue
        for meta in json.loads(mf.read_text()):
            if not silhouette_ok(meta):
                dropped[kind] = dropped.get(kind, 0) + 1
                continue
            kept[kind] = kept.get(kind, 0) + 1
            pl = c.load_layer(PATCHED / f"{meta['name']}.png")
            x0, y0, x1, y1 = meta["bbox_layer"]
            m = np.zeros((1500, 1500), np.float32)
            m[y0:y1, x0:x1] = 1
            for v in range(VARIANTS_PER_PATCH):
                rng = np.random.default_rng([2026, zlib.crc32(meta["name"].encode()) % 10_000, v])
                img, boxes = c.compose(pl.p, rng, {"defect": m})
                rel = f"PC10/{defect}/{meta['name']}-v{v}.jpg"
                r = row(rel, "PC10", defect, boxes["defect"], {"seed": meta["seed"], "strength": meta["strength"]}, "diffusion-z-image-turbo-crop")
                rows.append(r)
                save(img, rel)
    print("diffusion kept", kept, "dropped", dropped)

    # PC10 poor finish on the blade (cuchilla): scratches, edge nicks/burrs, pitting+oxidation, gouge, uneven polish
    blade_ops = {**pr.BLADE_FINISH, "polish": pr.op_poor_polish}
    for kind, fn in blade_ops.items():
        for i in range(5):
            rng = np.random.default_rng([2026, zlib.crc32(kind.encode()) % 10_000, i])
            p, masks, truth = fn(layer, rng)
            img, boxes = c.compose(p, rng, masks)
            rows.append(row(f"PC10/poor_finish/poor_finish-blade-{kind}-{i:02d}.jpg", "PC10", "poor_finish", boxes.get("defect"), truth, "procedural"))
            save(img, rows[-1]["file"])

    # PC12 reuse of shared / dimension defects + OK for PC08 and PC12
    for station, cls, op, n in [("PC12", "handle_misalignment", g.op_handle_misalignment, 10), ("PC12", "dimensions_out_of_spec", None, 8)]:
        for i in range(n):
            rng = np.random.default_rng([2027, zlib.crc32((station + cls).encode()) % 10_000, i])
            fn = op or (g.op_length if i % 2 == 0 else g.op_width)
            p, masks, truth = fn(layer, rng)
            img, boxes = c.compose(p, rng, masks)
            rows.append(row(f"{station}/{cls}/{cls}-{i:02d}.jpg", station, cls, boxes.get("defect"), truth, "deterministic"))
            save(img, rows[-1]["file"])
    for station in ("PC08", "PC12"):
        for i in range(12):
            rng = np.random.default_rng([2028, zlib.crc32(station.encode()) % 10_000, i])
            p, _, truth = g.op_ok(layer, rng)
            img, _ = c.compose(p, rng)
            rows.append(row(f"{station}/ok/ok-{i:02d}.jpg", station, None, None, truth, "deterministic"))
            save(img, rows[-1]["file"])

    # PC08 / PC12 procedural
    for station, ops in pr.OPS.items():
        for cls, fn in ops.items():
            for i in range(pr.PER_CLASS):
                rng = np.random.default_rng([2026, zlib.crc32(f"{station}{cls}".encode()) % 100_000, i])
                p, masks, truth = fn(layer, rng)
                img, boxes = c.compose(p, rng, masks)
                rows.append(row(f"{station}/{cls}/{cls}-{i:02d}.jpg", station, cls, boxes.get("defect"), truth, "procedural"))
                save(img, rows[-1]["file"])

    (OUT / "manifest.json").write_text(json.dumps(rows, indent=1, default=float))
    from collections import Counter
    cnt = Counter((r["station"], r["defect"] or "ok") for r in rows)
    for k in sorted(cnt):
        print(k, cnt[k])
    print(len(rows), "images ->", OUT)


if __name__ == "__main__":
    main()
