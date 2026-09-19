"""Thin Gemini client wrapper. Isolated so ai_service.py can swap providers.
GEMINI_API_KEY is read from .env server-side only; never sent to the frontend.
"""

import os

from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

PROMPT_TEMPLATE = """Extract structured shift-scheduling requirements from this text.
Return ONLY valid JSON with these fields (use null/[] when unknown):
staffing_count (int), roles (list[str]), skills (list[str]),
required_certifications (list[str]), days (list[str]),
shift_start_time ("HH:MM"), shift_end_time ("HH:MM"), max_hours (int),
min_rest_hours (int), preferences (list[str]), notes (str).

Text: {text}"""


def call_gemini(text: str) -> str:
    """Returns raw text response from Gemini. Raises on any failure."""
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GEMINI_API_KEY)
    response = client.models.generate_content(
        model="gemini-flash-lite-latest",
        contents=PROMPT_TEMPLATE.format(text=text),
        config=types.GenerateContentConfig(http_options=types.HttpOptions(timeout=20000)),
    )
    return response.text
