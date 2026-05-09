"""
app/services/generator.py
──────────────────────────
Gemini orchestration layer — converts a DTD-validated VideoContext XML into
a fully structured, Pydantic-validated video production blueprint.

Design principles:
  1. LAZY IMPORT  — google.generativeai is imported inside __init__ so Django
                    management commands (check, migrate, collectstatic) never
                    touch the protobuf C-extension.
  2. JSON MODE    — response_mime_type="application/json" forces Gemini to emit
                    raw JSON with no markdown fences, making json.loads() safe.
  3. SYSTEM INSTR — Creative direction lives in the system instruction (separate
                    from the user prompt) so it cannot be overridden by user data.
  4. SCHEMA GUARD — Pydantic validates every field before the dict is returned,
                    so downstream video renderers never receive malformed data.
  5. CONSISTENCY  — The visual_anchor post-processor prepends the anchor to every
                    scene's visual_prompt, guaranteeing cross-scene visual identity.

Cost note:
  Default model: gemini-2.5-flash (env: GEMINI_MODEL)
  Budget alternative: set GEMINI_MODEL=gemini-1.5-flash (~10x cheaper for
  structured extraction tasks that don't need deep reasoning).
"""

from __future__ import annotations

import json
import logging
import os

from typing import Any

from pydantic import ValidationError

from app.services.schemas import VideoBlueprintSchema

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# ── System instruction (injected as a separate role, not in user prompt) ────────
# This keeps creative direction immutable regardless of XML content.

_SYSTEM_INSTRUCTION = """\
You are a Lead Creative Technologist at a premier Gen-AI production studio. 
Your output must be a valid JSON blueprint for a 20-30 second marketing short.

═══ MANDATORY BRAND DNA ═══════════════════════════════════════════════════════
- PALETTE: Backgrounds MUST be Deep Navy (#0A1628). Accents MUST be Electric Gold (#F5C518).
- TEXTURE: Use terms like 'holographic data streams', 'minimalist glass-morphism', 'bokeh', '8k resolution'.
- AESTHETIC: Luxury Tech, Unreal Engine 5 render style, soft cinematic lighting.

═══ PROMPT ENGINEERING RULES ══════════════════════════════════════════════════
1. HYPER-DETAILED PROMPTS: Each 'visual_prompt' must be 80-120 words. 
   Do not just describe the scene; describe the lens, lighting, texture, and 'vibe'.
2. CONSISTENCY HOOK: Use the 'visual_anchor' as the base for every scene.
3. SCENING: Breakdown the client's goal into 5-6 high-impact visual beats.
4. TYPOGRAPHY: 'overlay_text' should be concise, professional, and high-contrast.

═══ DURATION CONTRACT ════════════════════════════════════════════════════════
- 5 or 6 scenes total.
- Total duration MUST be between 20 and 30 seconds.
- Each scene: 2-10 seconds.

═══ OUTPUT SCHEMA (strict) ══════════════════════════════════════════════════════
{
  "visual_anchor": "string (>=80 chars, hyper-detailed physical description)",
  "scenes": [
    {
      "scene_number": 1,
      "duration": 5,
      "visual_prompt": "VISUAL ANCHOR: ... | SCENE: ...",
      "motion_instruction": "camera movement + subject movement",
      "voiceover_text": "what the narrator says",
      "overlay_text": "on-screen title or caption (may be empty string)"
    }
  ],
  "audio": {
    "mood": "e.g. Cinematic tension",
    "tempo": "e.g. 90 BPM - slow build to 120 BPM",
    "description": "one-sentence audio brief"
  }
}
"""

# ── User prompt template (contains only variable data) ──────────────────────────

_BLUEPRINT_PROMPT = """\
Analyse the following VideoContext XML and generate the video blueprint.

[CONTEXT]
{xml_context}
[/CONTEXT]

Remember:
- visual_anchor must be >= 80 characters and describe the primary subject in cinematic detail.
- Every scene visual_prompt must open with "VISUAL ANCHOR: [first 30 words of anchor] | SCENE: ..."
- Total scene duration must be 20-30 seconds across 5-6 scenes.
- Output ONLY the JSON object - no commentary, no code fences.
"""


# ── Main orchestrator ───────────────────────────────────────────────────────────

class GeminiOrchestrator:
    """
    Transforms a DTD-validated VideoContext XML string into a structured,
    Pydantic-validated video blueprint dict.

    Usage:
        orchestrator = GeminiOrchestrator()
        blueprint: dict = orchestrator.get_video_blueprint(xml_string)

    The returned dict is safe to store directly in Django's JSONField and
    to pass as-is to the asset generation stage (Prompt 4).
    """

    def __init__(self, model_name: str | None = None) -> None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "GEMINI_API_KEY environment variable is not set. "
                "Add it to your .env file or Docker environment."
            )

        # ── Lazy import keeps Django startup free of protobuf C-extension ─────
        from google import genai  # noqa: PLC0415
        from google.genai import types

        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name or _DEFAULT_MODEL
        self.config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=VideoBlueprintSchema,  # THE KEY FIX: Enforce schema at the model level
            temperature=0.75,          # creative but not hallucination-prone
            top_p=0.95,
            max_output_tokens=4096,
            system_instruction=_SYSTEM_INSTRUCTION,
        )
        logger.info("GeminiOrchestrator ready — model: %s, Structured Output: ON", self.model_name)

    # ── Public API ─────────────────────────────────────────────────────────────

    def get_video_blueprint(self, xml_context: str) -> dict:
        """
        Main entry point.  Parse XML → Gemini → Pydantic → consistency hook → dict.

        Args:
            xml_context: DTD-validated XML string from xml_parser.md_to_xml_validated().

        Returns:
            A plain dict matching VideoBlueprintSchema, ready for Django's JSONField.
            Each scene['visual_prompt'] has the visual_anchor prepended.

        Raises:
            EnvironmentError:  GEMINI_API_KEY missing.
            RuntimeError:      Gemini returned empty response or un-parseable JSON.
            ValueError:        Blueprint fails Pydantic schema validation.
        """
        prompt = _BLUEPRINT_PROMPT.format(xml_context=xml_context)
        logger.info(
            "Requesting blueprint from %s (XML: %d chars)", self.model_name, len(xml_context)
        )

        # ── 1. Gemini API call ─────────────────────────────────────────────────
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=self.config
        )

        # ── 2. Handle Structured Response ──────────────────────────────────────
        if not response.parsed:
            # Fallback to manual parse if 'parsed' is missing but text exists
            if response.text:
                try:
                    raw_dict = json.loads(response.text)
                    blueprint = self._validate_schema(raw_dict)
                except (json.JSONDecodeError, ValidationError) as exc:
                    raise RuntimeError(
                        f"Gemini failed structured output and fallback parsing.\n"
                        f"Error: {exc}\n\n"
                        f"Raw response (first 500 chars):\n{response.text[:500]}"
                    ) from exc
            else:
                raise RuntimeError("Gemini returned no parsed data or raw text.")
        else:
            # SDK successfully parsed the response into our Pydantic model.
            # We explicitly cast to dict to satisfy the IDE's static analysis
            # since response.parsed is typed as a broad Union in the SDK.
            if hasattr(response.parsed, "model_dump"):
                blueprint = response.parsed.model_dump()
            else:
                blueprint = dict(response.parsed)  # type: ignore

        # ── 3. Consistency hook — inject visual_anchor into every visual_prompt ─
        result = self._apply_consistency_hook(blueprint)

        logger.info(
            "Blueprint complete — %d scenes, %ds total, anchor: %.60s…",
            len(result["scenes"]),
            sum(s["duration"] for s in result["scenes"]),
            result["visual_anchor"],
        )
        return result

    # ── Private helpers ────────────────────────────────────────────────────────

    def _validate_schema(self, raw_dict: dict) -> dict:
        """
        Validate raw Gemini output against VideoBlueprintSchema.

        Converts Pydantic ValidationError into a descriptive ValueError so the
        Celery task's error_log captures exactly which field(s) are wrong.
        """
        try:
            blueprint = VideoBlueprintSchema.model_validate(raw_dict)
            return blueprint.to_dict()
        except ValidationError as exc:
            error_summary = "\n".join(
                f"  • [{' → '.join(str(loc) for loc in e['loc'])}] {e['msg']}"
                for e in exc.errors()
            )
            raise ValueError(
                f"Gemini blueprint failed schema validation ({exc.error_count()} error(s)):\n"
                f"{error_summary}\n\n"
                f"Ensure the system instruction is not being truncated by token limits.\n"
                f"Raw output keys: {list(raw_dict.keys())}"
            ) from exc

    @staticmethod
    def _apply_consistency_hook(blueprint: dict) -> dict:
        """
        Prepend the visual_anchor to every scene's visual_prompt.

        This is the "Consistency Hook" — the single most effective technique to
        prevent image generation models from drifting between scenes.

        Strategy:
          - Use the first 200 characters of the anchor as the prefix (long enough
            to lock in the subject, short enough not to bloat the image prompt).
          - If Gemini already prefixed the prompt correctly (following system
            instruction), skip to avoid duplication.

        Args:
            blueprint: Already validated dict from _validate_schema().

        Returns:
            Same dict with modified visual_prompt values on each scene.
        """
        anchor = blueprint["visual_anchor"]
        anchor_prefix = anchor[:200].rstrip()

        for scene in blueprint["scenes"]:
            vp = scene["visual_prompt"]
            if not vp.startswith("VISUAL ANCHOR:"):
                scene["visual_prompt"] = (
                    f"VISUAL ANCHOR: {anchor_prefix} | "
                    f"SCENE {scene['scene_number']}: {vp}"
                )

        return blueprint

    @staticmethod
    def get_system_instruction() -> str:
        """Expose the system instruction for logging / prompt debugging."""
        return _SYSTEM_INSTRUCTION


# ── Convenience wrapper (backward compat + CLI) ────────────────────────────────

def generate_video_plan(xml_context: str) -> dict:
    """Thin wrapper around GeminiOrchestrator for script-level use."""
    return GeminiOrchestrator().get_video_blueprint(xml_context)
