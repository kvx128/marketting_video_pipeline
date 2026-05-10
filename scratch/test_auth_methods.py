import os
from google import genai

vertex_token = os.getenv("VERTEX_API_KEY")
gemini_key = os.getenv("GEMINI_API_KEY")

print(f"Vertex Token starts with: {vertex_token[:5] if vertex_token else 'None'}...")
print(f"Gemini Key starts with: {gemini_key[:5] if gemini_key else 'None'}...")

print("\n--- Testing Gemini API with Access Token as api_key ---")
try:
    client = genai.Client(api_key=vertex_token)
    # Just try to list models
    for m in client.models.list():
        print(f"Found model: {m.name}")
        break
    print("Success!")
except Exception as e:
    print(f"Failed: {e}")

print("\n--- Testing Gemini API with Access Token via HTTP Headers (via config) ---")
try:
    # Some SDKs allow passing headers in config
    print("Not implemented in this test yet.")
except Exception as e:
    print(f"Failed: {e}")
