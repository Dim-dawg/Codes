from dataclasses import dataclass
from typing import Optional, List, Dict, Any

@dataclass
class Profile:
    id: str
    name: str
    category_name: str
    account_type: str

@dataclass
class Transaction:
    id: str
    date: str
    amount: float
    amount_signed: float
    direction: str
    profile_id: Optional[str]
    category_name: str
    category_account_type: str
    confidence_score: float
    method: str
    review_status: str

@dataclass
class SyncResult:
    worksheet_title: str
    worksheet_gid: int
    profiles_count: int
    rows_written: int
    unlinked_count: int
    unlinked_details: Optional[List[Dict[str, Any]]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "worksheet_title": self.worksheet_title,
            "worksheet_gid": self.worksheet_gid,
            "profiles": self.profiles_count,
            "rows_written": self.rows_written,
            "unlinked_transactions": self.unlinked_count,
            "unlinked_details": self.unlinked_details,
        }
