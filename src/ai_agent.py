import os
import json
import requests
from datetime import datetime
from typing import Any, Dict, Optional
from .supabase_service import SupabaseService
from .config import config

class FinanceAgent:
    def __init__(self):
        self.api_key = config.GEMINI_API_KEY
        if not self.api_key:
            raise ValueError("Missing GEMINI_API_KEY in configuration")
        
        self.db = SupabaseService()
        # Updated to v1 for better stability
        self.endpoint = "https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent"
        self.system_prompt = (
            "You are Cipher Money AI, a elite financial intelligence agent. "
            "You analyze real-time budget and transaction data from Supabase. "
            "Be concise, professional, and data-driven. "
            "Always use specific profile names and exact dollar amounts. "
            "Format your responses using Markdown for clarity."
        )

    def _fetch_context(self, month: str) -> str:
        """Gathers all relevant financial context for the AI."""
        try:
            profiles = self.db.fetch_profiles()
            budgets = self.db.fetch_budgets(month)
            transactions = self.db.fetch_transactions(month)
            
            context = {
                "month": month,
                "profiles_summary": [{"name": p["name"], "cat": p.get("default_category", {}).get("name")} for p in profiles],
                "budgets": budgets,
                "recent_transactions": transactions[:50] # Top 50 recent
            }
            return json.dumps(context, indent=2)
        except Exception as e:
            return f"Error fetching context: {str(e)}"

    def ask(self, query: str, history: str = "", month: Optional[str] = None) -> str:
        """Analyzes data and responds to user queries."""
        target_month = month or datetime.now().strftime("%Y-%m")
        context = self._fetch_context(target_month)
        
        full_prompt = (
            f"SYSTEM: {self.system_prompt}\n\n"
            f"FINANCIAL_DATA (Supabase):\n{context}\n\n"
            f"CHAT_HISTORY:\n{history}\n\n"
            f"USER_QUERY: {query}"
        )

        payload = {
            "contents": [{"parts": [{"text": full_prompt}]}],
            "generationConfig": {
                "maxOutputTokens": 800,
                "temperature": 0.1,
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
            return f"❌ AI Analysis Error: {str(e)}"

if __name__ == "__main__":
    agent = FinanceAgent()
    print(agent.ask("How much did I spend on Bank Fees in 2025-02?", month="2025-02"))
