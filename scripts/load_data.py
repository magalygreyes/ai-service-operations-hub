"""
Breezio Service Hub: database loader
Slice 1, Phase 3

Builds the database and loads the synthetic data in one run:
  1. sql/01_schema.sql          tables, constraints, triggers (drops and recreates)
  2. sql/02_reference_data.sql  teams, categories, routing_config
  3. data/*.csv                 employees, requests, AI predictions, routing,
                                approvals, request events (from generate_data.py)

The connection string is read from a .env file in the repo folder:
    DATABASE_URL=postgresql://postgres.xxxx:PASSWORD@aws-0-xx.pooler.supabase.com:5432/postgres
The .env file is listed in .gitignore, so the password never reaches GitHub.

Run from the repo folder:
    py -3.12 scripts/load_data.py
"""

import os
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parent.parent
SQL_FILES = ["sql/01_schema.sql", "sql/02_reference_data.sql"]
# Parents before children, so every foreign key already exists when a row arrives.
CSV_TABLES = [
    "employees",
    "requests",
    "ai_predictions",
    "routing_decisions",
    "approvals",
    "request_events",
]


def read_env():
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"'))
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL is missing. Add it to the .env file (see .env.example).")
    return url


def main():
    missing = [t for t in CSV_TABLES if not (ROOT / "data" / f"{t}.csv").exists()]
    if missing:
        sys.exit(f"Missing CSVs: {', '.join(missing)}. Run scripts/generate_data.py first.")

    with psycopg.connect(read_env()) as conn:
        with conn.cursor() as cur:
            for f in SQL_FILES:
                print(f"Running {f} ...")
                cur.execute((ROOT / f).read_text(encoding="utf-8"))

            for table in CSV_TABLES:
                path = ROOT / "data" / f"{table}.csv"
                with path.open(encoding="utf-8") as fh:
                    header = fh.readline().strip()
                    with cur.copy(
                        f"COPY {table} ({header}) FROM STDIN WITH (FORMAT csv)"
                    ) as copy:
                        while chunk := fh.read(1 << 16):
                            copy.write(chunk)
                cur.execute(f"select count(*) from {table}")
                print(f"Loaded {table:<18} {cur.fetchone()[0]:>7,} rows")

        conn.commit()
    print("\nDone. The database is built and loaded.")


if __name__ == "__main__":
    main()
