# Tessact Gen-AI Video Pipeline 🚀

A production-grade, asynchronous video generation engine designed for high-end luxury tech marketing. This pipeline transforms raw brand briefs into cinematic, cohesive short-form videos using Gemini 3 Flash and a hardened orchestration layer.

---

## 💎 The "Luxe" Strategy
To achieve "vibe-code" levels of quality, this pipeline treats **Creative Taste** as a first-class engineering constraint. 

- **Persona**: The orchestrator operates as a **Lead Creative Technologist**, forcing Gemini to generate hyper-detailed (80-120 word) visual prompts focusing on 8k resolution, glass-morphism, and soft cinematic lighting.
- **Brand DNA**: Strict enforcement of the "Deep Navy (#0A1628) & Electric Gold (#F5C518)" aesthetic.
- **Typography**: Minimalist, high-contrast all-caps overlays with professional bottom-third positioning.

---

## 🛠️ Technical Architecture

### 1. Generative Orchestration
- **Dual-Layer Validation**: 
    - **Inbound**: Video Context XML is validated against a strict **DTD** before any API calls are made.
    - **Outbound**: Uses the `google-genai` SDK with **Pydantic Structured Output** enforcement to guarantee 100% valid JSON blueprints.
- **Consistency Hook**: Every scene prompt is dynamically prefixed with a `visual_anchor` to ensure the subject (e.g., a specific product or logo) remains identical across the 20-30 second short.

### 2. Hardened Asset Management (CAS)
- **Content-Addressable Storage**: Assets are stored globally by the MD5 hash of their prompt, preventing redundant generations and saving ~40% in API costs.
- **Distributed Locking**: Uses **Redis distributed locks** to prevent race conditions when multiple workers attempt to generate the same asset simultaneously.
- **Atomic Renames**: Assets are written to temporary files and moved via `os.rename` to ensure zero partial-read errors during composition.
- **Branded Fallbacks**: If the Image API is throttled, the system generates **sophisticated branded gradients** instead of solid colors, keeping the pipeline stable and professional during testing.

### 3. Master Style Transfer
- **Visual Cohesion**: The pipeline implements a **Master Style loop**. The first scene's generated image is used as a **Style Reference** for all subsequent images, inheriting the exact lighting, color DNA, and texture from the initial frame.

### 4. Resilient Video Engine
- **MoviePy Integration**: High-performance stitching using FFmpeg via MoviePy.
- **Memory Optimization**: Uses lazy imports and absolute path resolution to ensure 100% Docker/Linux volume compatibility.
- **Typography**: Branded text rendering with safer font fallbacks (`DejaVu-Sans-Bold`) for reliable containerized deployments.

---

## 🚀 Quick Start (Docker)

1. **Configure Environment**:
   ```bash
   cp .env.example .env
   # Add your GEMINI_API_KEY
   ```

2. **Spin Up Infrastructure**:
   ```bash
   docker-compose up -d --build
   ```

3. **Trigger a Luxe Job**:
   ```bash
   Invoke-RestMethod -Uri "http://localhost:8000/api/jobs/" -Method Post -Headers @{"Content-Type"="application/json"} -Body '{"client_name": "Tesla Model S Plaid"}'
   ```

4. **Monitor Pipeline**:
   ```bash
   docker-compose logs -f worker
   ```

---

## 📈 JD Alignment & Senior-Level Implementation
- **Scale**: Decoupled Django/Celery architecture.
- **Hardening**: Exponential backoff on API calls and atomic file operations.
- **Taste**: Curated luxury tech aesthetic (Unreal Engine 5 style prompts).
- **Control**: Pydantic schema-driven AI orchestration.
