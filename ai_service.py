import os
import json
import requests
from typing import Any, Dict
from dotenv import load_dotenv

load_dotenv()

class CipherAIAgent:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("Missing GEMINI_API_KEY in .env file")
        
        self.endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
        self.system_prompt = (
            "You are Cipher Money AI, a high-performance financial intelligence agent. "
            "You have access to a user's real-time financial data including profiles, budgets, and transactions. "
            "Your goal is to provide concise, accurate, and professional financial analysis. "
            "Always reference specific entities (profiles) and amounts when answering."
        )

    def ask(self, user_query: str, financial_context: Dict[str, Any]) -> str:
        """
        Sends context + query to Gemini and returns the text response.
        """
        full_prompt = (
            f"SYSTEM: {self.system_prompt}\n\n"
            f"FINANCIAL CONTEXT (Current Data):\n{json.dumps(financial_context, indent=2)}\n\n"
            f"USER QUESTION: {user_query}"
        )

        payload = {
            "contents": [{"parts": [{"text": full_prompt}]}],
            "generationConfig": {
                "maxOutputTokens": 1000,
                "temperature": 0.2, # Lower temperature for higher accuracy in financial analysis
            }
        }

        try:
            response = requests.post(
                f"{self.endpoint}?key={self.api_key}",
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            return result['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            return f"❌ AI Error: {str(e)}"

# Test execution (optional)
if __name__ == "__main__":
    agent = CipherAIAgent()
    print("Cipher AI Agent initialized and ready.")
