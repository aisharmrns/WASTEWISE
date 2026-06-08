import os
import mimetypes
from pathlib import Path
import streamlit as st
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

MODEL_NAME = "gemini-2.5-flash"

# ==========================================
# PYDANTIC SCHEMA FOR STRUCTURED OUTPUTS
# ==========================================
class FoodIdentificationResult(BaseModel):
    item: str = Field(description="The generic name of the main food item identified.")
    category: str = Field(description="The broader food category (e.g., Leafy Vegetable, Grain, Meat, Fruit).")
    confidence: int = Field(description="Confidence rating score from 0 to 100.")
    condition: str = Field(description="Must choose exactly one: fresh, rotten, expired, or unknown.")
    observation: str = Field(description="A short, practical operational kitchen observation.")


def get_gemini_client():
    """
    Dynamically initialize the Gemini Client using Streamlit Cloud Secrets.
    Explicitly forces the token environment setup to prevent 401 OAuth errors.
    """
    if "GEMINI_API_KEY" not in st.secrets:
        st.error("🚨 Streamlit configuration error: 'GEMINI_API_KEY' secret is missing.")
        st.stop()
        
    api_key_str = st.secrets["GEMINI_API_KEY"]
    
    os.environ["GEMINI_API_KEY"] = api_key_str
    os.environ["GOOGLE_API_KEY"] = api_key_str
    
    return genai.Client(api_key=api_key_str)


def get_mime_type(image_path: str) -> str:
    """
    Detect image MIME type. Default to image/jpeg if unknown.
    """
    mime_type, _ = mimetypes.guess_type(image_path)
    return mime_type if mime_type is not None else "image/jpeg"


def identify_food_with_gemini(image_path: str) -> dict:
    """
    Identify food item from an image using Gemini API with native Pydantic validation.
    Bypasses string parsing completely for error-free execution.
    """
    try:
        client = get_gemini_client()
        path = Path(image_path)
        image_bytes = path.read_bytes()
        mime_type = get_mime_type(str(path))

        prompt = """
        You are an AI assistant for a kitchen food waste tracking system.
        Analyze the provided image and extract the metrics matching the required structure.
        If the image is unclear or empty, populate the item as 'Unknown'.
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
                response_mime_type="application/json",
                response_schema=FoodIdentificationResult, 
                temperature=0.1 
            )
        )

        result: FoodIdentificationResult = response.parsed

        return {
            "item": result.item,
            "category": result.category,
            "confidence": max(0, min(int(result.confidence), 100)),
            "condition": result.condition.lower(),
            "observation": result.observation if result.observation else "Worker should confirm the AI result before saving."
        }

    except Exception as error:
        return {
            "item": "Unknown",
            "category": "Unknown",
            "confidence": 0,
            "condition": "unknown",
            "observation": "System Authentication Failed: Verify your cloud API key configuration token." if "401" in str(error) else f"Gemini Analysis Interrupted: {error}"
        }


def generate_waste_suggestion_with_gemini(waste_logs_text: str) -> str:
    """
    Generate food waste reduction suggestions using Gemini API.
    """
    try:
        client = get_gemini_client()

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
