#!/usr/bin/env python3
"""Phase 0 tests. No network, no LLM calls.

    python3 tests/make_samples.py && python3 -m pytest tests/ -q
    (or: python3 tests/test_scripts.py  - runs the same checks without pytest)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SAMPLES = os.path.join(HERE, "samples")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import normalize_image  # noqa: E402
import normalize_video  # noqa: E402
import specs as specs_mod  # noqa: E402
from probe import probe  # noqa: E402


def sample(name: str) -> str:
    path = os.path.join(SAMPLES, name)
    if not os.path.isfile(path):
        raise SystemExit(f"missing fixture {path}; run: python3 tests/make_samples.py")
    return path


def test_specs_load():
    s = specs_mod.load()
    assert specs_mod.video_profile("feed")["aspect"] == "9:16"
    assert specs_mod.video_profile("generated")["aspect"] == "9:16"
    assert specs_mod.image_profile("mission")["aspect"] == "1:1"
    assert s["video"]["feed"]["min_duration_s"] < s["video"]["feed"]["max_duration_s"]


def test_probe_reads_video():
    meta = probe(sample("landscape_1080p.mp4"))
    assert meta["kind"] == "video"
    assert (meta["width"], meta["height"]) == (1920, 1080)
    assert meta["aspect"] == "16:9"
    assert meta["is_vertical"] is False
    assert meta["container"] == "mp4"
    assert meta["has_audio"] is True


def test_probe_distinguishes_images():
    meta = probe(sample("small.png"))
    assert meta["kind"] == "image"
    assert meta["duration_s"] is None
    assert meta["aspect"] == "4:3"


def test_probe_rejects_missing_file():
    try:
        probe("/tmp/definitely-not-here.mp4")
    except Exception as exc:
        assert "no such file" in str(exc)
    else:
        raise AssertionError("expected ProbeError")


def test_vertical_source_crops_without_loss():
    spec = specs_mod.video_profile("feed")
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "v.mp4")
        r = normalize_video.normalize(sample("vertical_1080x1920.mp4"), "feed", out)
        assert r["fit"] == "crop", "a native 9:16 source must crop, never pad"
        assert r["crop_loss"] < 0.01
        assert r["ok"] is True, r["warnings"]
        assert (r["output"]["width"], r["output"]["height"]) == (spec["width"], spec["height"])
        assert r["output"]["codec"] == "h264"
        assert r["output"]["pix_fmt"] == spec["pix_fmt"]
        assert r["output"]["container"] == spec["container"]


def test_landscape_source_pads_rather_than_destroying_the_subject():
    with tempfile.TemporaryDirectory() as tmp:
        r = normalize_video.normalize(sample("landscape_1080p.mp4"), "feed", os.path.join(tmp, "v.mp4"))
        assert r["fit"] == "pad", "a 16:9 crop loses ~68% of the frame; auto must pad"
        assert r["output"]["aspect"] == "9:16"


def test_forced_crop_and_focus_are_honoured():
    with tempfile.TemporaryDirectory() as tmp:
        r = normalize_video.normalize(sample("landscape_1080p.mp4"), "feed",
                                      os.path.join(tmp, "v.mp4"), focus=(0.25, 0.5), fit="crop")
        assert r["fit"] == "crop"
        assert r["output"]["aspect"] == "9:16"


def test_long_source_is_trimmed_to_the_profile_window():
    spec = specs_mod.video_profile("feed")
    with tempfile.TemporaryDirectory() as tmp:
        r = normalize_video.normalize(sample("lowres_480p.mp4"), "feed", os.path.join(tmp, "v.mp4"))
        assert r["trim"]["duration_s"] == spec["max_duration_s"]
        assert abs(r["output"]["duration_s"] - spec["max_duration_s"]) < 0.5


def test_silent_source_gets_an_audio_track():
    with tempfile.TemporaryDirectory() as tmp:
        r = normalize_video.normalize(sample("lowres_480p.mp4"), "feed", os.path.join(tmp, "v.mp4"))
        assert r["output"]["has_audio"] is True
        assert any("silent" in w for w in r["warnings"])


def test_short_source_warns_and_is_never_looped():
    spec = specs_mod.video_profile("feed")
    with tempfile.TemporaryDirectory() as tmp:
        r = normalize_video.normalize(sample("vertical_1080x1920.mp4"), "feed",
                                      os.path.join(tmp, "v.mp4"), duration=6)
        assert any("under the" in w for w in r["warnings"])
        assert r["output"]["duration_s"] < spec["min_duration_s"]


def test_generated_profile_uses_its_own_resolution_and_window():
    spec = specs_mod.video_profile("generated")
    with tempfile.TemporaryDirectory() as tmp:
        r = normalize_video.normalize(sample("vertical_1080x1920.mp4"), "generated", os.path.join(tmp, "v.mp4"))
        assert (r["output"]["width"], r["output"]["height"]) == (spec["width"], spec["height"])
        assert r["output"]["duration_s"] <= spec["max_duration_s"] + 0.2


def test_start_beyond_duration_fails_loudly():
    with tempfile.TemporaryDirectory() as tmp:
        try:
            normalize_video.normalize(sample("vertical_1080x1920.mp4"), "feed",
                                      os.path.join(tmp, "v.mp4"), start=99)
        except normalize_video.NormalizeError as exc:
            assert "beyond the source duration" in str(exc)
        else:
            raise AssertionError("expected NormalizeError")


def test_image_is_squared_and_upscaled_with_a_warning():
    spec = specs_mod.image_profile("mission")
    with tempfile.TemporaryDirectory() as tmp:
        r = normalize_image.normalize(sample("small.png"), os.path.join(tmp, "i.png"), "mission")
        assert r["output"]["aspect"] == "1:1"
        assert (r["output"]["width"], r["output"]["height"]) == (spec["width"], spec["height"])
        assert r["upscaled"] is True
        assert any("below" in w for w in r["warnings"])


def test_large_image_is_downscaled_without_warning():
    with tempfile.TemporaryDirectory() as tmp:
        r = normalize_image.normalize(sample("large.png"), os.path.join(tmp, "i.png"), "mission")
        assert r["upscaled"] is False
        assert r["ok"] is True, r["warnings"]


def test_clis_emit_json_and_exit_non_zero_on_failure():
    for script, args in [
        ("probe.py", [sample("small.png")]),
        ("normalize_image.py", [sample("large.png"), "--out", tempfile.mktemp(suffix=".png")]),
    ]:
        proc = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", script), *args],
                              capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr
        json.loads(proc.stdout)

    proc = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "probe.py"), "/tmp/nope.mp4"],
                          capture_output=True, text=True)
    assert proc.returncode != 0
    assert "error" in json.loads(proc.stderr)


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception as exc:
                failures += 1
                print(f"FAIL {name}: {exc}")
    print(f"\n{failures} failure(s)")
    sys.exit(1 if failures else 0)
