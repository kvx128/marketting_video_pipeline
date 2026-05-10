from __future__ import annotations

"""
app/services/asset_manager.py
─────────────────────────────
Hardened Global Content-Addressable Asset Manager.

Features:
- Global Cache deduplication with Job-level symlinking.
- Distributed Locking: Uses Redis to ensure only one worker generates 
  a specific asset hash at a time (preventing race conditions).
- Atomic Writes: Generates assets to temporary files first, then renames
  them to the final path to prevent corrupted partial reads.
"""

import hashlib
import logging
import os
import tempfile
from django.conf import settings
from redis import Redis

logger = logging.getLogger(__name__)

class AssetManager:
    def __init__(self, job_id: str):
        self.job_id = job_id
        # The Job-specific folder (for symlinks and final output)
        media_root = str(settings.MEDIA_ROOT)
        self.job_path = os.path.join(media_root, "jobs", job_id)
        # The Global "Truth" folder (for unique input assets)
        self.global_path = os.path.join(media_root, "global_assets")
        
        os.makedirs(self.job_path, exist_ok=True)
        os.makedirs(self.global_path, exist_ok=True)
        
        # Redis connection for distributed locking
        self.redis = Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))
        
        # Lazy load genai
        self._genai = None

    @property
    def genai_client(self):
        if self._genai is None:
            from google import genai
            from google.oauth2 import credentials
            primary = os.getenv("VERTEX_API_KEY")
            fallback = os.getenv("GEMINI_API_KEY")
            
            if not primary and not fallback:
                raise EnvironmentError("Neither VERTEX_API_KEY nor GEMINI_API_KEY is set.")
            
            # Save for fallback use in _generate_image_to_path
            self._primary_key = primary
            self._fallback_key = fallback
            
            # Logic: If fallback exists and looks like a standard Gemini key (AIza...), use it first.
            # Otherwise use primary (Vertex) if it exists.
            # Finally, use fallback if it's all we have.
            if fallback and fallback.startswith("AI"):
                self._genai = genai.Client(api_key=fallback)
            elif primary:
                project = os.getenv("GOOGLE_CLOUD_PROJECT", "366509876542")
                location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
                
                if primary.startswith("AQ"):
                    # OAuth2 Token - Create credentials object to avoid DefaultCredentialsError
                    creds = credentials.Credentials(token=primary)
                    self._genai = genai.Client(vertexai=True, project=project, location=location, credentials=creds)
                else:
                    self._genai = genai.Client(vertexai=True, project=project, location=location)
            else:
                # fallback is all we have but doesn't start with AI
                self._genai = genai.Client(api_key=fallback)
        return self._genai

    def get_asset_hash(self, prompt: str, suffix: str = "") -> str:
        """MD5 hash of the prompt string to identify cached assets."""
        return hashlib.md5(f"{prompt}{suffix}".encode("utf-8")).hexdigest()

    def get_local_path(self, asset_hash: str, extension: str = ".png") -> str:
        """Resolve a hash to an absolute file path in the JOB folder."""
        return os.path.join(self.job_path, f"{asset_hash}{extension}")

    def get_asset(self, prompt: str, extension: str = ".png", generator_func=None, suffix: str = "", reference_image_path: str | None = None):
        """
        Main entry point for Hardened Content-Addressable Storage (CAS).
        Now supports optional reference_image_path for style consistency.
        """
        asset_hash = self.get_asset_hash(prompt, suffix=f"{suffix}_{reference_image_path or ''}")
        global_file = os.path.join(self.global_path, f"{asset_hash}{extension}")
        job_link = os.path.join(self.job_path, f"{asset_hash}{extension}")

        # 1. First check (No lock needed for existing files)
        if not os.path.exists(global_file):
            lock_name = f"lock:asset:{asset_hash}"
            # Acquire distributed lock with a 5-minute timeout
            with self.redis.lock(lock_name, timeout=300):
                # Double-check after acquiring lock
                if not os.path.exists(global_file):
                    logger.info(f"AssetManager: Global Cache MISS (Locked) for {asset_hash}")
                    
                    # Atomic generation using a temporary file
                    fd, temp_path = tempfile.mkstemp(dir=self.global_path, suffix=extension)
                    os.close(fd)
                    
                    try:
                        if generator_func:
                            generator_func(temp_path)
                        else:
                            self._generate_image_to_path(prompt, temp_path, reference_image_path=reference_image_path)
                        
                        # Verify the file was actually created and is not empty
                        if not os.path.exists(temp_path) or os.path.getsize(temp_path) == 0:
                            raise RuntimeError(f"Generator failed to produce a valid file at {temp_path}")

                        # Atomic rename ensures no partial reads
                        os.rename(temp_path, global_file)
                    except Exception as e:
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                        raise e
        else:
            logger.info(f"AssetManager: Global Cache HIT for {asset_hash}")

        # 2. Job-level Symlinking
        if not os.path.lexists(job_link):
            try:
                os.symlink(global_file, job_link)
                logger.info(f"AssetManager: Created symlink {asset_hash} -> job {self.job_id}")
            except FileExistsError:
                pass
            except OSError as e:
                import shutil
                if not os.path.lexists(job_link):
                    shutil.copy2(global_file, job_link)
                logger.warning(f"AssetManager: Symlink failed, fell back to copy: {e}")

        return job_link

    def generate_image_cached(self, prompt: str) -> str:
        """Legacy compatibility method."""
        return self.get_asset(prompt, extension=".png")

    def _generate_image_to_path(self, prompt: str, target_path: str, reference_image_path: str | None = None):
        """Internal method to call Gemini/Imagen with optional style reference."""
        from google.genai import types
        try:
            config_args = {
                "number_of_images": 1,
                "aspect_ratio": "16:9",
                "output_mime_type": "image/png"
            }
            
            from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
            
            @retry(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=2, max=10),
                retry=retry_if_exception_type(Exception),
                reraise=True
            )
            def _call_image_api():
                try:
                    return self.genai_client.models.generate_images(
                        model="imagen-3.0-generate-001",
                        prompt=prompt,
                        config=types.GenerateImagesConfig(**config_args)
                    )
                except Exception as e:
                    if self._fallback_key and self._fallback_key != self._primary_key:
                        logger.warning("Primary Image API failed. Trying fallback key...")
                        from google import genai
                        fallback_client = genai.Client(api_key=self._fallback_key)
                        return fallback_client.models.generate_images(
                            model="imagen-3.0-generate-001",
                            prompt=prompt,
                            config=types.GenerateImagesConfig(**config_args)
                        )
                    raise e

            response = _call_image_api()
            
            if not response.generated_images:
                raise RuntimeError("No images were generated by the API.")
                
            generated_image = response.generated_images[0]
            
            if generated_image.image and generated_image.image.image_bytes:
                with open(target_path, "wb") as f:
                    f.write(generated_image.image.image_bytes)
            else:
                raise RuntimeError("Generated image response missing image data.")
        except Exception as e:
            logger.warning(f"Image API failed, generating placeholder: {e}")
            self._generate_placeholder(target_path, prompt)

    def _generate_placeholder(self, local_path: str, prompt: str):
        """Creates a sophisticated branded placeholder image."""
        from PIL import Image, ImageDraw, ImageFilter
        
        # Branded Palette
        NAVY = (10, 22, 40)      # #0A1628
        GOLD = (245, 197, 24)    # #F5C518
        NAVY_LIGHT = (20, 44, 80)
        
        # Create gradient background
        img = Image.new('RGB', (1920, 1080), color=NAVY)
        d = ImageDraw.Draw(img)
        
        # Simple diagonal gradient
        for i in range(1080):
            mix = i / 1080
            r = int(NAVY[0] * (1 - mix) + NAVY_LIGHT[0] * mix)
            g = int(NAVY[1] * (1 - mix) + NAVY_LIGHT[1] * mix)
            b = int(NAVY[2] * (1 - mix) + NAVY_LIGHT[2] * mix)
            d.line([(0, i), (1920, i)], fill=(r, g, b))
            
        # Add tech texture (subtle noise)
        import random
        for _ in range(5000):
            x, y = random.randint(0, 1919), random.randint(0, 1079)
            d.point((x, y), fill=(255, 255, 255, 30))
            
        # Add branded border
        d.rectangle([0, 0, 1919, 1079], outline=GOLD, width=10)
        
        # Text Overlay
        short_prompt = prompt[:120] + ("..." if len(prompt) > 120 else "")
        try:
            # Try to use a better font if possible, else default
            d.text((100, 450), "TESSACT AI GENERATOR", fill=GOLD)
            d.text((100, 520), f"PREVIEW MODE: {short_prompt}", fill=(255,255,255))
        except:
            d.text((100, 500), f"Mock Image\n{short_prompt}", fill=(255,255,255))
            
        img.save(local_path, format="PNG")
