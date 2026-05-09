"""
tests/test_schemas.py
──────────────────────
Unit tests for app/services/schemas.py.

Run with:
    .venv/Scripts/python -m pytest tests/ -v

No API keys, no Django setup, no network access needed.
These tests validate that the Pydantic schema correctly:
  1. Accepts a valid blueprint
  2. Rejects short visual_anchors
  3. Rejects out-of-range scene counts
  4. Rejects invalid total durations
  5. Rejects non-sequential scene numbers
"""

import pytest
from pydantic import ValidationError

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.services.schemas import AudioConfig, Scene, VideoBlueprintSchema


# ── Fixtures ───────────────────────────────────────────────────────────────────

def _make_scene(n: int, duration: int = 5) -> dict:
    return {
        "scene_number": n,
        "duration": duration,
        "visual_prompt": f"VISUAL ANCHOR: A sleek matte-black chair | SCENE {n}: wide establishing shot",
        "motion_instruction": "slow dolly-in, subject static",
        "voiceover_text": f"Scene {n} narration text.",
        "overlay_text": f"Title {n}",
    }


VALID_ANCHOR = (
    "A minimalist matte-black ergonomic office chair with silver brushed-aluminium base, "
    "high-quality mesh backrest with subtle orange stitching on the armrests, "
    "shot in a sun-drenched Scandinavian loft interior with warm bokeh background."
)

VALID_AUDIO = {
    "mood": "Cinematic confidence",
    "tempo": "90 BPM — slow build",
    "description": "Minimal orchestral swell with a driving percussive kick entering at scene 3.",
}


def _valid_payload(n_scenes: int = 5, duration_each: int = 5) -> dict:
    return {
        "visual_anchor": VALID_ANCHOR,
        "scenes": [_make_scene(i + 1, duration_each) for i in range(n_scenes)],
        "audio": VALID_AUDIO,
    }


# ── Happy path ─────────────────────────────────────────────────────────────────

def test_valid_5_scene_blueprint():
    bp = VideoBlueprintSchema.model_validate(_valid_payload(n_scenes=5, duration_each=5))
    assert bp.total_duration == 25
    assert len(bp.scenes) == 5


def test_valid_6_scene_blueprint():
    # 6 × 4 = 24 s — within [20, 30]
    bp = VideoBlueprintSchema.model_validate(_valid_payload(n_scenes=6, duration_each=4))
    assert bp.total_duration == 24


def test_to_dict_contains_all_keys():
    bp = VideoBlueprintSchema.model_validate(_valid_payload())
    d = bp.to_dict()
    assert set(d.keys()) == {"visual_anchor", "scenes", "audio"}
    assert isinstance(d["scenes"], list)


# ── visual_anchor validation ───────────────────────────────────────────────────

def test_short_anchor_rejected():
    payload = _valid_payload()
    payload["visual_anchor"] = "Too short."
    with pytest.raises(ValidationError) as exc_info:
        VideoBlueprintSchema.model_validate(payload)
    assert "visual_anchor" in str(exc_info.value)


# ── Scene count validation ─────────────────────────────────────────────────────

def test_too_few_scenes_rejected():
    payload = _valid_payload(n_scenes=4, duration_each=6)
    with pytest.raises(ValidationError):
        VideoBlueprintSchema.model_validate(payload)


def test_too_many_scenes_rejected():
    payload = _valid_payload(n_scenes=7, duration_each=4)
    with pytest.raises(ValidationError):
        VideoBlueprintSchema.model_validate(payload)


# ── Duration validation ────────────────────────────────────────────────────────

def test_total_too_short_rejected():
    # 5 × 3 = 15 s < 20 s
    payload = _valid_payload(n_scenes=5, duration_each=3)
    with pytest.raises(ValidationError) as exc_info:
        VideoBlueprintSchema.model_validate(payload)
    assert "duration" in str(exc_info.value).lower()


def test_total_too_long_rejected():
    # 5 × 7 = 35 s > 30 s
    payload = _valid_payload(n_scenes=5, duration_each=7)
    with pytest.raises(ValidationError) as exc_info:
        VideoBlueprintSchema.model_validate(payload)
    assert "duration" in str(exc_info.value).lower()


def test_exact_boundary_20s_accepted():
    # 5 × 4 = 20 s — exactly at lower bound
    bp = VideoBlueprintSchema.model_validate(_valid_payload(n_scenes=5, duration_each=4))
    assert bp.total_duration == 20


def test_exact_boundary_30s_accepted():
    # 5 × 6 = 30 s — exactly at upper bound
    bp = VideoBlueprintSchema.model_validate(_valid_payload(n_scenes=5, duration_each=6))
    assert bp.total_duration == 30


# ── Scene number validation ────────────────────────────────────────────────────

def test_non_sequential_scene_numbers_rejected():
    payload = _valid_payload()
    payload["scenes"][2]["scene_number"] = 6  # break sequential order (1, 2, 6, 4, 5)
    with pytest.raises(ValidationError) as exc_info:
        VideoBlueprintSchema.model_validate(payload)
    assert "sequential" in str(exc_info.value).lower()


# ── Consistency hook (tested via GeminiOrchestrator._apply_consistency_hook) ───

def test_consistency_hook_prepends_anchor():
    from app.services.generator import GeminiOrchestrator

    payload = _valid_payload()
    # Simulate a scene whose visual_prompt does NOT yet have the anchor prefix
    payload["scenes"][0]["visual_prompt"] = "Wide shot of office chair on white background."

    result = GeminiOrchestrator._apply_consistency_hook(payload)
    assert result["scenes"][0]["visual_prompt"].startswith("VISUAL ANCHOR:")


def test_consistency_hook_does_not_duplicate_prefix():
    from app.services.generator import GeminiOrchestrator

    payload = _valid_payload()
    # Already has the prefix — hook must NOT prepend again
    original_prompt = "VISUAL ANCHOR: Already prefixed scene prompt."
    payload["scenes"][0]["visual_prompt"] = original_prompt

    result = GeminiOrchestrator._apply_consistency_hook(payload)
    # Should start with VISUAL ANCHOR: exactly once
    assert result["scenes"][0]["visual_prompt"].count("VISUAL ANCHOR:") == 1
