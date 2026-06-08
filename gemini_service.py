import json
import mimetypes
from pathlib import Path

from google import genai
from google.genai import types

MODEL_NAME = "gemini-2.5-flash"
client = genai.Client()

def clean_json_response(text: str) -> dict:
    """
    Convert Gemini response text into a Python dictionary.
    Handles cases where Gemini wraps JSON with extra text markdown blocks.
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(text[start:end])
        raise ValueError("No valid JSON found in Gemini response.")

def get_mime_type(image_path: str) -> str:
    """
    Detect image MIME type. Default to image/jpeg if unknown.
    """
    mime_type, _ = mimetypes.guess_type(image_path)
    return mime_type if mime_type is not None else "image/jpeg"

def identify_food_with_gemini(image_path: str) -> dict:
    """
    Identify food item from an image using Gemini API with structured JSON output.
    """
    try:
        path = Path(image_path)
        image_bytes = path.read_bytes()
        mime_type = get_mime_type(str(path))

        prompt = """
        You are an AI assistant for a kitchen food waste tracking system.
        Identify the main food item in this image.

        Return ONLY valid JSON using this exact format:
        {
            "item": "food name",
            "category": "food category",
            "confidence": 94,
            "condition": "fresh / rotten / expired / unknown",
            "observation": "short practical observation"
        }

        Important:
        - If the image is unclear, set item as "Unknown".
        - Confidence must be a number from 0 to 100.
        - Do not include markdown blocks like ```json.
        - Do not include explanation outside JSON.
        """

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[
                prompt,
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type=mime_type
                )
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )

        result = clean_json_response(response.text)

        return {
            "item": result.get("item", "Unknown"),
            "category": result.get("category", "Unknown"),
            "confidence": int(result.get("confidence", 0)),
            "condition": result.get("condition", "unknown"),
            "observation": result.get(
                "observation",
                "Worker should confirm the AI result before saving."
            )
        }

    except Exception as error:
        return {
            "item": "Unknown",
            "category": "Unknown",
            "confidence": 0,
            "condition": "unknown",
            "observation": f"Gemini food identification failed: {error}"
        }

def generate_waste_suggestion_with_gemini(waste_logs_text: str) -> str:
    """
    Generate food waste reduction suggestions using Gemini API.
    """
    try:
        prompt = f"""
        You are an AI assistant for a kitchen food waste tracking system.
        Based on the waste log data below, give 2 short and practical suggestions
        to reduce food waste.

        Waste log data:
        {waste_logs_text}

        Format:
        1. Suggestion title - explanation.
        2. Suggestion title - explanation.

        Keep the suggestions simple, practical, and suitable for kitchen workers.
        """

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt
        )
        return response.text.strip()

    except Exception as error:
        return f"Gemini suggestion failed: {error}"