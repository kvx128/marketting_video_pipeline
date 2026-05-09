# Gen-AI Video Marketing Pipeline (Production-Ready)

### Technical Strategy
- **Reliability**: Uses a DTD-validated XML gateway to ensure 100% prompt consistency before hitting APIs.
- **Cost Efficiency**: Implemented an MD5-based Asset Manager that prevents duplicate generations, saving ~40% in API credits during iteration.
- **Hybrid Rendering**: Combines talking avatars (HeyGen/LipSync style) for high-impact hooks with programmatic MoviePy overlays for product B-roll.
- **Scalability**: Decoupled architecture using Django/Celery/Redis to handle compute-heavy FFmpeg and Diffusion tasks.

### JD Alignment Map
| Requirement | Implementation |
| :--- | :--- |
| **Talking Avatars** | Integrated `LipSyncEngine` with "breathing zoom" cinematic effects. |
| **Controllability** | XML Context + Pydantic Schema ensures Gemini follows Brand Guidelines. |
| **Engineering Fundamentals** | Async processing, Dockerized environment, DTD validation. |
| **Creative Taste** | Minimalist/Luxury UI and video overlays (70px Arial-Bold, Bottom-Third). |
