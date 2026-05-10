"""
app/services/video_engine.py
────────────────────────────
Video Composer Engine using MoviePy.

Takes a validated video blueprint and a list of locally cached image assets,
then stitches them together into an MP4 with text overlays, applying a 
minimalist/luxury visual aesthetic.
"""

import logging
import os
from moviepy.editor import ImageClip, TextClip, CompositeVideoClip, concatenate_videoclips, VideoFileClip
from .audio_engine import AudioEngine
from .lipsync_engine import LipSyncEngine

logger = logging.getLogger(__name__)

class VideoComposer:
    def __init__(self, blueprint: dict, asset_paths: dict, job_id: str):
        self.blueprint = blueprint
        # dict mapping scene index (int) to absolute file path (str)
        self.asset_paths = asset_paths
        self.audio_engine = AudioEngine(job_id)
        self.lipsync_engine = LipSyncEngine(job_id)

    def create_scene(self, scene_data: dict, image_path: str):
        """Creates a composite clip for a single scene with image and text overlay."""
        duration = scene_data["duration"]
        
        # Base clip (image or video)
        logger.info("Creating clip for scene %d from %s", scene_data["scene_number"], image_path)
        
        if image_path.lower().endswith(('.mp4', '.mov', '.avi')):
            clip = VideoFileClip(image_path)
            # Make sure it matches the desired duration by looping or clipping
            if clip.duration < duration:
                from moviepy.video.fx.loop import loop
                clip = loop(clip, duration=duration)
            else:
                clip = clip.subclip(0, duration)
        else:
            clip = ImageClip(image_path).set_duration(duration)
        
        overlay_text = scene_data.get("overlay_text", "").strip()
        if overlay_text:
            try:
                # Add "Minimalist" Overlay Text
                # MoviePy requires ImageMagick to be installed for TextClip to work.
                # If ImageMagick is missing, this will raise an Exception.
                txt_clip = TextClip(
                    overlay_text.upper(),  # All caps for that luxury brand feel
                    fontsize=60,
                    color='#F5C518',       # Electric Gold
                    font='DejaVu-Sans-Bold', # Safer Docker default
                    method='caption',
                    size=(1600, None),
                    align='center'
                ).set_position(('center', 850)).set_duration(duration)
                
                # Combine image and text
                # We add a bottom margin to the text so it doesn't touch the very edge
                final_clip = CompositeVideoClip([clip, txt_clip.margin(bottom=100, opacity=0)])
            except Exception as e:
                logger.warning(
                    "Failed to create TextClip for scene %d. Is ImageMagick installed? Error: %s", 
                    scene_data["scene_number"], e
                )
                # Fallback to just the image clip if ImageMagick is not available
                final_clip = clip
        else:
            final_clip = clip
            
        return final_clip

    def assemble_video(self, output_path: str) -> str:
        """Assembles all scenes into a final output MP4, using raw Veo clips directly."""
        logger.info("Assembling video (DIRECT VEO MODE) to %s", output_path)
        clips = []
        
        for i, scene in enumerate(self.blueprint["scenes"]):
            asset_path = self.asset_paths.get(i)
            if not asset_path or not os.path.exists(asset_path):
                logger.warning(f"Asset for scene {i} missing, skipping...")
                continue
                
            # Load the clip (Video or Image)
            if asset_path.lower().endswith(('.mp4', '.mov', '.avi')):
                clip = VideoFileClip(asset_path)
                # Keep it as is, or subclip if it's way too long
                clip_duration = getattr(clip, 'duration', 0) or 0
                if clip_duration > 10:
                    clip = clip.subclip(0, 10)
            else:
                # If it's an image, just show it for 3 seconds
                clip = ImageClip(asset_path).set_duration(3.0)
            
            clips.append(clip)
        
        if not clips:
            raise RuntimeError("No clips generated for assembly.")
            
        logger.info("Concatenating %d raw clips", len(clips))
        # Use 'compose' to handle potential size differences between Veo generations
        final_video = concatenate_videoclips(clips, method="compose")
        
        # Write final video
        final_video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac")
        return output_path
