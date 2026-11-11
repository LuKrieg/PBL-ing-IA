"""Texture defects for PC10 using the local ia-local Z-Image img2img model, on a CROP only.

Run with the ia-local environment (GPU):
  cd ~/projects/personal-projects/ai/ia-local && uv run python <this file> --kind rust --n 8
Writes patched full-size photos + masks to data/gen/patched/. The rest of the machete stays the real photo.
Everything produced is SIMULATED demo material, not training data.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "data" / "base" / "m980-original.jpg"
OUT = ROOT / "data" / "gen" / "patched"
RIVETS = [(1137, 800), (1261, 804), (1379, 813)]

# kind -> (crop half-size (w,h), region centers, prompt, strength, mask radius scale)
KINDS = {
    "rust": dict(
        half=(100, 100), centers=RIVETS, strength=0.62, mask_r=62, defect="rusty_rivets",
        prompt="extreme close-up photo of a steel rivet on a light wooden machete handle, the rivet is heavily corroded "
               "with orange-brown rust, rust stains bleeding into the wood grain around it, macro, sharp, studio lighting",
    ),
    "badrivet": dict(
        half=(100, 100), centers=RIVETS, strength=0.68, mask_r=62, defect="bad_riveting",
        prompt="extreme close-up photo of a badly set steel rivet on a light wooden machete handle, the rivet is crooked "
               "and off-center, with a deformed flattened mushroomed head and a small crack in the wood around it, macro, sharp",
    ),
    "finish_handle": dict(
        half=(190, 95), centers=[(1170, 770), (1300, 770), (1240, 855), (1370, 852)], strength=0.6, mask_r=100,
        defect="poor_finish",
        prompt="close-up photo of the edge of a light wooden machete handle with a rough unfinished surface, splinters, "
               "sanding marks and burrs, macro, sharp, studio lighting",
    ),
    "finish_blade": dict(
        half=(190, 95), centers=[(560, 868), (700, 868), (860, 866), (980, 866)], strength=0.6, mask_r=100,
        defect="poor_finish",
        prompt="close-up photo of a carbon steel machete blade edge with rough grinding marks, burrs and uneven "
               "polishing, scratches, macro, sharp, studio lighting",
    ),
}


def feather_mask(size, r_w, r_h):
    w, h = size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((xx - w / 2) / r_w) ** 2 + ((yy - h / 2) / r_h) ** 2)
    m = np.clip((1.0 - d) / 0.35, 0, 1)
    return m


def run(kind, n, seed0):
    from iagen.edit import edit_image

    cfg = KINDS[kind]
    base = Image.open(BASE).convert("RGB")
    hw, hh = cfg["half"]
    OUT.mkdir(parents=True, exist_ok=True)
    meta = []
    tiles = []
    for i in range(n):
        cx, cy = cfg["centers"][i % len(cfg["centers"])]
        box = (cx - hw, cy - hh, cx + hw, cy + hh)
        crop = base.crop(box)
        scale = 512 / max(crop.size)
        up = crop.resize((round(crop.width * scale) // 16 * 16, round(crop.height * scale) // 16 * 16), Image.LANCZOS)
        gen, _, seed = edit_image(up, cfg["prompt"], strength=cfg["strength"], seed=seed0 + i, save=False,
                                  longest_side=max(up.size))
        gen = gen.resize(crop.size, Image.LANCZOS)
        m = feather_mask(crop.size, cfg["mask_r"] * 1.0, cfg["mask_r"] * (hh / hw) * 1.0 if hw != hh else cfg["mask_r"])
        mimg = Image.fromarray((m * 255).astype(np.uint8))
        full = base.copy()
        full.paste(gen, box[:2], mimg)
        name = f"{kind}-{i:02d}"
        full.save(OUT / f"{name}.png")
        # defect bbox = where the feathered mask is strong
        ys, xs = np.where(m > 0.5)
        bbox = [int(box[0] + xs.min()), int(box[1] + ys.min()), int(box[0] + xs.max()), int(box[1] + ys.max())]
        meta.append({"name": name, "kind": kind, "defect": cfg["defect"], "bbox_layer": bbox, "seed": int(seed),
                     "center": [cx, cy], "prompt": cfg["prompt"], "strength": cfg["strength"]})
        side = Image.new("RGB", (crop.width * 2, crop.height))
        side.paste(crop, (0, 0)); side.paste(full.crop(box), (crop.width, 0))
        tiles.append(side)
    (OUT / f"meta-{kind}.json").write_text(json.dumps(meta, indent=1))
    cols = 2
    tw, th = tiles[0].size
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * th), "white")
    for k, t in enumerate(tiles):
        sheet.paste(t, ((k % cols) * tw, (k // cols) * th))
    sheet.save(OUT / f"sheet-{kind}.jpg", quality=85)
    print("done", kind, n)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True, choices=KINDS)
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--seed", type=int, default=100)
    a = ap.parse_args()
    run(a.kind, a.n, a.seed)
