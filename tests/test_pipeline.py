import pytest
import os
from app.services.xml_parser import md_to_xml_validated
from app.services.asset_manager import AssetManager

def test_xml_validation_fails_on_missing_headers(tmp_path):
    # Create a malformed markdown file (missing 'mission' header)
    bad_md = tmp_path / "bad_client.md"
    bad_md.write_text("# Company Name\nTessact\n# Vision\nTo lead AI.")
    
    # We expect a ValueError or an exception from xml validation
    with pytest.raises(Exception) as exc:
        # Assuming the DTD requires mission
        md_to_xml_validated(str(bad_md), 'app/data/purpose.md', 'app/services/video_context.dtd')
    
def test_asset_manager_idempotency(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    manager = AssetManager("test_job")
    prompt = "A luxury watch on a marble table"
    
    # First hash
    hash1 = manager.get_asset_hash(prompt, "image")
    # Second hash for same prompt
    hash2 = manager.get_asset_hash(prompt, "image")
    
    assert hash1 == hash2
