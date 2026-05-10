import os
from google import genai
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

api_key = os.getenv("GEMINI_API_KEY") or os.getenv("VERTEX_API_KEY")

if not api_key:
    print("No API Key found.")
else:
    client = genai.Client(api_key=api_key)
    print("--- Gemini API Models ---")
    try:
        for m in client.models.list():
            print(f"Model: {m.name}")
    except Exception as e:
        print(f"Error listing Gemini models: {e}")

    # Try Vertex if project is set
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    if project:
        print("\n--- Vertex AI Models ---")
        try:
            # Vertex usually doesn't support list_models via API key easily without OAuth
            client_v = genai.Client(vertexai=True, project=project, location="us-central1")
            for m in client_v.models.list():
                print(f"Vertex Model: {m.name}")
        except Exception as e:
            print(f"Error listing Vertex models: {e}")
