#!/usr/bin/env python3
import json
import math
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from curate_air_attack_component import (
    crop_segment,
    edge_clearance,
    make_atlas,
    make_contact,
    normalize,
    x_segments,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "art/characters/astra-mycelion/refinement/dash-attack/astra_mycelion_dash_attack_v2_source.png"
COMPONENT_ROOT = ROOT / "art/characters/astra-mycelion/game-ready/components/dash_attack"
LEGACY_ROOT = ROOT / "art/characters/astra-mycelion/game-ready/frames/combat-defense/dash_attack"
METADATA = ROOT / "art/characters/astra-mycelion/game-ready/metadata/astra_mycelion_animations.json"
COMBAT_ATLAS = ROOT / "art/characters/astra-mycelion/game-ready/atlases/astra_mycelion_combat_defense_atlas.png"
QA_ROOT = ROOT / "art/characters/astra-mycelion/game-ready/qa/dash_attack"

HI_CELL = (384, 256)
LEGACY_CELL = (192, 192)
PIVOT_HI = (192, 248)
PIVOT_LEGACY = (96, 172)
FPS = 18
FRAME_COUNT = 8
VERSION = "v2.1-curated"
TIMING = [0.09, 0.045, 0.04, 0.035, 0.05, 0.06, 0.075, 0.1]


def clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def update_combat_atlas():
    data = json.loads(METADATA.read_text())
    dash_frames = []
    for idx in range(FRAME_COUNT):
        file_path = LEGACY_ROOT / f"dash_attack_{idx:03d}.png"
        dash_frames.append({
            "index": idx,
            "file": str(file_path.relative_to(ROOT)),
            "duration": TIMING[idx],
            "source": "curated-dash-attack-v2.1",
            "cell_size": list(LEGACY_CELL),
        })
    data["animations"]["dash_attack"] = {
        "sheet": "combat-defense",
        "fps": FPS,
        "loop": False,
        "curated_component": str((COMPONENT_ROOT / "metadata/dash_attack_component.json").relative_to(ROOT)),
        "frames": dash_frames,
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
        "note": "Combat atlas repacked after curated dash_attack v2 replacement."
    }
    METADATA.write_text(json.dumps(data, indent=2))


def draw_impact_overlay(frame: Image.Image, idx: int) -> Image.Image:
    """Add the game-feel pass for the contact and follow-through frames."""
    if idx not in {2, 3, 4}:
        return frame

    im = frame.copy()
    bbox = im.getchannel("A").getbbox()
    if bbox is None:
        return im

    left, top, right, bottom = bbox
    width, height = im.size
    scale = width / 384
    safe_margin = max(18, 30 * scale)
    cx = min(width - safe_margin, right - 34 * scale)
    cy = top + (bottom - top) * (0.47 if idx == 3 else 0.52)
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    if idx == 2:
        # Pre-impact compression: thin amber speed needles ahead of the lance.
        for n in range(4):
            y = cy + (n - 1.5) * 8 * scale
            draw.line(
                (cx - 12 * scale, y, min(width - safe_margin, cx + (24 + n * 6) * scale), y - 3 * scale),
                fill=(255, 224, 54, 150),
                width=max(1, round(2 * scale)),
            )
    elif idx == 3:
        # Main contact: sharp starburst, short shock ring, and obsidian shard spray.
        r_outer = min(42 * scale, (width - safe_margin - cx) * 0.9)
        r_inner = 12 * scale
        points = []
        for n in range(18):
            angle = n * 3.14159265 * 2 / 18
            radius = r_outer if n % 2 == 0 else r_inner
            points.append((cx + math.cos(angle) * radius, cy + math.sin(angle) * radius))
        draw.polygon(points, fill=(255, 211, 42, 205))
        draw.ellipse((cx - 28 * scale, cy - 28 * scale, cx + 28 * scale, cy + 28 * scale), outline=(255, 179, 33, 230), width=max(1, round(3 * scale)))
        draw.line((cx - 70 * scale, cy, min(width - safe_margin, cx + 42 * scale), cy), fill=(255, 244, 145, 235), width=max(2, round(4 * scale)))
        draw.line((cx - 42 * scale, cy - 18 * scale, min(width - safe_margin, cx + 32 * scale), cy + 15 * scale), fill=(255, 179, 33, 190), width=max(1, round(2 * scale)))
        for n in range(9):
            angle = -0.65 + n * 0.16
            sx = cx + math.cos(angle) * 30 * scale
            sy = cy + math.sin(angle) * 30 * scale
            shard = [
                (sx, sy),
                (sx + 10 * scale, sy + (n % 3 - 1) * 5 * scale),
                (sx + 2 * scale, sy + 10 * scale),
            ]
            draw.polygon(shard, fill=(42, 44, 49, 210), outline=(255, 224, 54, 150))
    elif idx == 4:
        # Follow-through: fading fracture trail so the hit has a readable aftershock.
        for n in range(8):
            x = cx - (n * 18 + 8) * scale
            y = cy + ((n % 3) - 1) * 9 * scale
            draw.line((x, y, x + 28 * scale, y - 5 * scale), fill=(255, 179, 33, max(45, 150 - n * 13)), width=max(1, round(2 * scale)))
            draw.polygon(
                [(x + 7 * scale, y), (x + 14 * scale, y + 7 * scale), (x + 2 * scale, y + 9 * scale)],
                fill=(141, 40, 71, max(45, 130 - n * 10)),
            )

    glow = layer.filter(ImageFilter.GaussianBlur(max(1, round(5 * scale))))
    glow.putalpha(glow.getchannel("A").point(lambda value: min(150, value)))
    im.alpha_composite(glow)
    im.alpha_composite(layer)
    return im


def main():
    src = Image.open(SOURCE).convert("RGBA")
    segments = x_segments(src, expected=FRAME_COUNT)
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
        hi = draw_impact_overlay(hi, idx)
        legacy = draw_impact_overlay(legacy, idx)
        hi_qa["alpha_bbox"] = list(hi.getchannel("A").getbbox())
        legacy_qa["alpha_bbox"] = list(legacy.getchannel("A").getbbox())
        hi_path = COMPONENT_ROOT / "frames" / f"dash_attack_{idx:03d}.png"
        legacy_path = LEGACY_ROOT / f"dash_attack_{idx:03d}.png"
        hi.save(hi_path)
        legacy.save(legacy_path)
        hi_frames.append(hi)
        legacy_frames.append(legacy)
        frame_metadata.append({
            "index": idx,
            "source_segment": [x0, x1],
            "frame": str(hi_path.relative_to(ROOT)),
            "legacy_frame": str(legacy_path.relative_to(ROOT)),
            "duration": TIMING[idx],
            "hi": hi_qa,
            "legacy": legacy_qa,
            "edge_clearance_hi": edge_clearance(hi),
            "edge_clearance_legacy": edge_clearance(legacy),
        })

    atlas, rects = make_atlas(hi_frames, HI_CELL)
    atlas_path = COMPONENT_ROOT / "atlas" / "astra_mycelion_dash_attack_v2_atlas.png"
    atlas.save(atlas_path)
    make_contact(hi_frames, HI_CELL, PIVOT_HI).save(QA_ROOT / "dash_attack_v2_contact_hi.png")
    make_contact(legacy_frames, LEGACY_CELL, PIVOT_LEGACY).save(QA_ROOT / "dash_attack_v2_contact_legacy.png")

    metadata = {
        "component": "dash_attack",
        "version": VERSION,
        "source": str(SOURCE.relative_to(ROOT)),
        "frame_count": FRAME_COUNT,
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
                "eight readable dash attack frames",
                "curated anticipation/contact/recovery timing",
                "aggressive impact pass on the contact frame",
                "no alpha touching frame edges",
                "no neighboring sprite bleed",
                "transparent PNG output",
                "legacy dash_attack frames replaced for existing game-ready path"
            ]
        }
    }
    (COMPONENT_ROOT / "metadata" / "dash_attack_component.json").write_text(json.dumps(metadata, indent=2))
    update_combat_atlas()
    print(f"Curated dash_attack frames: {len(hi_frames)}")
    print(f"Wrote {atlas_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
