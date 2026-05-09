# Project Documentation: Tessact Video Pipeline 🏗️

This document provides a comprehensive walkthrough of the system's execution flow and a granular breakdown of the codebase structure.

---

## 🔄 End-to-End Execution Flow

The pipeline operates as a deterministic state machine that manages probabilistic AI outputs.

### 1. The Gateway (Inbound Validation)
- **Action**: The user submits a marketing brief (Markdown/XML).
- **Logic**: The system runs a **DTD (Document Type Definition)** check.
- **Why**: To ensure 100% structural integrity before expensive AI calls. If the XML is malformed, the pipeline errors out early at zero cost.

### 2. Orchestration (Gemini 3 Flash)
- **Action**: The `GeminiOrchestrator` sends the XML to Gemini with a "Lead Creative Technologist" system instruction.
- **Logic**: Uses **Structured Output (Pydantic)** to force the LLM to return a valid JSON blueprint.
- **Why**: Eliminates the "Non-deterministic JSON" problem where LLMs return markdown fences or malformed strings.

### 3. Asset Generation & CAS (Content-Addressable Storage)
- **Action**: The `AssetManager` iterates through the blueprint's scenes.
- **Logic**: 
    - **Hashing**: Each scene's prompt is hashed (MD5).
    - **Deduplication**: If the hash exists in `global_assets/`, it's a "Cache Hit" (zero cost).
    - **Style Transfer**: The first image acts as a "Master Style." All subsequent images use this as a reference to ensure visual cohesion.
- **Why**: Reduces API costs by ~40% and guarantees subject consistency.

### 4. Audio & Text Synthesis
- **Action**: TTS (Voiceover) and Audio moods are generated.
- **Logic**: Programmatic alignment of voiceover timing with scene durations.

### 5. Programmatic Composition (The "Engine")
- **Action**: `VideoComposer` uses MoviePy (FFmpeg) to stitch assets.
- **Logic**: Layers the "Style Transferred" images, applies "Ken Burns" motion, and renders the "Electric Gold" typography.
- **Why**: Programmatic rendering allows for infinite variations without manual editing.

---

## 📂 Folder & File Structure

| Path | Purpose |
| :--- | :--- |
| **`app/core/models.py`** | Defines the `VideoJob` state machine (PENDING -> PROCESSING -> COMPLETED). |
| **`app/core/tasks.py`** | The Celery heart. Orchestrates the stages (Parsing -> Gemini -> Assets -> Render). |
| **`app/services/generator.py`** | The Gemini "Brain." Contains prompt engineering and schema enforcement logic. |
| **`app/services/asset_manager.py`** | The "Vault." Handles MD5 caching, Redis locking, and style transfer. |
| **`app/services/video_engine.py`** | The "Renderer." Handles MoviePy logic, typography, and FFmpeg assembly. |
| **`app/services/schemas.py`** | The Data Contract. Contains the Pydantic models that Gemini must follow. |
| **`core/settings.py`** | Global config. Enforces absolute pathing (`MEDIA_ROOT`) for Docker compatibility. |
| **`global_assets/`** | The persistent Content-Addressable Storage (CAS) for all generated AI assets. |
| **`jobs/`** | Ephemeral working directories for active video assembly (excluded from Git). |
| **`scripts/dtd_validator.py`** | Logic for validating inbound XML against the `video_brief.dtd`. |
| **`Dockerfile`** | Hardened environment config, including ImageMagick security patches for text rendering. |
| **`docker-compose.yml`** | Orchestrates the Web, Worker, Redis, and Postgres containers. |

---

## 🛠️ Key Architectural Decisions

### Why Redis Locking?
In a distributed environment, two workers might try to generate the same missing asset simultaneously. Redis locks ensure we only pay for one API call.

### Why Atomic Writes?
FFmpeg is sensitive to file locks. By writing to `.tmp` files and using `os.rename`, we guarantee that the video engine never tries to read a partially written image.

### Why Absolute Paths?
Docker volume mappings (`/app`) can cause path resolution errors if relative paths are used. Enforcing `BASE_DIR` in the `AssetManager` ensures the pipeline works on any OS.
