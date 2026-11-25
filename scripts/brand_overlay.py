#!/usr/bin/env python3
"""Composite the real logo and copy onto a generated scene.

    brand_overlay.py <scene> --layout <layout.json> --out <final.png> [--overlay <check.png>]

The scene comes from an image model and must be text-free and logo-free
(rule 3). Everything a brand depends on - logo, headline, CTA - is placed
here, deterministically, from files and strings the agent puts in the layout.

layout.json, in 1080x1920 canvas pixels (the safe_area profile's canvas):

    {"elements": [
      {"type": "image", "label": "logo", "src": "brands/uber/logo/logo.png",
       "slot": [x0, y0, x1, y1], "align": "center", "tint": "#FFFFFF"},
      {"type": "text", "label": "headline", "text": "GO ANYWHERE.",
       "font": "path/to/font.ttf", "size": 96, "color": "#FFFFFF",
       "slot": [x0, y0, x1, y1], "align": "center", "group": "headline",
       "shadow": true, "button": {"color": "#000000", "pad": 24}}
    ]}

Text elements sharing a `group` are set at one size, the smallest any of
them needed. `tint` recolours a single-colour logo (e.g. white on dark).

A slot is where the agent wants the element; the element is fitted inside
it (images keep their aspect, text shrinks to fit, never below min_font_px).
Every slot must sit inside the safe area less min_padding_px, so the layout
is built inside-out as Safe Area Skill v2.1 s3 requires. Text bounds are
measured from the rendered glyphs, not estimated, so the safe-area check
that runs on the result is exact.

Exit codes: 0 pass, 2 the check failed, 1 error. Prints JSON.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_safe_area  # noqa: E402
import specs as specs_mod  # noqa: E402
from probe import ProbeError, probe, run  # noqa: E402

BBOX = re.compile(r"x1:(\d+) x2:(\d+) y1:(\d+) y2:(\d+)")


class OverlayError(RuntimeError):
    pass


def _ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise OverlayError("ffmpeg not found on PATH")
    return ffmpeg


def _fpath(path: str) -> str:
    """A file path as a quoted filtergraph value. Windows drive colons must be escaped."""
    return "'" + os.path.abspath(path).replace("\\", "/").replace(":", "\\:") + "'"


def _drawtext(el: dict, textfile: str, size: int, x: int, y: int, measure: bool = False) -> str:
    color = "white" if measure else el.get("color", "white")
    parts = [f"drawtext=fontfile={_fpath(el['font'])}", f"textfile={_fpath(textfile)}",
             f"fontsize={size}", f"fontcolor={color}", f"x={x}", f"y={y}"]
    button = el.get("button")
    if button:
        parts += ["box=1", f"boxcolor={'white' if measure else button.get('color', 'black')}",
                  f"boxborderw={int(button.get('pad', 24))}"]
    if el.get("shadow") and not measure:
        off = max(2, size // 40)
        parts += ["shadowcolor=black@0.55", f"shadowx={off}", f"shadowy={off}"]
    return ":".join(parts)


def _measure(el: dict, textfile: str, size: int) -> tuple[int, int, int, int]:
    """Rendered bounds of the text (and its button) relative to the drawtext origin."""
    pad = int(el.get("button", {}).get("pad", 0)) if el.get("button") else 0
    origin = size + pad
    w = origin * 2 + size * max(1, len(el["text"]))
    h = origin * 2 + size * 2
    proc = subprocess.run(
        [_ffmpeg(), "-v", "info", "-f", "lavfi", "-i", f"color=c=black:s={w}x{h}", "-frames:v", "1",
         "-vf", f"{_drawtext(el, textfile, size, origin, origin, measure=True)},bbox",
         "-f", "null", "-"],
        capture_output=True, text=True)
    m = BBOX.search(proc.stderr)
    if proc.returncode != 0 or not m:
        raise OverlayError(f"could not measure text {el.get('label')!r}: {proc.stderr.strip()[-300:]}")
    x1, x2, y1, y2 = (int(v) for v in m.groups())
    return x1 - origin, y1 - origin, x2 - origin + 1, y2 - origin + 1


def _aligned(align: str, s0: float, s1: float, length: float) -> float:
    if align in ("left", "top"):
        return s0
    if align in ("right", "bottom"):
        return s1 - length
    return s0 + (s1 - s0 - length) / 2


def _check_slot(el: dict, safe: list[int], pad: int) -> list[int]:
    try:
        x0, y0, x1, y1 = (int(round(float(v))) for v in el["slot"])
    except (KeyError, TypeError, ValueError) as exc:
        raise OverlayError(f"element {el.get('label')!r}: slot must be [x0, y0, x1, y1]") from exc
    sx0, sy0, sx1, sy1 = safe[0] + pad, safe[1] + pad, safe[2] - pad, safe[3] - pad
    if x1 <= x0 or y1 <= y0:
        raise OverlayError(f"element {el.get('label')!r}: slot has no area")
    if x0 < sx0 or y0 < sy0 or x1 > sx1 or y1 > sy1:
        raise OverlayError(
            f"element {el.get('label')!r}: slot {[x0, y0, x1, y1]} leaves the padded safe area "
            f"{[sx0, sy0, sx1, sy1]}; move or shrink the slot")
    return [x0, y0, x1, y1]


def _place_text(el: dict, slot: list[int], textfile: str, min_font: int) -> dict:
    sw, sh = slot[2] - slot[0], slot[3] - slot[1]
    size = int(el.get("size", 72))
    for _ in range(12):
        ox0, oy0, ox1, oy1 = _measure(el, textfile, size)
        w, h = ox1 - ox0, oy1 - oy0
        if w <= sw and h <= sh:
            break
        size = min(size - 1, int(size * min(sw / w, sh / h)))
        if size < min_font:
            raise OverlayError(
                f"text {el.get('label')!r} does not fit its {sw}x{sh} slot above {min_font}px "
                f"(min_font_px); split it into lines or shorten it")
    else:
        raise OverlayError(f"text {el.get('label')!r}: could not converge on a size that fits")

    gx0 = round(_aligned(el.get("align", "center"), slot[0], slot[2], w))
    gy0 = round(_aligned(el.get("valign", "center"), slot[1], slot[3], h))
    return {"size": size, "x": gx0 - ox0, "y": gy0 - oy0, "box": [gx0, gy0, gx0 + w, gy0 + h],
            "shrunk": size < int(el.get("size", 72))}


def _place_image(el: dict, slot: list[int]) -> dict:
    if not os.path.isfile(el.get("src", "")):
        raise OverlayError(f"element {el.get('label')!r}: src {el.get('src')!r} not found")
    if el["src"].lower().endswith(".svg"):
        raise OverlayError(f"element {el.get('label')!r}: ffmpeg cannot render SVG; use the kit's PNG")
    meta = probe(el["src"])
    sw, sh = slot[2] - slot[0], slot[3] - slot[1]
    scale = min(sw / meta["width"], sh / meta["height"])
    w, h = max(1, int(meta["width"] * scale)), max(1, int(meta["height"] * scale))
    x = round(_aligned(el.get("align", "center"), slot[0], slot[2], w))
    y = round(_aligned(el.get("valign", "center"), slot[1], slot[3], h))
    return {"w": w, "h": h, "x": x, "y": y, "box": [x, y, x + w, y + h], "upscaled": scale > 1.0}


def compose(scene: str, layout_path: str, out: str, overlay: str | None = None,
            profile_name: str = "feed", specs_path: str | None = None) -> dict:
    spec = specs_mod.safe_area_profile(profile_name, specs_path)
    geo = check_safe_area.geometry(spec)
    cw, ch = geo["canvas"]
    with open(layout_path, encoding="utf-8") as fh:
        layout = json.load(fh)
    elements = layout.get("elements", [])
    if not elements:
        raise OverlayError("layout has no elements")

    probe(scene)  # fail early on an unreadable scene
    tmp = tempfile.mkdtemp(prefix="brand_overlay_")
    try:
        placed, warnings = [], []
        for i, el in enumerate(elements):
            slot = _check_slot(el, geo["safe_area"], spec["min_padding_px"])
            if el.get("type") == "text":
                for key in ("text", "font"):
                    if not el.get(key):
                        raise OverlayError(f"text element {el.get('label')!r} needs {key!r}")
                if not os.path.isfile(el["font"]):
                    raise OverlayError(f"font {el['font']!r} not found")
                textfile = os.path.join(tmp, f"text{i}.txt")
                with open(textfile, "w", encoding="utf-8") as fh:
                    fh.write(el["text"])
                p = _place_text(el, slot, textfile, spec["min_font_px"])
                p["textfile"] = textfile
                if p["shrunk"]:
                    warnings.append(f"{el.get('label')}: shrunk from {el.get('size', 72)}px to {p['size']}px to fit")
            elif el.get("type") == "image":
                p = _place_image(el, slot)
                if p["upscaled"]:
                    warnings.append(f"{el.get('label')}: source is smaller than its slot and was upscaled")
            else:
                raise OverlayError(f"element {el.get('label')!r}: type must be text or image")
            placed.append((el, p))

        # Lines in the same group share one size: the smallest any of them needed to fit.
        # Otherwise a three-line headline comes out 84/79/72px, which reads as a mistake.
        groups: dict[str, int] = {}
        for el, p in placed:
            if el["type"] == "text" and el.get("group"):
                groups[el["group"]] = min(groups.get(el["group"], p["size"]), p["size"])
        for i, (el, p) in enumerate(placed):
            g = el.get("group")
            if el["type"] == "text" and g and p["size"] != groups[g]:
                slot = _check_slot(el, geo["safe_area"], spec["min_padding_px"])
                q = _place_text({**el, "size": groups[g]}, slot, p["textfile"], spec["min_font_px"])
                placed[i] = (el, {**q, "textfile": p["textfile"], "shrunk": True})
        if groups:
            warnings = [w for w in warnings if not any(
                w.startswith(f"{el.get('label')}:") for el, _ in placed if el.get("group"))]
            warnings += [f"group {g!r}: all lines set to {s}px" for g, s in groups.items()]

        inputs = ["-i", scene]
        graph = [f"[0:v]scale={cw}:{ch}:force_original_aspect_ratio=increase:flags=lanczos,"
                 f"crop={cw}:{ch}[v0]"]
        last, n_in = "v0", 1
        for el, p in placed:
            if el["type"] != "image":
                continue
            inputs += ["-i", el["src"]]
            tint = ""
            if el.get("tint"):
                # Single-colour marks only (a black wordmark shown white on a dark scene).
                # Recolours every pixel and keeps the alpha, so it would flatten a multi-colour logo.
                hexcol = el["tint"].lstrip("#")
                if not re.fullmatch(r"[0-9A-Fa-f]{6}", hexcol):
                    raise OverlayError(f"element {el.get('label')!r}: tint must be #RRGGBB")
                r, g, b = (int(hexcol[i:i + 2], 16) for i in (0, 2, 4))
                tint = f",format=rgba,lutrgb=r={r}:g={g}:b={b}"
            graph.append(f"[{n_in}:v]scale={p['w']}:{p['h']}:flags=lanczos{tint}[im{n_in}]")
            graph.append(f"[{last}][im{n_in}]overlay={p['x']}:{p['y']}:format=auto[v{n_in}]")
            last, n_in = f"v{n_in}", n_in + 1
        texts = [_drawtext(el, p["textfile"], p["size"], p["x"], p["y"])
                 for el, p in placed if el["type"] == "text"]
        graph.append(f"[{last}]" + (",".join(texts) if texts else "null") + "[out]")

        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        run([_ffmpeg(), "-y", "-v", "error", *inputs, "-frames:v", "1",
             "-filter_complex", ";".join(graph), "-map", "[out]", out])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    boxes_path = os.path.splitext(out)[0] + "_boxes.json"
    with open(boxes_path, "w", encoding="utf-8") as fh:
        json.dump({"elements": [{"label": el.get("label", "?"), "box": p["box"], "critical": True}
                                for el, p in placed]}, fh, indent=2)
    result = check_safe_area.check(out, boxes_path, overlay, profile_name, specs_path)

    return {
        "scene": scene,
        "output": out,
        "boxes": boxes_path,
        "elements": [{"label": el.get("label", "?"), "type": el["type"], "box": p["box"],
                      **({"size": p["size"]} if el["type"] == "text" else {})} for el, p in placed],
        "pass": result["pass"],
        "failures": result["failures"],
        "warnings": warnings + result["warnings"],
        "overlay": overlay,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Composite real logo and copy onto a generated scene.")
    ap.add_argument("scene")
    ap.add_argument("--layout", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--overlay", help="also write the safe-area check overlay here")
    ap.add_argument("--profile", default="feed")
    ap.add_argument("--specs", help="override path to specs.json")
    args = ap.parse_args()

    try:
        result = compose(args.scene, args.layout, args.out, args.overlay, args.profile, args.specs)
    except (OverlayError, check_safe_area.CheckError, ProbeError, KeyError, OSError,
            json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0 if result["pass"] else 2


if __name__ == "__main__":
    sys.exit(main())
