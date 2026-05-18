#!/usr/bin/env python3
import json
import math
import random
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
CHAR_ROOT = ROOT / "art" / "characters" / "astra-mycelion"
VFX_ROOT = ROOT / "art" / "vfx" / "astra-mycelion"
OUT_ROOT = CHAR_ROOT / "game-ready"


def clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def trim_alpha(im: Image.Image):
    bbox = im.getchannel("A").getbbox()
    if bbox is None:
        return im, None
    return im.crop(bbox), bbox


def fit_to_canvas(im: Image.Image, canvas_size):
    trimmed, bbox = trim_alpha(im)
    canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    if bbox is None:
        return canvas, {"source_bounds": None, "trimmed_size": [0, 0], "paste_xy": [0, 0]}
    tw, th = trimmed.size
    scale = min(canvas_size[0] / tw, canvas_size[1] / th, 1.0)
    if scale < 1.0:
        trimmed = trimmed.resize((max(1, round(tw * scale)), max(1, round(th * scale))), Image.Resampling.LANCZOS)
        tw, th = trimmed.size
    x = (canvas_size[0] - tw) // 2
    y = (canvas_size[1] - th) // 2
    canvas.alpha_composite(trimmed, (x, y))
    return canvas, {"source_bounds": list(bbox), "trimmed_size": [tw, th], "paste_xy": [x, y]}


def grid_box(width, height, cols, rows, col, row):
    x0 = round(col * width / cols)
    x1 = round((col + 1) * width / cols)
    y0 = round(row * height / rows)
    y1 = round((row + 1) * height / rows)
    return x0, y0, x1, y1


def consecutive_segments(active):
    segments = []
    start = None
    for i, value in enumerate(active):
        if value and start is None:
            start = i
        if (not value or i == len(active) - 1) and start is not None:
            end = i if not value else i + 1
            segments.append([start, end])
            start = None
    return segments


def merge_close_segments(segments, max_gap=4):
    if not segments:
        return []
    merged = [segments[0]]
    for start, end in segments[1:]:
        if start - merged[-1][1] <= max_gap:
            merged[-1][1] = end
        else:
            merged.append([start, end])
    return merged


def detect_row_boxes(im: Image.Image, row_count: int):
    alpha = np.array(im.getchannel("A"))
    content_bbox = im.getchannel("A").getbbox()
    if content_bbox is None:
        return [[] for _ in range(row_count)]
    _, by0, _, by1 = content_bbox
    content_h = by1 - by0
    boxes_by_row = []

    for row in range(row_count):
        y0 = max(0, round(by0 + row * content_h / row_count) - 14)
        y1 = min(im.height, round(by0 + (row + 1) * content_h / row_count) + 14)
        band = alpha[y0:y1, :]
        best_segments = None
        best_score = -1
        for threshold in [3, 1, 8, 15]:
            active = band.sum(axis=0) > threshold
            segments = merge_close_segments(consecutive_segments(active), max_gap=5)
            segments = [s for s in segments if s[1] - s[0] > 8]
            score = len(segments)
            if score > best_score:
                best_score = score
                best_segments = segments
        row_boxes = []
        frame_count = max(1, len(best_segments or []))
        row_active = band > 8
        if not row_active.any():
            boxes_by_row.append(row_boxes)
            continue
        _, active_xs = np.where(row_active)
        row_x0 = max(0, int(active_xs.min()) - 10)
        row_x1 = min(im.width, int(active_xs.max()) + 1 + 10)
        row_w = row_x1 - row_x0

        for index in range(frame_count):
            x0 = round(row_x0 + index * row_w / frame_count)
            x1 = round(row_x0 + (index + 1) * row_w / frame_count)
            crop_alpha = alpha[y0:y1, x0:x1] > 8
            if not crop_alpha.any():
                continue
            ys, xs = np.where(crop_alpha)
            row_boxes.append((
                max(0, x0 + int(xs.min()) - 10),
                max(0, y0 + int(ys.min()) - 10),
                min(im.width, x0 + int(xs.max()) + 1 + 10),
                min(im.height, y0 + int(ys.max()) + 1 + 10),
            ))
        boxes_by_row.append(row_boxes)
    return boxes_by_row


def extract_hud():
    src = Image.open(CHAR_ROOT / "hud" / "astra_mycelion_hud_icons.png").convert("RGBA")
    out_dir = OUT_ROOT / "hud"
    clean_dir(out_dir)
    metadata = {}
    # Boxes are production crops from the generated UI sheet.
    crops = {
        "portrait_large": ((0, 20, 760, 1015), (768, 1024)),
        "portrait_square": ((780, 55, 1120, 390), (256, 256)),
        "minimap_marker": ((1250, 120, 1435, 330), (128, 128)),
        "health_core": ((725, 410, 930, 650), (128, 128)),
        "ability_shield": ((960, 410, 1185, 655), (128, 128)),
        "ability_teleport_glitch": ((1230, 405, 1510, 650), (128, 128)),
        "ability_gravity_flip": ((1050, 670, 1365, 980), (128, 128)),
    }
    for name, (box, canvas_size) in crops.items():
        normalized, qa = fit_to_canvas(src.crop(box), canvas_size)
        path = out_dir / f"astra_mycelion_{name}.png"
        normalized.save(path)
        metadata[name] = {"file": str(path.relative_to(ROOT)), "size": list(canvas_size), **qa}
    return metadata


def extract_vfx():
    frames_root = OUT_ROOT / "vfx" / "frames"
    atlas_root = OUT_ROOT / "vfx" / "atlases"
    clean_dir(frames_root)
    clean_dir(atlas_root)
    cell_size = (256, 256)
    metadata = {
        "cell_size": list(cell_size),
        "source": "procedural-raster",
        "concept_sheet": "art/vfx/astra-mycelion/astra_mycelion_ability_vfx_sheet.png",
        "animations": {},
    }
    all_frames = []

    animations = [
        ("shield_activation", 12, 14, False, draw_shield_frame),
        ("teleport_glitch", 12, 14, False, draw_teleport_frame),
        ("gravity_flip", 12, 12, False, draw_gravity_frame),
        ("parry_impact", 12, 16, False, draw_parry_frame),
    ]

    for anim_name, frame_count, fps, loop, drawer in animations:
        anim_dir = frames_root / anim_name
        anim_dir.mkdir(parents=True, exist_ok=True)
        anim_frames = []
        for idx in range(frame_count):
            normalized = drawer(idx, frame_count, cell_size)
            frame_path = anim_dir / f"{anim_name}_{idx:03d}.png"
            normalized.save(frame_path)
            anim_frames.append({
                "index": idx,
                "file": str(frame_path.relative_to(ROOT)),
                "duration": round(1 / fps, 6),
            })
            all_frames.append((f"{anim_name}/{frame_path.name}", normalized))
        metadata["animations"][anim_name] = {"fps": fps, "loop": loop, "frames": anim_frames}

    cols = 8
    rows = (len(all_frames) + cols - 1) // cols
    atlas = Image.new("RGBA", (cols * cell_size[0], rows * cell_size[1]), (0, 0, 0, 0))
    atlas_frames = []
    for i, (name, frame) in enumerate(all_frames):
        x = (i % cols) * cell_size[0]
        y = (i // cols) * cell_size[1]
        atlas.alpha_composite(frame, (x, y))
        atlas_frames.append({"name": name, "x": x, "y": y, "w": cell_size[0], "h": cell_size[1]})
    atlas_path = atlas_root / "astra_mycelion_vfx_atlas.png"
    atlas.save(atlas_path)
    metadata["atlas"] = {"file": str(atlas_path.relative_to(ROOT)), "frames": atlas_frames}
    return metadata


def glow_layer(size, draw_fn, blur=8, alpha=150):
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw_fn(draw)
    glow = layer.filter(ImageFilter.GaussianBlur(blur))
    glow.putalpha(glow.getchannel("A").point(lambda v: min(alpha, v)))
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    out.alpha_composite(glow)
    out.alpha_composite(layer)
    return out


def draw_hex_grid(draw, cx, cy, radius, color):
    hex_r = 13
    for y in range(int(cy - radius), int(cy + radius), int(hex_r * 1.6)):
        for x in range(int(cx - radius), int(cx + radius), int(hex_r * 1.8)):
            if (x - cx) ** 2 + (y - cy) ** 2 > radius ** 2:
                continue
            pts = []
            for i in range(6):
                a = math.pi / 3 * i + math.pi / 6
                pts.append((x + math.cos(a) * hex_r, y + math.sin(a) * hex_r))
            draw.line(pts + [pts[0]], fill=color, width=1)


def draw_shield_frame(idx, count, size):
    w, h = size
    cx, cy = w // 2, h // 2 + 8
    t = idx / (count - 1)
    radius = 24 + 86 * math.sin(t * math.pi / 2)
    alpha = int(220 * (1 - max(0, t - 0.72) / 0.28))

    def base(draw):
        col = (255, 224, 54, alpha)
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=col, width=4)
        draw.ellipse((cx - radius - 8, cy - radius - 8, cx + radius + 8, cy + radius + 8), outline=(255, 179, 33, max(45, alpha // 2)), width=2)
        draw_hex_grid(draw, cx, cy, radius * 0.82, (255, 230, 80, max(35, alpha // 3)))
        for n in range(10):
            a = n * math.tau / 10 + t * 2.4
            px = cx + math.cos(a) * (radius + 8)
            py = cy + math.sin(a) * (radius + 8)
            draw.polygon([(px, py), (px + math.cos(a) * 9, py + math.sin(a) * 9), (px + math.cos(a + 1.9) * 5, py + math.sin(a + 1.9) * 5)], fill=(141, 40, 71, max(35, alpha // 2)))

    return glow_layer(size, base, blur=10, alpha=150)


def draw_teleport_frame(idx, count, size):
    w, h = size
    cx, cy = w // 2, h // 2
    t = idx / (count - 1)
    rng = random.Random(7300 + idx)
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    spread = 18 + 82 * abs(math.sin(t * math.pi))
    for i in range(26):
        x = cx + rng.uniform(-spread, spread)
        y = cy + rng.uniform(-80, 80)
        length = rng.uniform(14, 52) * (1 - abs(t - 0.5) * 0.7)
        color = rng.choice([(255, 179, 33, 180), (141, 40, 71, 150), (125, 92, 255, 130), (216, 209, 189, 140)])
        draw.line((x - length / 2, y, x + length / 2, y + rng.uniform(-4, 4)), fill=color, width=rng.randint(1, 3))
    for i in range(12):
        x = cx + rng.uniform(-spread, spread)
        y = cy + rng.uniform(-70, 70)
        r = rng.uniform(3, 8)
        pts = [(x, y - r), (x + r * 0.9, y + r), (x - r * 0.7, y + r * 0.6)]
        draw.polygon(pts, fill=(42, 44, 49, 180), outline=(255, 179, 33, 150))
    return im.filter(ImageFilter.GaussianBlur(0.2))


def draw_gravity_frame(idx, count, size):
    w, h = size
    cx, cy = w // 2, h // 2
    t = idx / (count - 1)
    direction = -1 if idx < count / 2 else 1
    rot = t * math.tau

    def base(draw):
        for r, width in [(88, 4), (66, 3), (45, 2)]:
            box = (cx - r, cy - r, cx + r, cy + r)
            draw.arc(box, int(math.degrees(rot)), int(math.degrees(rot + math.pi * 1.35)), fill=(255, 224, 54, 190), width=width)
            draw.arc(box, int(math.degrees(rot + math.pi)), int(math.degrees(rot + math.pi * 2.1)), fill=(141, 40, 71, 120), width=max(1, width - 1))
        for n in range(3):
            y = cy + direction * (24 - n * 22)
            pts = [(cx, y + direction * 15), (cx - 16, y - direction * 8), (cx + 16, y - direction * 8)]
            draw.polygon(pts, fill=(255, 224, 54, 210))

    return glow_layer(size, base, blur=7, alpha=130)


def draw_parry_frame(idx, count, size):
    w, h = size
    cx, cy = w // 2, h // 2
    t = idx / (count - 1)
    rng = random.Random(9100 + idx)
    radius = 8 + t * 100
    fade = int(255 * (1 - t))

    def base(draw):
        points = []
        for n in range(24):
            a = n * math.tau / 24
            r = radius * (1.0 if n % 2 == 0 else 0.35)
            points.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
        draw.polygon(points, outline=(255, 224, 54, max(30, fade)), fill=(255, 179, 33, max(0, fade // 5)))
        for _ in range(18):
            a = rng.random() * math.tau
            r0 = radius * rng.uniform(0.25, 0.7)
            r1 = radius * rng.uniform(0.8, 1.25)
            draw.line((cx + math.cos(a) * r0, cy + math.sin(a) * r0, cx + math.cos(a) * r1, cy + math.sin(a) * r1), fill=(255, 224, 54, max(25, fade)), width=2)
        for _ in range(10):
            a = rng.random() * math.tau
            r = radius * rng.uniform(0.5, 1.2)
            x = cx + math.cos(a) * r
            y = cy + math.sin(a) * r
            draw.polygon([(x, y), (x + 7, y + 2), (x + 2, y + 9)], fill=(141, 40, 71, max(20, fade // 2)))

    return glow_layer(size, base, blur=8, alpha=150)


def main():
    metadata_dir = OUT_ROOT / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        "hud": extract_hud(),
        "vfx": extract_vfx(),
    }
    out = metadata_dir / "astra_mycelion_secondary_assets.json"
    out.write_text(json.dumps(metadata, indent=2))
    print(f"Wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
