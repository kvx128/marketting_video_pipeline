"""
app/services/schemas.py
────────────────────────
Pydantic v2 schemas that define the exact JSON shape Gemini must return.

Why Pydantic (not just a dict):
  - Validation happens at parse time — the Celery task fails fast with a clear
    error rather than silently passing garbage to the video renderer.
  - model_dump() serialises cleanly to JSON for Django's JSONField on VideoJob.
  - Field constraints are self-documenting for future prompt engineers.

Schema hierarchy:
  VideoBlueprintSchema
    ├── visual_anchor: str          (the "Consistency Hook")
    ├── scenes: list[Scene]         (5–6 items, total duration 20–30 s)
    └── audio: AudioConfig
"""

from __future__ import annotations

from typing import Annotated, List

from pydantic import BaseModel, Field, model_validator


# ── Leaf models ────────────────────────────────────────────────────────────────

class Scene(BaseModel):
    """One cinematic beat of the video."""

    scene_number: Annotated[int, Field(ge=1, le=6)]
    duration: Annotated[int, Field(ge=2, le=10, description="Duration in seconds")]
    visual_prompt: Annotated[
        str,
        Field(
            min_length=30,
            description=(
                "Text-to-image prompt. Must begin with 'VISUAL ANCHOR:' "
                "reference injected by the consistency hook."
            ),
        ),
    ]
    motion_instruction: Annotated[
        str,
        Field(
            min_length=5,
            description="Camera/subject movement (e.g. 'slow dolly-in', 'static wide shot').",
        ),
    ]
    voiceover_text: Annotated[str, Field(min_length=1)]
    overlay_text: str = ""   # on-screen caption / title — may be empty string


class AudioConfig(BaseModel):
    """Soundtrack mood and tempo guidance for the audio compositor."""

    mood: Annotated[str, Field(min_length=3)]
    tempo: Annotated[str, Field(min_length=3)]
    description: Annotated[
        str,
        Field(
            min_length=10,
            description="One-sentence audio brief for the music selection agent.",
        ),
    ]


# ── Root schema ────────────────────────────────────────────────────────────────

class VideoBlueprintSchema(BaseModel):
    """
    Complete video production plan returned by GeminiOrchestrator.

    Constraints enforced by Pydantic validators:
      - visual_anchor must be ≥ 80 characters (forces Gemini to be specific).
      - scenes: exactly 5 or 6 items.
      - total_duration: sum of scene.duration must be in [20, 30] seconds.
    """

    visual_anchor: Annotated[
        str,
        Field(
            min_length=80,
            description=(
                "Hyper-detailed physical description of the primary brand subject. "
                "Every scene visual_prompt references this anchor to guarantee "
                "visual consistency across all generated images."
            ),
        ),
    ]
    scenes: Annotated[
        List[Scene],
        Field(min_length=5, max_length=6),
    ]
    audio: AudioConfig

    # ── Cross-field validators ─────────────────────────────────────────────────

    @model_validator(mode="after")
    def check_total_duration(self) -> "VideoBlueprintSchema":
        total = sum(s.duration for s in self.scenes)
        if not (20 <= total <= 30):
            raise ValueError(
                f"Total scene duration is {total}s — must be between 20 and 30 seconds. "
                f"Individual scene durations: {[s.duration for s in self.scenes]}"
            )
        return self

    @model_validator(mode="after")
    def check_scene_numbers_sequential(self) -> "VideoBlueprintSchema":
        numbers = [s.scene_number for s in self.scenes]
        expected = list(range(1, len(self.scenes) + 1))
        if numbers != expected:
            raise ValueError(
                f"scene_number values must be sequential starting at 1. "
                f"Got: {numbers}"
            )
        return self

    # ── Convenience properties ─────────────────────────────────────────────────

    @property
    def total_duration(self) -> int:
        return sum(s.duration for s in self.scenes)

    def to_dict(self) -> dict:
        """Serialise to a plain dict suitable for Django's JSONField."""
        return self.model_dump()
