import os
from dotenv import load_dotenv

class Config:
    def __init__(self):
        load_dotenv()
        self.SUPABASE_URL = self._require("SUPABASE_URL")
        self.SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip() or self._require("SUPABASE_ANON_KEY")
        self.SUPABASE_USER_ID = self._require("SUPABASE_USER_ID")
        self.GOOGLE_SHEET_ID = self._require("GOOGLE_SHEET_ID")
        self.GOOGLE_SERVICE_ACCOUNT_FILE = self._require("GOOGLE_SERVICE_ACCOUNT_FILE")
        self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

    def _require(self, name: str) -> str:
        value = os.getenv(name, "").strip()
        if not value:
            raise RuntimeError(f"Missing required environment variable: {name}")
        return value

config = Config()
