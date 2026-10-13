#!/usr/bin/env python3
"""Make a video spec-compliant (9:16 feed or generated profile).

    normalize_video.py <in> --profile feed|generated [--out <file>]
                       [--focus x,y] [--fit crop|pad|auto] [--start <s>] [--duration <s>]

Framing:
  crop  smart centre crop to 9:16 (default; --focus moves the crop window)
  pad   blurred-background pad, keeps the whole frame - use when a crop
        would cut the subject
  auto  crop unless the crop would discard more than --max-loss of the
        frame width/height, in which case pad

Trimming: clamped to the profile's duration window. A source longer than
max_duration_s is cut from --start; a source shorter than min_duration_s
is passed through with a warning (never looped - looping looks cheap).

All encode settings come from skills/creative-standards/references/specs.json.
Prints JSON. Exits non-zero on failure.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import specs as specs_mod  # noqa: E402
from probe import ProbeError, probe, run  # noqa: E402


class NormalizeError(RuntimeError):
    pass


def _crop_chain(src_w: int, src_h: int, target_w: int, target_h: int,
                focus: tuple[float, float] | None) -> tuple[str, float]:
    """Centre/focus crop to the target aspect. Returns (filter, fraction of frame lost)."""
    target_ratio = target_w / target_h
    if src_w / src_h > target_ratio:
        crop_w, crop_h = round(src_h * target_ratio), src_h
    else:
        crop_w, crop_h = src_w, round(src_w / target_ratio)
    crop_w -= crop_w % 2
    crop_h -= crop_h % 2

    fx, fy = focus if focus else (0.5, 0.5)
    x = min(max(round(src_w * fx - crop_w / 2), 0), src_w - crop_w)
    y = min(max(round(src_h * fy - crop_h / 2), 0), src_h - crop_h)

    lost = 1 - (crop_w * crop_h) / (src_w * src_h)
    chain = f"crop={crop_w}:{crop_h}:{x}:{y},scale={target_w}:{target_h}:flags=lanczos"
    return chain, lost


def _pad_chain(target_w: int, target_h: int) -> str:
    """Blurred, scaled copy of the frame behind a fully visible foreground."""
    return (
        f"split=2[bg][fg];"
        f"[bg]scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
        f"crop={target_w}:{target_h},boxblur=luma_radius=min(h\\,w)/20:luma_power=1,"
        f"eq=brightness=-0.06[bgb];"
        f"[fg]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease:flags=lanczos[fgs];"
        f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2"
    )


def normalize(src: str, profile_name: str, out: str | None = None,
              focus: tuple[float, float] | None = None, fit: str = "auto",
              start: float = 0.0, duration: float | None = None,
              max_loss: float = 0.4, specs_path: str | None = None) -> dict:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise NormalizeError("ffmpeg not found on PATH")

    spec = specs_mod.video_profile(profile_name, specs_path)
    meta = probe(src)
    if meta["kind"] != "video":
        raise NormalizeError(f"{src} is an image; use normalize_image.py")

    target_w, target_h = spec["width"], spec["height"]
    if out is None:
        stem = os.path.splitext(src)[0]
        out = f"{stem}_{profile_name}.{spec.get('container', 'mp4')}"
    container = spec.get("container", "mp4")
    ext = os.path.splitext(out)[1].lstrip(".").lower()
    if ext and ext != container:
        raise NormalizeError(
            f"--out ends in .{ext} but specs.json sets video.{profile_name}.container to "
            f"{container}; use .{container} or change the spec"
        )
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)

    # Framing
    crop_chain, lost = _crop_chain(meta["width"], meta["height"], target_w, target_h, focus)
    if fit == "crop":
        chosen, vf = "crop", crop_chain
    elif fit == "pad":
        chosen, vf = "pad", _pad_chain(target_w, target_h)
    else:
        chosen = "crop" if lost <= max_loss else "pad"
        vf = crop_chain if chosen == "crop" else _pad_chain(target_w, target_h)
    vf += f",fps={spec['fps']},setsar=1"

    # Trimming
    warnings = []
    src_duration = meta["duration_s"] or 0.0
    lo, hi = spec["min_duration_s"], spec["max_duration_s"]
    want = duration if duration is not None else min(max(src_duration - start, 0.0), hi)
    want = min(want, hi)
    if want <= 0:
        raise NormalizeError(f"--start {start}s is beyond the source duration {src_duration}s")
    if want < lo:
        warnings.append(
            f"output {round(want, 2)}s is under the {lo}s minimum for profile {profile_name}; "
            "not looped - find a longer source or accept the short cut"
        )

    # All inputs must precede output options, so the silent-audio source
    # (added when the clip has none) is declared up front.
    silent_audio = not meta["has_audio"]
    if silent_audio:
        warnings.append("source had no audio track; a silent one was added")

    def encode(target_video_kbps: int | None) -> dict:
        """One encode pass. CRF by default; bitrate-targeted when a size cap forces it."""
        cmd = [ffmpeg, "-y", "-loglevel", "error"]
        if start:
            cmd += ["-ss", str(start)]
        cmd += ["-i", src]
        if silent_audio:
            cmd += ["-f", "lavfi", "-i", f"anullsrc=r={spec['audio_sample_rate']}:cl=stereo"]
        cmd += ["-map", "0:v:0", "-map", "1:a:0" if silent_audio else "0:a:0"]
        cmd += ["-t", f"{want:.3f}", "-vf", vf]
        cmd += [
            "-c:v", spec["vcodec"],
            "-profile:v", spec["profile"],
            "-level", spec["level"],
            "-pix_fmt", spec["pix_fmt"],
            "-preset", spec["preset"],
        ]
        if target_video_kbps is None:
            cap = spec["max_bitrate_kbps"]
            cmd += ["-crf", str(spec["crf"]), "-maxrate", f"{cap}k", "-bufsize", f"{cap * 2}k"]
        else:
            cmd += ["-b:v", f"{target_video_kbps}k",
                    "-maxrate", f"{target_video_kbps}k",
                    "-bufsize", f"{target_video_kbps * 2}k"]
        cmd += [
            "-c:a", spec["acodec"],
            "-b:a", f"{spec['audio_bitrate_kbps']}k",
            "-ar", str(spec["audio_sample_rate"]),
            "-ac", "2",
        ]
        if spec.get("faststart"):
            cmd += ["-movflags", "+faststart"]
        cmd.append(out)
        run(cmd)
        return probe(out)

    result = encode(None)
    passes = 1

    # The Command Center caps file size, so overshooting means a rejected
    # upload. Re-encode against a bitrate computed from the size budget
    # rather than leaving the operator to guess at a lower CRF.
    max_mb = spec.get("max_size_mb")
    if max_mb and spec.get("enforce_max_size") and result["size_mb"] > max_mb:
        for headroom in (0.95, 0.88):
            budget_kbps = (max_mb * 8 * 1024) / want * headroom
            target = int(budget_kbps - spec["audio_bitrate_kbps"])
            if target < 500:
                break
            result = encode(target)
            passes += 1
            if result["size_mb"] <= max_mb:
                break
        if result["size_mb"] <= max_mb:
            warnings.append(
                f"first pass exceeded the {max_mb}MB cap; re-encoded at a size-targeted bitrate "
                f"({result['bitrate_kbps']} kbps, {result['size_mb']}MB)"
            )
        else:
            warnings.append(
                f"output {result['size_mb']}MB still exceeds the {max_mb}MB cap after {passes} passes; "
                "shorten the cut or pick a less detailed source"
            )

    # Real upscaling depends on the framing: a crop blows up a sub-region,
    # a pad only scales the frame to fit inside the target box.
    if chosen == "crop":
        crop_h = int(crop_chain.split("crop=")[1].split(",")[0].split(":")[1])
        upscale = target_h / crop_h
    else:
        upscale = min(target_w / meta["width"], target_h / meta["height"])
    notes = []
    if upscale > 1.05:
        message = (f"source {meta['width']}x{meta['height']} was upscaled {upscale:.2f}x to reach "
                   f"{target_w}x{target_h}")
        # The generated profile renders at 720x1280 on purpose and is always
        # upscaled to clear the >=1080x1920 minimum; that is expected, not a defect.
        (notes if spec.get("allow_upscale") else warnings).append(
            message if spec.get("allow_upscale") else message + "; expect softness"
        )

    if result["height"] < spec["height"] or result["width"] < spec["width"]:
        warnings.append(
            f"output {result['width']}x{result['height']} is below the required "
            f"{spec['width']}x{spec['height']} minimum"
        )

    return {
        "ok": not warnings,
        "input": meta,
        "output": result,
        "profile": profile_name,
        "fit": chosen,
        "crop_loss": round(lost, 3),
        "trim": {"start_s": start, "duration_s": round(want, 3)},
        "encode_passes": passes,
        "notes": notes,
        "warnings": warnings,
    }


def _parse_focus(raw: str | None) -> tuple[float, float] | None:
    if not raw:
        return None
    try:
        x, y = (float(v) for v in raw.split(","))
    except ValueError as exc:
        raise NormalizeError("--focus expects x,y as 0-1 floats, e.g. 0.5,0.35") from exc
    return x, y


def main() -> int:
    ap = argparse.ArgumentParser(description="Normalize a video to the feed spec.")
    ap.add_argument("input")
    ap.add_argument("--profile", required=True, choices=["feed", "generated"])
    ap.add_argument("--out")
    ap.add_argument("--focus", help="crop focus point as x,y in 0-1 (default centre)")
    ap.add_argument("--fit", default="auto", choices=["crop", "pad", "auto"])
    ap.add_argument("--start", type=float, default=0.0, help="trim start in seconds")
    ap.add_argument("--duration", type=float, help="output duration in seconds (clamped to the profile window)")
    ap.add_argument("--max-loss", type=float, default=0.4, help="crop loss above which --fit auto pads instead")
    ap.add_argument("--specs", help="override path to specs.json")
    args = ap.parse_args()

    try:
        print(json.dumps(normalize(args.input, args.profile, args.out, _parse_focus(args.focus),
                                   args.fit, args.start, args.duration, args.max_loss, args.specs), indent=2))
    except (NormalizeError, ProbeError, KeyError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
