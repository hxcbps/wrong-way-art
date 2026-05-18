#!/usr/bin/env python3
import json
import math
import shutil
from pathlib import Path

from PIL import Image
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "manifests" / "astra_mycelion_gameplay_manifest.json"
OUT_ROOT = ROOT / "art" / "characters" / "astra-mycelion" / "game-ready"
FRAMES_ROOT = OUT_ROOT / "frames"
ATLASES_ROOT = OUT_ROOT / "atlases"
METADATA_ROOT = OUT_ROOT / "metadata"
QA_ROOT = OUT_ROOT / "qa"


def clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def grid_box(content_bbox, image_size, cols: int, rows: int, col: int, row: int, pad_x=8, pad_y=8):
    bx0, by0, bx1, by1 = content_bbox
    width = bx1 - bx0
    height = by1 - by0
    image_w, image_h = image_size
    x0 = round(bx0 + col * width / cols) - pad_x
    x1 = round(bx0 + (col + 1) * width / cols) + pad_x
    y0 = round(by0 + row * height / rows) - pad_y
    y1 = round(by0 + (row + 1) * height / rows) + pad_y
    return max(0, x0), max(0, y0), min(image_w, x1), min(image_h, y1)


def remove_edge_bleed(cell: Image.Image) -> Image.Image:
    """Remove small alpha islands introduced by overlapping neighboring grid crops."""
    arr = np.array(cell)
    mask = arr[:, :, 3] > 8
    height, width = mask.shape
    visited = np.zeros_like(mask, dtype=bool)
    components = []

    for y in range(height):
        for x in range(width):
            if not mask[y, x] or visited[y, x]:
                continue
            stack = [(x, y)]
            visited[y, x] = True
            coords = []
            while stack:
                cx, cy = stack.pop()
                coords.append((cx, cy))
                for ny in range(max(0, cy - 1), min(height, cy + 2)):
                    for nx in range(max(0, cx - 1), min(width, cx + 2)):
                        if not visited[ny, nx] and mask[ny, nx]:
                            visited[ny, nx] = True
                            stack.append((nx, ny))
            xs = [c[0] for c in coords]
            ys = [c[1] for c in coords]
            components.append({
                "coords": coords,
                "area": len(coords),
                "bbox": (min(xs), min(ys), max(xs) + 1, max(ys) + 1),
            })

    if not components:
        return cell

    largest = max(c["area"] for c in components)
    remove = []
    for comp in components:
        x0, y0, x1, y1 = comp["bbox"]
        touches_side = x0 <= 1 or x1 >= width - 1
        touches_top = y0 <= 1
        # Do not treat bottom contact as bleed; platformer feet and impacts belong there.
        is_small = comp["area"] < largest * 0.28
        is_sliver = (x1 - x0) <= 28 or (y1 - y0) <= 20
        if (touches_side or touches_top) and is_small and is_sliver:
            remove.append(comp)

    if not remove:
        return cell

    cleaned = arr.copy()
    for comp in remove:
        for x, y in comp["coords"]:
            cleaned[y, x, 3] = 0
    return Image.fromarray(cleaned, "RGBA")


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


def detect_row_frame_boxes(im: Image.Image, rows: int, expected_cols: int, content_bbox):
    alpha = np.array(im.getchannel("A"))
    boxes_by_row = []
    bx0, by0, bx1, by1 = content_bbox
    content_h = by1 - by0
    max_needed_by_row = [expected_cols for _ in range(rows)]

    for row in range(rows):
        y0 = max(0, round(by0 + row * content_h / rows) - 10)
        y1 = min(im.height, round(by0 + (row + 1) * content_h / rows) + 10)
        band = alpha[y0:y1, :]
        best_segments = None
        best_score = 10**9

        for threshold in [3, 1, 8, 15]:
            active = band.sum(axis=0) > threshold
            segments = consecutive_segments(active)
            segments = merge_close_segments(segments, max_gap=4)
            segments = [s for s in segments if s[1] - s[0] > 4]
            score = abs(len(segments) - max_needed_by_row[row])
            if len(segments) >= max_needed_by_row[row]:
                score -= 0.25
            if score < best_score:
                best_score = score
                best_segments = segments

        row_boxes = []
        for x0, x1 in best_segments or []:
            crop_alpha = alpha[y0:y1, x0:x1] > 8
            if not crop_alpha.any():
                continue
            ys, xs = np.where(crop_alpha)
            tight_x0 = max(0, x0 + int(xs.min()) - 8)
            tight_x1 = min(im.width, x0 + int(xs.max()) + 1 + 8)
            tight_y0 = max(0, y0 + int(ys.min()) - 8)
            tight_y1 = min(im.height, y0 + int(ys.max()) + 1 + 8)
            row_boxes.append((tight_x0, tight_y0, tight_x1, tight_y1))

        boxes_by_row.append(row_boxes)

    return boxes_by_row


def trim_alpha(im: Image.Image):
    alpha = im.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        return im, None
    return im.crop(bbox), bbox


def normalize_frame(cell: Image.Image, target_size, pivot):
    target_w, target_h = target_size
    pivot_x, pivot_y = pivot
    trimmed, bbox = trim_alpha(cell)
    canvas = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))

    if bbox is None:
        return canvas, {
            "empty": True,
            "source_bounds": None,
            "trimmed_size": [0, 0],
            "paste_xy": [0, 0],
        }

    tw, th = trimmed.size
    paste_x = int(round(pivot_x - tw / 2))
    paste_y = int(round(pivot_y - th))

    # Keep oversized VFX frames visible inside the normalized canvas.
    if tw > target_w:
        scale = target_w / tw
        new_size = (target_w, max(1, int(round(th * scale))))
        trimmed = trimmed.resize(new_size, Image.Resampling.LANCZOS)
        tw, th = trimmed.size
        paste_x = 0
        paste_y = int(round(pivot_y - th))
    if th > target_h:
        scale = target_h / th
        new_size = (max(1, int(round(tw * scale))), target_h)
        trimmed = trimmed.resize(new_size, Image.Resampling.LANCZOS)
        tw, th = trimmed.size
        paste_x = int(round(pivot_x - tw / 2))
        paste_y = 0

    paste_x = max(0, min(target_w - tw, paste_x))
    paste_y = max(0, min(target_h - th, paste_y))
    canvas.alpha_composite(trimmed, (paste_x, paste_y))
    return canvas, {
        "empty": False,
        "source_bounds": list(bbox),
        "trimmed_size": [tw, th],
        "paste_xy": [paste_x, paste_y],
    }


def pack_atlas(frames, cell_size):
    frame_count = len(frames)
    cols = min(8, max(1, math.ceil(math.sqrt(frame_count))))
    rows = math.ceil(frame_count / cols)
    atlas = Image.new("RGBA", (cols * cell_size[0], rows * cell_size[1]), (0, 0, 0, 0))
    rects = []
    for i, (name, im) in enumerate(frames):
        col = i % cols
        row = i // cols
        x = col * cell_size[0]
        y = row * cell_size[1]
        atlas.alpha_composite(im, (x, y))
        rects.append({"name": name, "x": x, "y": y, "w": cell_size[0], "h": cell_size[1]})
    return atlas, rects


def make_contact_sheet(frames, cell_size, label_height=18):
    cols = min(8, max(1, math.ceil(math.sqrt(len(frames)))))
    rows = math.ceil(len(frames) / cols)
    sheet = Image.new("RGBA", (cols * cell_size[0], rows * (cell_size[1] + label_height)), (18, 18, 18, 255))
    for i, (name, im) in enumerate(frames):
        col = i % cols
        row = i // cols
        x = col * cell_size[0]
        y = row * (cell_size[1] + label_height)
        # checker backing makes transparency readable in QA.
        backing = Image.new("RGBA", cell_size, (32, 32, 32, 255))
        for cy in range(0, cell_size[1], 16):
            for cx in range(0, cell_size[0], 16):
                if (cx // 16 + cy // 16) % 2 == 0:
                    Image.Image.paste(backing, (48, 48, 48, 255), (cx, cy, cx + 16, cy + 16))
        sheet.alpha_composite(backing, (x, y + label_height))
        sheet.alpha_composite(im, (x, y + label_height))
    return sheet


def main():
    data = json.loads(MANIFEST.read_text())
    target_size = tuple(data["target_cell_size"])
    pivot = tuple(data["pivot_pixels"])

    for path in [FRAMES_ROOT, ATLASES_ROOT, METADATA_ROOT, QA_ROOT]:
        clean_dir(path)

    all_metadata = {
        "character": data["character"],
        "display_name": data["display_name"],
        "cell_size": list(target_size),
        "pivot_pixels": list(pivot),
        "pivot_normalized_unity": data["pivot_normalized_unity"],
        "animations": {},
        "atlases": {},
        "qa": {"warnings": []},
    }

    for sheet in data["sheets"]:
        sheet_id = sheet["id"]
        src = ROOT / sheet["path"]
        im = Image.open(src).convert("RGBA")
        content_bbox = im.getchannel("A").getbbox()
        if content_bbox is None:
            raise ValueError(f"Sheet has no visible pixels: {src}")
        detected_boxes = detect_row_frame_boxes(im, sheet["rows"], sheet["columns"], content_bbox)
        all_metadata["qa"].setdefault("detected_rows", {})[sheet_id] = [
            {"row": index, "detected_frames": len(row_boxes)}
            for index, row_boxes in enumerate(detected_boxes)
        ]
        sheet_frames = []
        sheet_frame_root = FRAMES_ROOT / sheet_id
        sheet_frame_root.mkdir(parents=True, exist_ok=True)

        for anim in sheet["animations"]:
            anim_name = anim["name"]
            anim_dir = sheet_frame_root / anim_name
            anim_dir.mkdir(parents=True, exist_ok=True)
            anim_frames = []
            for idx in range(anim["frames"]):
                col = anim["start_col"] + idx
                row = anim["row"]
                row_boxes = detected_boxes[row]
                if col < len(row_boxes):
                    box = row_boxes[col]
                else:
                    box = grid_box(content_bbox, im.size, sheet["columns"], sheet["rows"], col, row)
                    all_metadata["qa"]["warnings"].append(
                        f"Used fallback grid crop: {sheet_id}/{anim_name}/{idx}"
                    )
                cell = remove_edge_bleed(im.crop(box))
                normalized, qa = normalize_frame(cell, target_size, pivot)
                frame_name = f"{anim_name}_{idx:03d}.png"
                rel_frame = anim_dir / frame_name
                normalized.save(rel_frame)
                atlas_frame_name = f"{sheet_id}/{anim_name}/{frame_name}"
                sheet_frames.append((atlas_frame_name, normalized))
                anim_frames.append({
                    "index": idx,
                    "file": str(rel_frame.relative_to(ROOT)),
                    "duration": round(1 / anim["fps"], 6),
                    "source_grid": {"row": row, "column": col, "box": list(box)},
                    **qa,
                })
                if qa["empty"]:
                    all_metadata["qa"]["warnings"].append(f"Empty frame: {sheet_id}/{anim_name}/{idx}")

            all_metadata["animations"][anim_name] = {
                "sheet": sheet_id,
                "fps": anim["fps"],
                "loop": anim["loop"],
                "frames": anim_frames,
            }

        atlas, rects = pack_atlas(sheet_frames, target_size)
        atlas_path = ATLASES_ROOT / f"astra_mycelion_{sheet['output_prefix']}_atlas.png"
        atlas.save(atlas_path)
        all_metadata["atlases"][sheet_id] = {
            "file": str(atlas_path.relative_to(ROOT)),
            "frames": rects,
        }

        contact = make_contact_sheet(sheet_frames, target_size)
        contact_path = QA_ROOT / f"{sheet_id}_contact_sheet.png"
        contact.save(contact_path)

    metadata_path = METADATA_ROOT / "astra_mycelion_animations.json"
    metadata_path.write_text(json.dumps(all_metadata, indent=2))

    unity_path = METADATA_ROOT / "astra_mycelion_unity_import.json"
    unity_path.write_text(json.dumps({
        "pixels_per_unit": 100,
        "sprite_mode": "multiple",
        "pivot": data["pivot_normalized_unity"],
        "metadata": "Use atlas frame rectangles from astra_mycelion_animations.json."
    }, indent=2))

    godot_path = METADATA_ROOT / "astra_mycelion_godot_spriteframes.json"
    godot_path.write_text(json.dumps({
        "type": "SpriteFrames-import-plan",
        "cell_size": list(target_size),
        "pivot_pixels": list(pivot),
        "animations": {
            name: {
                "fps": anim["fps"],
                "loop": anim["loop"],
                "frames": [frame["file"] for frame in anim["frames"]]
            }
            for name, anim in all_metadata["animations"].items()
        }
    }, indent=2))

    print(f"Wrote {metadata_path.relative_to(ROOT)}")
    print(f"Frames: {sum(len(a['frames']) for a in all_metadata['animations'].values())}")
    print(f"Warnings: {len(all_metadata['qa']['warnings'])}")


if __name__ == "__main__":
    main()
