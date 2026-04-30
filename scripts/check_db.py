import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")

headers = {
    "apikey": key,
    "Authorization": f"Bearer {key}",
    "Content-Type": "application/json"
}

def query_table(table):
    response = requests.get(f"{url}/rest/v1/{table}", headers=headers)
    return response.json()

print("--- CATEGORIES ---")
categories = query_table("categories")
for cat in categories:
    print(f"ID: {cat['id']}, Name: {cat['name']}, Type: {cat.get('account_type')}")

print("\n--- PROFILES (First 10) ---")
profiles = query_table("profiles")
for prof in profiles[:10]:
    print(f"Name: {prof['name']}, Category ID: {prof.get('default_category_id')}")
