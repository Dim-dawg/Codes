import requests
import calendar
from typing import Any, List, Dict
from src.config import config

class SupabaseService:
    def __init__(self):
        self.base_url = config.SUPABASE_URL.rstrip("/")
        self.headers = {
            "apikey": config.SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {config.SUPABASE_SERVICE_ROLE_KEY}",
        }
        self.user_id = config.SUPABASE_USER_ID

    def _get(self, table: str, params: Dict[str, str]) -> List[Dict[str, Any]]:
        response = requests.get(
            f"{self.base_url}/rest/v1/{table}",
            headers=self.headers,
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def fetch_profiles(self) -> List[Dict[str, Any]]:
        return self._get(
            "profiles",
            {
                "user_id": f"eq.{self.user_id}",
                "select": "id,name,type,address,notes,default_category_id,default_category:categories(name,account_type)",
                "order": "name.asc",
            },
        )

    def fetch_budgets(self, month_year: str) -> List[Dict[str, Any]]:
        return self._get(
            "budgets",
            {
                "user_id": f"eq.{self.user_id}",
                "month": f"eq.{month_year}",
                "select": "category_id,amount",
            },
        )

    def fetch_transactions(self, month_year: str) -> List[Dict[str, Any]]:
        year, month = month_year.split("-")
        next_month = int(month) + 1 if int(month) < 12 else 1
        next_year = int(year) if int(month) < 12 else int(year) + 1
        return self._get(
            "transaction_sheet_view",
            {
                "user_id": f"eq.{self.user_id}",
                "and": f"(date.gte.{month_year}-01,date.lt.{next_year}-{next_month:02d}-01)",
                "select": "id,date,amount,amount_signed,direction,profile_id,category_id,category_name,category_account_type,confidence_score,category_method,confidence_band,review_status",
                "order": "date.asc",
            },
        )

    def get_unlinked_transactions(self, month_year: str) -> List[Dict[str, Any]]:
        year, month = month_year.split("-")
        next_month = int(month) + 1 if int(month) < 12 else 1
        next_year = int(year) if int(month) < 12 else int(year) + 1
        try:
            return self._get(
                "transaction_sheet_view",
                {
                    "user_id": f"eq.{self.user_id}",
                    "profile_id": "is.null",
                    "and": f"(date.gte.{month_year}-01,date.lt.{next_year}-{next_month:02d}-01)",
                    "select": "id,date,amount,amount_signed,direction,category_id,category_name,category_account_type,confidence_score,category_method,review_status",
                    "order": "date.asc",
                },
            )
        except Exception:
            return []
    def fetch_goals(self) -> List[Dict[str, Any]]:
        return self._get(
            "goals",
            {
                "user_id": f"eq.{self.user_id}",
                "select": "id,name,target_amount,current_amount",
                "order": "name.asc",
            },
        )
