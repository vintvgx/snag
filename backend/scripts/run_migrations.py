"""Apply any backend/migrations/*.sql files that haven't been run yet.

Usage (from backend/):
    python scripts/run_migrations.py

Requires DATABASE_URL in the environment (backend/.env) — use Supabase's
*direct* Postgres connection string (Project Settings -> Database ->
Connection string -> URI), not the pgbouncer pooler: DDL doesn't always
play well with transaction-mode pooling.

Tracks what's already been applied in a public.schema_migrations table, so
re-running this is safe — only new files get executed.
"""

import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv()

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def main():
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        sys.exit(
            "DATABASE_URL is not set. Add Supabase's direct Postgres connection "
            "string (Project Settings -> Database -> Connection string -> URI) "
            "to backend/.env as DATABASE_URL."
        )

    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migration_files:
        print("No migration files found.")
        return

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                create table if not exists public.schema_migrations (
                    filename text primary key,
                    applied_at timestamptz not null default now()
                )
                """
            )
            cur.execute("select filename from public.schema_migrations")
            applied = {row[0] for row in cur.fetchall()}
        conn.commit()

        for path in migration_files:
            if path.name in applied:
                print(f"skip  {path.name} (already applied)")
                continue

            print(f"apply {path.name}")
            with conn.cursor() as cur:
                cur.execute(path.read_text())
                cur.execute(
                    "insert into public.schema_migrations (filename) values (%s)",
                    (path.name,),
                )
            conn.commit()
            print(f"  done")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
