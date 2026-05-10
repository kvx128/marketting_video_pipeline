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
            # Compatibility for MoviePy which expects PIL.Image.ANTIALIAS
            resampling = getattr(Image, 'Resampling', None)
            resample_val = getattr(resampling, 'LANCZOS', 1) if resampling else 1
            setattr(Image, 'ANTIALIAS', resample_val)
            
        from moviepy.editor import ImageClip, AudioFileClip
        
        try:
            audio = AudioFileClip(audio_path)
            # Duration based on audio, or a minimum if audio is empty
            audio_duration = getattr(audio, 'duration', 0)
            if audio_duration is None:
                audio_duration = 0
            duration = max(float(audio_duration), 1.0) if audio_duration > 0 else 5.0
            
            # Ensure audio is exactly the same duration as the clip to prevent buffer issues
            # during concatenation/composition in MoviePy.
            audio = audio.set_duration(duration)
            
            clip = ImageClip(image_path).set_duration(duration)
            # Add a slight "breathing" zoom effect to make it feel 'alive'
            clip = clip.resize(lambda t: 1 + 0.02*t) 
            clip = clip.set_audio(audio)
            
            # Explicitly set fps and audio settings
            clip.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac", temp_audiofile='temp-audio.m4a', remove_temp=True)
        except Exception as e:
            logger.error(f"Simulated lipsync failed: {e}")
            # Fallback to just the image without audio if it fails
            clip = ImageClip(image_path).set_duration(5.0)
            clip.write_videofile(output_path, fps=24, codec="libx264")
            
        return output_path
