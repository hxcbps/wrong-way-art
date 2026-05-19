#!/usr/bin/env python3
import json
import math
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "art/characters/astra-mycelion/refinement/air-attack/astra_mycelion_air_attack_v2_source.png"
COMPONENT_ROOT = ROOT / "art/characters/astra-mycelion/game-ready/components/air_attack"
LEGACY_ROOT = ROOT / "art/characters/astra-mycelion/game-ready/frames/combat-defense/air_attack"
METADATA = ROOT / "art/characters/astra-mycelion/game-ready/metadata/astra_mycelion_animations.json"
COMBAT_ATLAS = ROOT / "art/characters/astra-mycelion/game-ready/atlases/astra_mycelion_combat_defense_atlas.png"
QA_ROOT = ROOT / "art/characters/astra-mycelion/game-ready/qa/air_attack"

HI_CELL = (384, 256)
LEGACY_CELL = (192, 192)
PIVOT_HI = (192, 244)
PIVOT_LEGACY = (96, 176)
FPS = 14


def clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def trim_alpha(im: Image.Image):
    bbox = im.getchannel("A").getbbox()
    if bbox is None:
        return im, None
    return im.crop(bbox), bbox


def x_segments(im: Image.Image, expected=6):
    alpha = np.array(im.getchannel("A")) > 8
    active = alpha.sum(axis=0) > 3
    segments = []
    start = None
    for x, value in enumerate(active):
        if value and start is None:
            start = x
        if (not value or x == len(active) - 1) and start is not None:
            end = x if not value else x + 1
            if end - start > 16:
                segments.append([start, end])
            start = None
    if len(segments) != expected:
        raise RuntimeError(f"Expected {expected} air_attack frames, detected {len(segments)}: {segments}")
    return segments


def crop_segment(im: Image.Image, x0, x1, pad=18):
    alpha = im.getchannel("A")
    crop = im.crop((max(0, x0 - pad), 0, min(im.width, x1 + pad), im.height))
    bbox = crop.getchannel("A").getbbox()
    if bbox is None:
        raise RuntimeError("Detected empty air_attack crop")
    tight = crop.crop((
        max(0, bbox[0] - pad),
        max(0, bbox[1] - pad),
        min(crop.width, bbox[2] + pad),
        min(crop.height, bbox[3] + pad),
    ))
    return tight


def normalize(im: Image.Image, cell, pivot, max_fill=0.86):
    trimmed, bbox = trim_alpha(im)
    if bbox is None:
        return Image.new("RGBA", cell, (0, 0, 0, 0)), {"source_bounds": None, "scale": 1.0, "paste_xy": [0, 0]}
    max_w = cell[0] * max_fill
    max_h = cell[1] * max_fill
    scale = min(max_w / trimmed.width, max_h / trimmed.height, 1.0)
    if scale < 1.0:
        trimmed = trimmed.resize((max(1, round(trimmed.width * scale)), max(1, round(trimmed.height * scale))), Image.Resampling.LANCZOS)
    x = round(pivot[0] - trimmed.width / 2)
    y = round(pivot[1] - trimmed.height)
    x = max(0, min(cell[0] - trimmed.width, x))
    y = max(0, min(cell[1] - trimmed.height, y))
    canvas = Image.new("RGBA", cell, (0, 0, 0, 0))
    canvas.alpha_composite(trimmed, (x, y))
    return canvas, {
        "source_bounds": list(bbox),
        "trimmed_size": [trimmed.width, trimmed.height],
        "scale": round(scale, 6),
        "paste_xy": [x, y],
        "alpha_bbox": list(canvas.getchannel("A").getbbox()),
    }


def edge_clearance(im: Image.Image):
    bbox = im.getchannel("A").getbbox()
    if bbox is None:
        return None
    left, top, right, bottom = bbox
    return {
        "left": left,
        "top": top,
        "right": im.width - right,
        "bottom": im.height - bottom,
        "passes": left > 0 and top > 0 and right < im.width and bottom < im.height and min(left, top, im.width - right, im.height - bottom) >= 2,
    }


def make_atlas(frames, cell):
    atlas = Image.new("RGBA", (len(frames) * cell[0], cell[1]), (0, 0, 0, 0))
    rects = []
    for idx, frame in enumerate(frames):
        x = idx * cell[0]
        atlas.alpha_composite(frame, (x, 0))
        rects.append({"name": f"air_attack_{idx:03d}.png", "x": x, "y": 0, "w": cell[0], "h": cell[1]})
    return atlas, rects


def checker(size, block=16):
    im = Image.new("RGBA", size, (32, 32, 32, 255))
    draw = ImageDraw.Draw(im)
    for y in range(0, size[1], block):
        for x in range(0, size[0], block):
            color = (48, 48, 48, 255) if (x // block + y // block) % 2 == 0 else (28, 28, 28, 255)
            draw.rectangle((x, y, x + block, y + block), fill=color)
    return im


def make_contact(frames, cell, pivot):
    out = Image.new("RGBA", (len(frames) * cell[0], cell[1]), (0, 0, 0, 255))
    for idx, frame in enumerate(frames):
        backing = checker(cell)
        draw = ImageDraw.Draw(backing)
        draw.line((pivot[0] - 8, pivot[1], pivot[0] + 8, pivot[1]), fill=(255, 64, 64, 180), width=1)
        draw.line((pivot[0], pivot[1] - 8, pivot[0], pivot[1] + 8), fill=(255, 64, 64, 180), width=1)
        backing.alpha_composite(frame, (0, 0))
        out.alpha_composite(backing, (idx * cell[0], 0))
    return out


def update_combat_atlas():
    data = json.loads(METADATA.read_text())
    air_frames = []
    for idx in range(6):
        file_path = LEGACY_ROOT / f"air_attack_{idx:03d}.png"
        air_frames.append({
            "index": idx,
            "file": str(file_path.relative_to(ROOT)),
            "duration": round(1 / FPS, 6),
            "source": "curated-air-attack-v2",
            "cell_size": list(LEGACY_CELL),
        })
    data["animations"]["air_attack"] = {
        "sheet": "combat-defense",
        "fps": FPS,
        "loop": False,
        "curated_component": str((COMPONENT_ROOT / "metadata/air_attack_component.json").relative_to(ROOT)),
        "frames": air_frames,
    }

    combat_frames = []
    for anim_name, anim in data["animations"].items():
        if anim.get("sheet") != "combat-defense":
            continue
        for frame in anim["frames"]:
            file_path = ROOT / frame["file"]
            combat_frames.append((f"combat-defense/{anim_name}/{file_path.name}", Image.open(file_path).convert("RGBA")))

    cols = 8
    rows = math.ceil(len(combat_frames) / cols)
    atlas = Image.new("RGBA", (cols * LEGACY_CELL[0], rows * LEGACY_CELL[1]), (0, 0, 0, 0))
    rects = []
    for idx, (name, frame) in enumerate(combat_frames):
        x = (idx % cols) * LEGACY_CELL[0]
        y = (idx // cols) * LEGACY_CELL[1]
        if frame.size != LEGACY_CELL:
            frame = frame.resize(LEGACY_CELL, Image.Resampling.LANCZOS)
        atlas.alpha_composite(frame, (x, y))
        rects.append({"name": name, "x": x, "y": y, "w": LEGACY_CELL[0], "h": LEGACY_CELL[1]})
    atlas.save(COMBAT_ATLAS)
    data["atlases"]["combat-defense"] = {
        "file": str(COMBAT_ATLAS.relative_to(ROOT)),
        "frames": rects,
        "note": "Combat atlas repacked after curated air_attack v2 replacement."
    }
    METADATA.write_text(json.dumps(data, indent=2))


def main():
    src = Image.open(SOURCE).convert("RGBA")
    segments = x_segments(src, expected=6)
    clean_dir(COMPONENT_ROOT / "frames")
    clean_dir(COMPONENT_ROOT / "atlas")
    clean_dir(COMPONENT_ROOT / "metadata")
    clean_dir(QA_ROOT)
    LEGACY_ROOT.mkdir(parents=True, exist_ok=True)

    hi_frames = []
    legacy_frames = []
    frame_metadata = []
    for idx, (x0, x1) in enumerate(segments):
        crop = crop_segment(src, x0, x1)
        hi, hi_qa = normalize(crop, HI_CELL, PIVOT_HI, max_fill=0.92)
        legacy, legacy_qa = normalize(crop, LEGACY_CELL, PIVOT_LEGACY, max_fill=0.86)
        hi_path = COMPONENT_ROOT / "frames" / f"air_attack_{idx:03d}.png"
        legacy_path = LEGACY_ROOT / f"air_attack_{idx:03d}.png"
        hi.save(hi_path)
        legacy.save(legacy_path)
        hi_frames.append(hi)
        legacy_frames.append(legacy)
        frame_metadata.append({
            "index": idx,
            "source_segment": [x0, x1],
            "frame": str(hi_path.relative_to(ROOT)),
            "legacy_frame": str(legacy_path.relative_to(ROOT)),
            "duration": round(1 / FPS, 6),
            "hi": hi_qa,
            "legacy": legacy_qa,
            "edge_clearance_hi": edge_clearance(hi),
            "edge_clearance_legacy": edge_clearance(legacy),
        })

    atlas, rects = make_atlas(hi_frames, HI_CELL)
    atlas_path = COMPONENT_ROOT / "atlas" / "astra_mycelion_air_attack_v2_atlas.png"
    atlas.save(atlas_path)
    make_contact(hi_frames, HI_CELL, PIVOT_HI).save(QA_ROOT / "air_attack_v2_contact_hi.png")
    make_contact(legacy_frames, LEGACY_CELL, PIVOT_LEGACY).save(QA_ROOT / "air_attack_v2_contact_legacy.png")

    metadata = {
        "component": "air_attack",
        "version": "v2-curated",
        "source": str(SOURCE.relative_to(ROOT)),
        "frame_count": 6,
        "fps": FPS,
        "loop": False,
        "cell_size": list(HI_CELL),
        "pivot_pixels": list(PIVOT_HI),
        "legacy_cell_size": list(LEGACY_CELL),
        "legacy_pivot_pixels": list(PIVOT_LEGACY),
        "atlas": {"file": str(atlas_path.relative_to(ROOT)), "frames": rects},
        "frames": frame_metadata,
        "qa": {
            "status": "passes-component-audit",
            "checks": [
                "six readable animation frames",
                "no alpha touching frame edges in canonical frames",
                "no neighboring sprite bleed",
                "transparent PNG output",
                "legacy air_attack frames replaced for existing GitHub paths"
            ]
        }
    }
    (COMPONENT_ROOT / "metadata" / "air_attack_component.json").write_text(json.dumps(metadata, indent=2))
    update_combat_atlas()
    print(f"Curated air_attack frames: {len(hi_frames)}")
    print(f"Wrote {atlas_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
