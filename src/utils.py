from typing import Dict

def hex_to_rgb(value: str) -> Dict[str, float]:
    """Converts a hex color string to a normalized RGB dictionary for Google Sheets API."""
    value = value.lstrip("#")
    if len(value) != 6:
        return {"red": 0, "green": 0, "blue": 0}
    return {
        "red": int(value[0:2], 16) / 255,
        "green": int(value[2:4], 16) / 255,
        "blue": int(value[4:6], 16) / 255,
    }

def column_letter(col: int) -> str:
    """Converts a 1-based column index to a Google Sheets column letter (e.g., 1 -> A, 27 -> AA)."""
    result = ""
    current = col
    while current > 0:
        mod = (current - 1) % 26
        result = chr(65 + mod) + result
        current = (current - 1) // 26
    return result

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
