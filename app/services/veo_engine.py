import time
import logging
import os
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

class VeoEngine:
    """
    Service for Google Veo: High-fidelity generative video.
    """
    def __init__(self):
        self.primary_api_key = os.getenv("VERTEX_API_KEY")
        self.fallback_api_key = os.getenv("GEMINI_API_KEY")
        
        if not self.primary_api_key and not self.fallback_api_key:
            raise EnvironmentError("Neither VERTEX_API_KEY nor GEMINI_API_KEY is set.")
        
        self.model_name = "veo-2.0-generate-001"

    def generate_animated_clip(self, prompt, output_path, motion_instruction=None, reference_image=None):
        """
        Generates a 5-second high-fidelity cinematic clip.
        """
        # Enhance prompt for video-specific marketing quality
        full_prompt = f"High-end marketing video, commercial grade luxury aesthetic. SCENE: {prompt}"
        if motion_instruction:
            full_prompt += f" | MOTION: {motion_instruction}"
            
        logger.info(f"VeoEngine: Generating cinematic clip for prompt: {full_prompt[:80]}...")
        
        from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=2, min=4, max=20),
            retry=retry_if_exception_type(Exception),
            reraise=True
        )
        def _call_veo():
            key_to_use = self.fallback_api_key if (self.fallback_api_key and self.fallback_api_key.startswith("AI")) else self.primary_api_key
            
            try:
                project = os.getenv("GOOGLE_CLOUD_PROJECT", "366509876542")
                location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
                
                from google.oauth2 import credentials
                if key_to_use and key_to_use.startswith("AI"):
                    client = genai.Client(api_key=key_to_use)
                elif key_to_use:
                    # Vertex AI Path
                    if key_to_use.startswith("AQ"):
                        creds = credentials.Credentials(token=key_to_use)
                        client = genai.Client(vertexai=True, project=project, location=location, credentials=creds)
                    else:
                        client = genai.Client(vertexai=True, project=project, location=location)
                else:
                    raise EnvironmentError("No API key available for Veo.")
                
                return self._generate_with_client(client, full_prompt, output_path)
            except Exception as e:
                # Fallback within retry if main key fails
                other_key = self.primary_api_key if key_to_use == self.fallback_api_key else self.fallback_api_key
                if other_key and other_key != key_to_use:
                    logger.warning(f"Veo main key failed. Trying other key...")
                    if other_key.startswith("AI"):
                        client = genai.Client(api_key=other_key)
                    else:
                        if other_key.startswith("AQ"):
                            creds = credentials.Credentials(token=other_key)
                            client = genai.Client(vertexai=True, project=project, location=location, credentials=creds)
                        else:
                            client = genai.Client(vertexai=True, project=project, location=location)
                    return self._generate_with_client(client, full_prompt, output_path)
                raise e

        try:
            return _call_veo()
        except Exception as e:
            logger.error(f"VeoEngine: All generation attempts failed: {e}")
            raise e
        
        raise RuntimeError("Veo generation failed and no working API key available.")

    def _generate_with_client(self, client: genai.Client, prompt: str, output_path: str):
        operation = client.models.generate_videos(
            model=self.model_name,
            prompt=prompt
        )
        
        logger.info("VeoEngine: Polling for video completion...")
        while not operation.done:
            time.sleep(15) # Longer sleep for video
            operation = client.operations.get(operation)
            
        if operation.error:
            raise RuntimeError(f"Veo generation failed: {operation.error}")
            
        response = operation.response
        if response and response.generated_videos:
            video_obj = response.generated_videos[0].video
            if not video_obj:
                raise RuntimeError("Video object is missing in the response.")

            video_bytes = getattr(video_obj, 'video_bytes', None)
            if video_bytes:
                with open(output_path, "wb") as f:
                    f.write(video_bytes)
                logger.info(f"VeoEngine: Video successfully saved to {output_path}")
                return output_path
            
            # If bytes aren't available, check for URI
            video_uri = getattr(video_obj, 'uri', None)
            if video_uri:
                logger.info(f"VeoEngine: Video generated at URI: {video_uri}")
                # Future: Implement download logic if needed
                pass
        
        raise RuntimeError("No video returned from Veo API.")
