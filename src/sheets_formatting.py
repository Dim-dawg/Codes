from typing import Any, List, Dict
from src.utils import hex_to_rgb

def build_format_requests(sheet_id: int, last_row: int, row_formats: List[Dict[str, Any]], last_day: int, total_cols: int, blueprint: Dict[str, Any]) -> List[Dict[str, Any]]:
    h_style = blueprint["headers"]["style"]
    requests = [
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {
                        "frozenRowCount": blueprint["frozen_rows"],
                        "frozenColumnCount": blueprint["frozen_cols"],
                    },
                },
                "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount",
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 2, "startColumnIndex": 0, "endColumnIndex": 2},
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {"red": 0.95, "green": 0.95, "blue": 0.95},
                        "textFormat": {"bold": True},
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat)",
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 2, "startColumnIndex": 2, "endColumnIndex": 3},
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {"red": 0.95, "green": 0.95, "blue": 0.95},
                        "textFormat": {"bold": True},
                        "horizontalAlignment": "RIGHT"
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 1, "endColumnIndex": 2},
                "cell": {"userEnteredFormat": {"numberFormat": {"type": blueprint["controls"]["year"]["format"], "pattern": blueprint["controls"]["year"]["pattern"]}}},
                "fields": "userEnteredFormat.numberFormat",
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 1, "endColumnIndex": 2},
                "cell": {"userEnteredFormat": {"numberFormat": {"type": blueprint["controls"]["month"]["format"]}}},
                "fields": "userEnteredFormat.numberFormat",
            }
        },
        {
            "setDataValidation": {
                "range": {"sheetId": sheet_id, "startRowIndex": 1, "endRowIndex": 2, "startColumnIndex": 3, "endColumnIndex": 4},
                "rule": {"condition": {"type": "BOOLEAN"}}
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 2, "endRowIndex": 3, "startColumnIndex": 0, "endColumnIndex": 34},
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": hex_to_rgb(h_style["bg"]),
                        "textFormat": {"foregroundColor": hex_to_rgb(h_style["text"]), "bold": h_style["bold"]},
                        "horizontalAlignment": h_style["align"],
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
            }
        },
        {
            "setBasicFilter": {
                "filter": {
                    "range": {"sheetId": sheet_id, "startRowIndex": 2, "endRowIndex": last_row, "startColumnIndex": 0, "endColumnIndex": total_cols}
                }
            }
        },
        {
            "updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 1},
                "properties": {"pixelSize": 220},
                "fields": "pixelSize",
            }
        },
        {
            "updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 1, "endIndex": 3},
                "properties": {"pixelSize": 110},
                "fields": "pixelSize",
            }
        },
        {
            "updateDimensionProperties": {
                "range": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 3, "endIndex": total_cols},
                "properties": {"pixelSize": 42},
                "fields": "pixelSize",
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 2, "endRowIndex": 3, "startColumnIndex": 0, "endColumnIndex": total_cols},
                "cell": {
                    "userEnteredFormat": {
                        "verticalAlignment": "MIDDLE",
                        "wrapStrategy": "CLIP",
                    }
                },
                "fields": "userEnteredFormat(verticalAlignment,wrapStrategy)",
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 3, "endRowIndex": last_row, "startColumnIndex": 0, "endColumnIndex": 1},
                "cell": {
                    "userEnteredFormat": {
                        "horizontalAlignment": "LEFT",
                    }
                },
                "fields": "userEnteredFormat.horizontalAlignment",
            }
        },
        {
            "repeatCell": {
                "range": {"sheetId": sheet_id, "startRowIndex": 3, "endRowIndex": last_row, "startColumnIndex": 1, "endColumnIndex": total_cols},
                "cell": {
                    "userEnteredFormat": {
                        "horizontalAlignment": "CENTER",
                    }
                },
                "fields": "userEnteredFormat.horizontalAlignment",
            }
        },
    ]

    for item in row_formats:
        row_index = item["row"] - 1
        kind = item["kind"]
        if kind == "section":
            color = hex_to_rgb(item["color"])
            requests.append({
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": row_index, "endRowIndex": row_index + 1, "startColumnIndex": 0, "endColumnIndex": total_cols},
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": color,
                            "textFormat": {"foregroundColor": {"red": 1, "green": 1, "blue": 1}, "bold": True},
                            "horizontalAlignment": "LEFT",
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
                }
            })
        elif kind == "total":
            color = hex_to_rgb(item["color"])
            requests.append({
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": row_index, "endRowIndex": row_index + 1, "startColumnIndex": 0, "endColumnIndex": total_cols},
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": color,
                            "textFormat": {"foregroundColor": {"red": 1, "green": 1, "blue": 1}, "bold": True},
                            "horizontalAlignment": "LEFT"
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
                }
            })
            requests.append({
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": row_index, "endRowIndex": row_index + 1, "startColumnIndex": 1, "endColumnIndex": total_cols},
                    "cell": {
                        "userEnteredFormat": {
                            "numberFormat": {"type": "CURRENCY", "pattern": "$#,##0.00;$(#,##0.00)"}
                        }
                    },
                    "fields": "userEnteredFormat.numberFormat",
                }
            })
        elif kind == "summary":
            requests.append({
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": row_index, "endRowIndex": row_index + 1, "startColumnIndex": 0, "endColumnIndex": 3},
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"bold": True},
                            "backgroundColor": {"red": 0.98, "green": 0.98, "blue": 0.98},
                            "horizontalAlignment": "LEFT"
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,backgroundColor,horizontalAlignment)",
                }
            })
            requests.append({
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": row_index, "endRowIndex": row_index + 1, "startColumnIndex": 1, "endColumnIndex": 3},
                    "cell": {
                        "userEnteredFormat": {
                            "numberFormat": {"type": "CURRENCY", "pattern": "$#,##0.00;$(#,##0.00)"}
                        }
                    },
                    "fields": "userEnteredFormat.numberFormat",
                }
            })
            requests.append({
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": row_index, "endRowIndex": row_index + 1, "startColumnIndex": 3, "endColumnIndex": total_cols},
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {"red": 1, "green": 1, "blue": 1},
                        }
                    },
                    "fields": "userEnteredFormat.backgroundColor",
                }
            })
        elif kind == "category":
            requests.append({
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": row_index, "endRowIndex": row_index + 1, "startColumnIndex": 0, "endColumnIndex": total_cols},
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
                            "textFormat": {"bold": True, "italic": True},
                            "horizontalAlignment": "LEFT",
                        }
                    },
                    "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment)",
                }
            })
        elif kind == "entity":
            if item["row"] % 2 == 0:
                requests.append({
                    "repeatCell": {
                        "range": {"sheetId": sheet_id, "startRowIndex": row_index, "endRowIndex": row_index + 1, "startColumnIndex": 0, "endColumnIndex": total_cols},
                        "cell": {"userEnteredFormat": {"backgroundColor": {"red": 0.97, "green": 0.98, "blue": 0.98}}},
                        "fields": "userEnteredFormat.backgroundColor",
                    }
                })
            requests.append({
                "repeatCell": {
                    "range": {"sheetId": sheet_id, "startRowIndex": row_index, "endRowIndex": row_index + 1, "startColumnIndex": 1, "endColumnIndex": total_cols},
                    "cell": {
                        "userEnteredFormat": {
                            "numberFormat": {"type": "CURRENCY", "pattern": "$#,##0.00;$(#,##0.00)"}
                        }
                    },
                    "fields": "userEnteredFormat.numberFormat",
                }
            })

    return requests
