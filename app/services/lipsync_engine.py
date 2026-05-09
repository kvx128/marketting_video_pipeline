import os
import logging
from .asset_manager import AssetManager

logger = logging.getLogger(__name__)

class LipSyncEngine:
    def __init__(self, job_id):
        self.manager = AssetManager(job_id)

    def generate_talking_head(self, image_path, audio_path, scene_index):
        # Unique identifier for the combination of image and audio
        prompt_combo = image_path + audio_path
        
        def generator(target_path):
            # Simulation mode
            self._simulate_lipsync(image_path, audio_path, target_path)

        return self.manager.get_asset(
            prompt_combo, 
            extension=".mp4", 
            generator_func=generator, 
            suffix="lipsync"
        )

    def _simulate_lipsync(self, image_path, audio_path, output_path):
        from PIL import Image
        if not hasattr(Image, 'ANTIALIAS'):
            Image.ANTIALIAS = Image.Resampling.LANCZOS
            
        from moviepy.editor import ImageClip, AudioFileClip
        
        try:
            audio = AudioFileClip(audio_path)
            # Duration based on audio, or a minimum if audio is empty
            duration = max(audio.duration, 1.0) if audio.duration > 0 else 5.0
            
            clip = ImageClip(image_path).set_duration(duration)
            # Add a slight "breathing" zoom effect to make it feel 'alive'
            # Note: The zoom lambda requires a resize operation which moviepy can do 
            # if we apply it properly.
            clip = clip.resize(lambda t: 1 + 0.02*t) 
            clip = clip.set_audio(audio)
            
            clip.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac")
        except Exception as e:
            logger.error(f"Simulated lipsync failed: {e}")
            # Fallback to just the image without audio if it fails
            clip = ImageClip(image_path).set_duration(5.0)
            clip.write_videofile(output_path, fps=24, codec="libx264")
            
        return output_path
