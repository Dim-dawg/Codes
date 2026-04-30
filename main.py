import os
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime
from collections import defaultdict

# Core Service Imports
from src.sync_engine import BudgetSyncApp
from src.ai_agent import FinanceAgent
from src.logger import setup_logger

# Initialize Logger
logger = setup_logger("hub_api")

app = FastAPI(title="Cipher Money Hub API")

# 🛡️ SECURITY: CORS Configuration
# Only allow the local dashboard to communicate with the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Change to specific domain in production
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Resolve absolute path to dashboard directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DASHBOARD_DIR = os.path.join(BASE_DIR, "dashboard")

class SyncRequest(BaseModel):
    month: Optional[str] = None

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.now()
    response = await call_next(request)
    duration = datetime.now() - start_time
    logger.info(f"{request.method} {request.url.path} | Status: {response.status_code} | Duration: {duration}")
    return response

@app.post("/api/sync")
async def trigger_sync(req: SyncRequest):
    month_year = req.month or datetime.now().strftime("%Y-%m")
    logger.info(f"Triggering Atomic Sync for {month_year}")
    try:
        sync_app = BudgetSyncApp()
        result = sync_app.run_sync(month_year)
        return result
    except Exception as e:
        logger.error(f"Sync failed for {month_year}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Sync Error. Check logs for details.")

@app.post("/api/sync/profiles")
async def sync_profiles():
    logger.info("Triggering Profile Metadata Sync")
    try:
        from scripts.sync_profiles import sync_profiles_to_sheet
        count = sync_profiles_to_sheet()
        return {"ok": True, "synced": count}
    except Exception as e:
        logger.error(f"Profile sync failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Profile Sync Error.")

@app.post("/api/chat")
async def chat(req: Dict[str, str]):
    query = req.get("query")
    month = req.get("month", datetime.now().strftime("%Y-%m"))
    logger.info(f"AI Query received for {month}")
    try:
        agent = FinanceAgent()
        response = agent.ask(query, "", month)
        return {"response": response}
    except Exception as e:
        logger.error(f"AI Chat failed: {str(e)}")
        raise HTTPException(status_code=500, detail="AI Service unavailable.")

@app.get("/api/summary/{month}")
async def get_summary(month: str):
    try:
        sync_app = BudgetSyncApp()
        profiles = sync_app.db.fetch_profiles()
        budgets = sync_app.db.fetch_budgets(month)
        transactions = sync_app.db.fetch_transactions(month)
        
        budget_map = {b["category_id"]: float(b.get("amount") or 0) for b in budgets}
        actual_map = defaultdict(float)
        for t in transactions:
            actual_map[t["category_id"]] += abs(float(t.get("amount_signed") or 0))
            
        category_data = {}
        for p in profiles:
            cat = p.get("default_category") or {}
            cat_id = p.get("default_category_id")
            cat_name = cat.get("name") or "Uncategorized"
            if cat_name not in category_data:
                category_data[cat_name] = {"planned": 0.0, "actual": 0.0}
            category_data[cat_name]["planned"] += budget_map.get(cat_id, 0.0)
            category_data[cat_name]["actual"] += actual_map.get(cat_id, 0.0)
            
        summary = [{"category": k, **v} for k, v in category_data.items() if v["planned"] > 0 or v["actual"] > 0]
        summary.sort(key=lambda x: x["planned"], reverse=True)
        return summary
    except Exception as e:
        logger.error(f"Summary fetch failed for {month}: {str(e)}")
        raise HTTPException(status_code=500, detail="Data fetch error.")

@app.get("/api/profiles")
async def get_profiles():
    try:
        sync_app = BudgetSyncApp()
        return sync_app.db.fetch_profiles()
    except Exception as e:
        logger.error(f"Profiles fetch failed: {str(e)}")
        raise HTTPException(status_code=500, detail="DB Error.")

@app.get("/api/goals")
async def get_goals():
    try:
        sync_app = BudgetSyncApp()
        return sync_app.db.fetch_goals()
    except Exception as e:
        logger.error(f"Goals fetch failed: {str(e)}")
        raise HTTPException(status_code=500, detail="DB Error.")

# Static Asset Serving (Hardened Paths)
@app.get("/style.css")
async def get_css():
    return FileResponse(os.path.join(DASHBOARD_DIR, "style.css"), media_type="text/css")

@app.get("/app.js")
async def get_js():
    return FileResponse(os.path.join(DASHBOARD_DIR, "app.js"), media_type="application/javascript")

@app.get("/")
async def get_index():
    return FileResponse(os.path.join(DASHBOARD_DIR, "index.html"))

app.mount("/", StaticFiles(directory=DASHBOARD_DIR), name="dashboard")

if __name__ == "__main__":
    logger.info("🚀 Starting Cipher Money Neural Hub on http://0.0.0.0:8000")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="warning")
