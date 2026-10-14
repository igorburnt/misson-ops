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

import extract_frames  # noqa: E402
import normalize_image  # noqa: E402
import normalize_video  # noqa: E402
import profile_library  # noqa: E402
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


def test_specs_match_the_command_center_limits():
    """Confirmed by Sidney 2026-10-13. These are upload-rejection limits, not preferences."""
    s = specs_mod.load()
    for name in ("feed", "generated"):
        v = s["video"][name]
        assert (v["width"], v["height"]) == (1080, 1920), f"{name}: minimum is 1080x1920"
        assert v["max_duration_s"] <= 30, f"{name}: hard 30s ceiling"
        assert v["max_size_mb"] <= 30, f"{name}: hard 30MB ceiling"
        assert v["container"] == "mp4" and v["vcodec"] == "libx264"
        assert v["fps"] in (24, 30)
    i = s["image"]["mission"]
    assert i["min_width"] >= 1024 and i["min_height"] >= 1024
    assert i["width"] >= i["min_width"] and i["height"] >= i["min_height"]
    assert i["max_size_mb"] <= 1.0
    assert i["format"] in ("png", "jpg", "jpeg", "webp")


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
        # The ceiling is a hard upload limit: never at or over it, and never
        # so far under that we throw away usable footage.
        assert r["output"]["duration_s"] <= spec["max_duration_s"], "a 30.002s file is rejected"
        assert r["output"]["duration_s"] > spec["max_duration_s"] - 0.5


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


def test_generated_profile_clears_the_1080x1920_minimum():
    """Generation renders at 720x1280 for credits/artifacts, but the Command Center
    requires >=1080x1920, so the export upscales - a note, never a blocking warning."""
    spec = specs_mod.video_profile("generated")
    assert (spec["generate_width"], spec["generate_height"]) == (720, 1280)
    assert spec["allow_upscale"] is True
    with tempfile.TemporaryDirectory() as tmp:
        small = os.path.join(tmp, "small.mp4")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                        "-i", "testsrc2=size=720x1280:rate=30:duration=8",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", small], check=True)
        r = normalize_video.normalize(small, "generated", os.path.join(tmp, "v.mp4"))
        assert (r["output"]["width"], r["output"]["height"]) == (1080, 1920)
        assert any("upscaled" in n for n in r["notes"]), "expected upscale to be a note"
        assert not any("upscaled" in w for w in r["warnings"]), "upscale must not block generated"


def test_oversized_output_is_re_encoded_to_fit_the_cap():
    """Overshooting the size cap means a rejected upload, so the script
    re-encodes against the budget instead of just warning."""
    with tempfile.TemporaryDirectory() as tmp:
        tight = json.loads(open(specs_mod.SPECS_PATH).read())
        tight["video"]["feed"]["max_size_mb"] = 5
        tight_path = os.path.join(tmp, "specs.json")
        with open(tight_path, "w") as fh:
            json.dump(tight, fh)
        r = normalize_video.normalize(sample("vertical_1080x1920.mp4"), "feed",
                                      os.path.join(tmp, "v.mp4"), specs_path=tight_path)
        assert r["encode_passes"] > 1
        assert r["output"]["size_mb"] <= 5
        assert any("re-encoded" in w for w in r["warnings"])


def test_output_extension_must_match_the_spec_container():
    with tempfile.TemporaryDirectory() as tmp:
        try:
            normalize_video.normalize(sample("vertical_1080x1920.mp4"), "feed", os.path.join(tmp, "v.webm"))
        except normalize_video.NormalizeError as exc:
            assert "container" in str(exc)
        else:
            raise AssertionError("expected NormalizeError on container mismatch")


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
        out = os.path.join(tmp, "i." + spec["format"])
        r = normalize_image.normalize(sample("small.png"), out, "mission")
        assert r["output"]["aspect"] == "1:1"
        assert (r["output"]["width"], r["output"]["height"]) == (spec["width"], spec["height"])
        assert r["upscaled"] is True
        assert any("below" in w for w in r["warnings"])


def test_large_image_is_downscaled_without_warning():
    with tempfile.TemporaryDirectory() as tmp:
        spec = specs_mod.image_profile("mission")
        out = os.path.join(tmp, "i." + spec["format"])
        r = normalize_image.normalize(sample("large.png"), out, "mission")
        assert r["upscaled"] is False
        assert r["ok"] is True, r["warnings"]
        assert r["output"]["size_mb"] <= spec["max_size_mb"]


def test_image_quality_ladder_fits_a_detailed_source_under_the_cap():
    """A photographic 1080x1080 PNG routinely lands at 2-3MB against a 1.0MB
    cap; the lossy ladder is what keeps the mission image uploadable."""
    spec = specs_mod.image_profile("mission")
    assert spec["format"] != "png", "a lossless format cannot be stepped down to fit the cap"
    with tempfile.TemporaryDirectory() as tmp:
        noisy = os.path.join(tmp, "noise.png")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                        "-i", "nullsrc=s=1600x1600,geq=random(1)*255:128:128",
                        "-frames:v", "1", noisy], check=True)
        r = normalize_image.normalize(noisy, os.path.join(tmp, "i." + spec["format"]), "mission")
        assert r["output"]["size_mb"] <= spec["max_size_mb"], r["warnings"]


def test_image_extension_must_match_the_spec_format():
    spec = specs_mod.image_profile("mission")
    wrong = "jpg" if spec["format"] != "jpg" else "webp"
    with tempfile.TemporaryDirectory() as tmp:
        try:
            normalize_image.normalize(sample("large.png"), os.path.join(tmp, "i." + wrong), "mission")
        except normalize_image.NormalizeError as exc:
            assert "format" in str(exc)
        else:
            raise AssertionError("expected NormalizeError on format mismatch")


def test_extract_frames_takes_the_first_frame_and_spaced_frames():
    """The first frame matters on its own - the rubric's hook criterion is
    about the first 2 seconds."""
    with tempfile.TemporaryDirectory() as tmp:
        r = extract_frames.extract(sample("vertical_1080x1920.mp4"), tmp, n=6, detect=False)
        assert len(r["frames"]) == 6
        assert r["frames"][0]["time_s"] == 0.0
        times = [f["time_s"] for f in r["frames"]]
        assert times == sorted(times)
        assert all(os.path.getsize(f["file"]) > 0 for f in r["frames"])
        assert max(times) < r["input"]["duration_s"]


def test_extract_frames_detects_cuts_on_a_cut_heavy_clip():
    with tempfile.TemporaryDirectory() as tmp:
        # Two visually unrelated sources spliced together: exactly one hard cut.
        a, b, spliced = (os.path.join(tmp, n) for n in ("a.mp4", "b.mp4", "s.mp4"))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                        "-i", "color=c=black:s=640x1136:d=3:r=30", "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", a], check=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                        "-i", "color=c=white:s=640x1136:d=3:r=30", "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", b], check=True)
        lst = os.path.join(tmp, "l.txt")
        with open(lst, "w") as fh:
            fh.write(f"file '{a}'\nfile '{b}'\n")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                        "-i", lst, "-c", "copy", spliced], check=True)
        r = extract_frames.extract(spliced, tmp, n=3, detect=True)
        assert r["cut_count"] >= 1, "a black-to-white splice must register as a cut"
        assert r["cuts_per_second"] is not None
        assert r["mean_shot_s"] > 0


def test_extract_frames_rejects_an_image():
    with tempfile.TemporaryDirectory() as tmp:
        try:
            extract_frames.extract(sample("small.png"), tmp)
        except extract_frames.FrameError as exc:
            assert "image" in str(exc)
        else:
            raise AssertionError("expected FrameError")


def test_profile_library_separates_the_mixed_groups():
    """The library mixes shipped finals, raw sources and ad-network banners.
    Averaging across them describes nothing, so grouping is the whole point."""
    with tempfile.TemporaryDirectory() as tmp:
        for brand, fixtures in {
            "Acme": [("feed-high.mp4", "testsrc2=size=1080x1920:rate=30:duration=6"),
                     ("scraped.publer.com.mp4", "testsrc2=size=1920x1080:rate=30:duration=6")],
            "Globex": [("feed.mp4", "testsrc2=size=1080x1920:rate=30:duration=6"),
                       ("dsp_480x320.mp4", "testsrc2=size=480x320:rate=30:duration=6")],
        }.items():
            os.makedirs(os.path.join(tmp, brand), exist_ok=True)
            for name, src in fixtures:
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", src,
                                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                                os.path.join(tmp, brand, name)], check=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                        "-i", "testsrc2=size=1024x1024", "-frames:v", "1",
                        os.path.join(tmp, "Acme", "acme_1x1_1024.png")], check=True)

        r = profile_library.profile(tmp, cuts=False)
        assert r["groups"]["feed"]["count"] == 2, "feed*.mp4 is the house standard"
        assert r["groups"]["feed"]["brands"] == 2
        assert r["groups"]["undersized"]["count"] == 1, "480x320 can never reach 1080x1920"
        assert r["groups"]["source"]["count"] == 1
        assert r["groups"]["image_1x1"]["count"] == 1
        assert r["groups"]["feed"]["duration_s"]["median"] > 0
        assert any("misleading" in n for n in r["notes"])


def test_profile_library_reports_brand_skew():
    """One brand dominating a group makes its aggregate describe that brand,
    so the share is reported rather than left for the reader to notice."""
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, "Hoggy"), exist_ok=True)
        os.makedirs(os.path.join(tmp, "Small"), exist_ok=True)
        for i in range(4):
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                            "-i", "testsrc2=size=480x320:rate=30:duration=2",
                            "-c:v", "libx264", "-pix_fmt", "yuv420p",
                            os.path.join(tmp, "Hoggy", f"dsp{i}.mp4")], check=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                        "-i", "testsrc2=size=480x320:rate=30:duration=2",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        os.path.join(tmp, "Small", "dsp.mp4")], check=True)
        r = profile_library.profile(tmp, cuts=False)
        top = r["groups"]["undersized"]["top_brand"]
        assert top["name"] == "Hoggy"
        assert top["share"] == 0.8


def test_clis_emit_json_and_exit_non_zero_on_failure():
    for script, args in [
        ("probe.py", [sample("small.png")]),
        ("normalize_image.py", [sample("large.png"), "--out",
                                tempfile.mktemp(suffix="." + specs_mod.image_profile("mission")["format"])]),
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
