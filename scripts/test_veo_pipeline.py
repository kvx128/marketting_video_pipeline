import os
import sys
import django

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from app.services.asset_manager import AssetManager
from app.services.veo_engine import VeoEngine

def test_veo_caching_flow():
    job_id = "veo-test-001"
    manager = AssetManager(job_id)
    veo = VeoEngine()

    # 1. Define a complex cinematic prompt
    prompt = "A futuristic cyberpunk Mumbai at night, neon lights reflecting in puddles, cinematic drone shot, 4k, hyper-realistic."
    
    print("\n--- Running Veo Pipeline Test ---")
    
    # 2. Get Asset (This will trigger the symlink logic)
    # Using the new get_asset method with a custom generator (Veo)
    asset_path = manager.get_asset(
        prompt=prompt, 
        extension=".mp4", 
        generator_func=lambda path: veo.generate_animated_clip(prompt, path)
    )

    print(f"Asset path returned: {asset_path}")
    
    # 3. Verification
    # Note: On Windows, os.path.islink only works if Developer Mode is on or 
    # if the script is run with admin privileges.
    is_link = os.path.islink(asset_path)
    print(f"Is this a symlink to global storage? {is_link}")
    
    if is_link:
        target = os.readlink(asset_path)
        print(f"Points to global source: {target}")
    else:
        print("Note: If not a link, it might have fallen back to a copy (common on Windows without Dev Mode).")

    # 4. Check global storage
    asset_hash = manager.get_asset_hash(prompt)
    global_file = os.path.join(manager.global_path, f"{asset_hash}.mp4")
    print(f"Global file exists: {os.path.exists(global_file)}")

if __name__ == "__main__":
    test_veo_caching_flow()
