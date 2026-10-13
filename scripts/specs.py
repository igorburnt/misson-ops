#!/usr/bin/env python3
"""Loads skills/creative-standards/references/specs.json.

Every output spec lives in that file. Scripts must never hardcode a
resolution, codec or duration - read it from here so that when the
Command Center limits are confirmed, one JSON edit updates the pipeline.
"""
from __future__ import annotations

import json
import os

SPECS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "skills", "creative-standards", "references", "specs.json",
)


def load(path: str | None = None) -> dict:
    with open(path or SPECS_PATH) as fh:
        return json.load(fh)


def video_profile(name: str, path: str | None = None) -> dict:
    profiles = load(path)["video"]
    if name not in profiles:
        raise KeyError(f"unknown video profile {name!r}; have {sorted(profiles)}")
    return profiles[name]


def image_profile(name: str, path: str | None = None) -> dict:
    profiles = load(path)["image"]
    if name not in profiles:
        raise KeyError(f"unknown image profile {name!r}; have {sorted(profiles)}")
    return profiles[name]
