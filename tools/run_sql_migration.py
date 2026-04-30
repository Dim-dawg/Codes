import argparse
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv


def require_database_url() -> str:
    value = os.getenv("DATABASE_URL", "").strip()
    if not value:
        raise RuntimeError(
            "Missing DATABASE_URL. Add the full Supabase Postgres connection string "
            "to .env, including the database password."
        )
    if "[YOUR-PASSWORD]" in value:
        raise RuntimeError("DATABASE_URL still contains [YOUR-PASSWORD]. Replace it with the real database password.")
    return value


def ensure_psycopg() -> None:
    try:
        import psycopg  # noqa: F401
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "psycopg[binary]>=3.2"])


def run_sql(database_url: str, sql_path: Path) -> None:
    import psycopg

    sql = sql_path.read_text(encoding="utf-8")
    with psycopg.connect(database_url, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()


def main() -> int:
    load_dotenv(".env")
    parser = argparse.ArgumentParser(description="Run a SQL migration against DATABASE_URL.")
    parser.add_argument("sql_file")
    args = parser.parse_args()

    sql_path = Path(args.sql_file)
    if not sql_path.exists():
        raise RuntimeError(f"SQL file not found: {sql_path}")

    database_url = require_database_url()
    ensure_psycopg()
    run_sql(database_url, sql_path)
    print(f"applied: {sql_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
