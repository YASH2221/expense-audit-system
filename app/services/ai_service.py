import asyncio
import os
import json
import google.generativeai as genai
from typing import Dict, Any
from app.core.config import settings

class AIService:
    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        # Using gemini-1.5-flash for high speed and multimodal (image/pdf) support
        self.model = genai.GenerativeModel('gemini-3-flash-preview')

    async def analyze_receipt(self, file_path: str, claim_amount: float) -> Dict[str, Any]:
        """
        Uses real Gemini AI to analyze the receipt and extract itemized totals.
        """
        if not os.path.exists(file_path):
            raise ValueError(f"File not found at {file_path}")

        try:
            # Load the file bytes
            with open(file_path, "rb") as f:
                file_bytes = f.read()

            # Determine mime type based on extension (simple way)
            mime_type = "image/jpeg" # Default
            if file_path.endswith(".pdf"):
                mime_type = "application/pdf"
            elif file_path.endswith(".png"):
                mime_type = "image/png"

            prompt = f"""
            Identify all line items and their individual amounts from this receipt.
            Calculate the final total of all items.
            The claim amount submitted is {claim_amount}.
            
            Return ONLY a JSON object with this exact structure:
            {{
                "is_match": boolean,
                "extracted_total": float,
                "claim_amount": {claim_amount},
                "items": [{{ "item": string, "amount": float }}],
                "confidence_score": float,
                "ai_remarks": string
            }}
            
            Note: Set is_match to true only if extracted_total matches {claim_amount}.
            """

            # Run in thread pool since genai is synchronous (blocking)
            response = await asyncio.to_thread(
                self.model.generate_content,
                [prompt, {"mime_type": mime_type, "data": file_bytes}]
            )

            # Extract JSON from response text (Gemini sometimes adds markdown blocks)
            text = response.text
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            
            result = json.loads(text.strip())
            return result

        except Exception as e:
            return {
                "is_match": False,
                "extracted_total": 0.0,
                "claim_amount": claim_amount,
                "items": [],
                "confidence_score": 0.0,
                "ai_remarks": f"AI Error: Could not process document. {str(e)}"
            }
