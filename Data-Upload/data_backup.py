"""
Database Backup Script
Dumps covariablesv1 (Brazil) and covariables_indonesia using pg_dump -Fc.
Output: Z:\ENVIROMICS\DATABASE_BACKUP\database\
"""

import os
import subprocess
from pathlib import Path
from datetime import date

# ----------------- CONFIG -----------------
PG_DUMP = r"C:\Program Files\PostgreSQL\13\bin\pg_dump.exe"

DATABASES = [
    {"name": "covariablesv1",         "host": "localhost", "port": "5433", "user": "postgres", "pass": "postgres"},
    {"name": "covariables_indonesia",  "host": "localhost", "port": "5433", "user": "postgres", "pass": "postgres"},
]

OUTPUT_DIR = Path(r"Z:\ENVIROMICS\DATABASE_BACKUP\database")
TODAY = date.today().isoformat()  # e.g. 2026-04-17

# ----------------- MAIN -----------------
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

for db in DATABASES:
    out_file = OUTPUT_DIR / f"{db['name']}_{TODAY}.dump"
    print(f"Backing up {db['name']} → {out_file} ...")

    env = os.environ.copy()
    env["PGPASSWORD"] = db["pass"]

    cmd = [
        PG_DUMP,
        "-h", db["host"],
        "-p", db["port"],
        "-U", db["user"],
        "-Fc",           # custom compressed format
        "-f", str(out_file),
        db["name"],
    ]

    result = subprocess.run(cmd, env=env, capture_output=True, text=True)

    if result.returncode == 0:
        size_mb = out_file.stat().st_size / (1024 * 1024)
        print(f"  ✓ Done ({size_mb:.1f} MB)")
    else:
        print(f"  ✗ FAILED:\n{result.stderr}")

print("\nAll backups complete.")
print(f"Location: {OUTPUT_DIR}")
