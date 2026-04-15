"""
TerraClimate Indonesia Upload Script
Uploads monthly TerraClimate GeoTIFFs into PostGIS with partitions by year.

Expected file naming: terraclim_<var>_<year>_<month>.tif
"""

import os
import re
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from multiprocessing import Pool
import psycopg2

# ----------------- CONFIG -----------------
INPUT_DIR = Path(r"Z:\ENVIROMICS\terraclimate\Indonesia_TerraClimate_Resampled")
LOG_FILE = INPUT_DIR.parent / "upload_terraclim_indonesia_log.txt"

DB_HOST = "localhost"
DB_PORT = "5433"
DB_NAME = "covariables_indonesia"
DB_USER = "postgres"
DB_PASS = "postgres"

TABLE_NAME = "terraclim_data"  # change if needed
NUM_WORKERS = 12

# ----------------- HELPERS -----------------

def parse_file_info(path: Path):
    # terraclim_<var>_<year>_<month>.tif
    match = re.match(r"terraclim_(.+)_(\d{4})_(\d{2})\.tif$", path.name)
    if not match:
        return None
    var_name, year, month = match.group(1), int(match.group(2)), int(match.group(3))
    date_id = f"{year}-{month:02d}-01"
    return var_name, year, date_id


def ensure_table_and_partitions(years):
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASS
    )
    cur = conn.cursor()

    # Drop table if it exists (will also drop partitions)
    cur.execute(f"DROP TABLE IF EXISTS {TABLE_NAME} CASCADE;")
    cur.execute(f"""
        CREATE TABLE {TABLE_NAME} (
            date_id DATE NOT NULL,
            var_name TEXT NOT NULL,
            rid SERIAL,
            rast RASTER,
            PRIMARY KEY (date_id, var_name, rid)
        ) PARTITION BY RANGE (date_id)
    """)

    for y in years:
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME}_{y}
            PARTITION OF {TABLE_NAME}
            FOR VALUES FROM ('{y}-01-01') TO ('{y+1}-01-01')
        """)

    conn.commit()
    conn.close()


def fix_raster2pgsql_output(sql, var_name, date_id):
    raster_values = re.findall(r"'[0-9A-F]+'::raster", sql)
    if not raster_values:
        return []

    statements = []
    for raster_value in raster_values:
        statements.append(
            f"INSERT INTO {TABLE_NAME} (date_id, var_name, rast) "
            f"VALUES ('{date_id}', '{var_name}', {raster_value});"
        )
    return statements


def upload_one(file_path: Path):
    info = parse_file_info(file_path)
    if not info:
        return "error", file_path.name, "filename pattern mismatch"

    var_name, year, date_id = info

    try:
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASS
        )
        cur = conn.cursor()
        cur.execute(
            f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE var_name=%s AND date_id=%s",
            (var_name, date_id)
        )
        exists = cur.fetchone()[0] > 0
        conn.close()

        if exists:
            return "skipped", file_path.name, None

        cmd = [
            "raster2pgsql",
            "-a",
            "-s", "4326",
            "-t", "100x100",
            "-x",
            "-I",
            str(file_path),
            TABLE_NAME
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            return "error", file_path.name, res.stderr[:400]

        sql_statements = fix_raster2pgsql_output(res.stdout, var_name, date_id)
        if not sql_statements:
            return "error", file_path.name, "Could not parse raster2pgsql output"

        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASS
        )
        cur = conn.cursor()
        for stmt in sql_statements:
            cur.execute(stmt)
        conn.commit()
        conn.close()

        return "success", file_path.name, f"{len(sql_statements)} tiles"

    except Exception as e:
        return "error", file_path.name, str(e)[:400]


# ----------------- MAIN -----------------

if __name__ == "__main__":
    print("TerraClimate Indonesia upload")
    print(f"Input: {INPUT_DIR}")
    print(f"Table: {TABLE_NAME}")

    tiff_files = sorted(INPUT_DIR.glob("terraclim_*.tif"))
    if not tiff_files:
        print(f"❌ No GeoTIFF files found in {INPUT_DIR}")
        sys.exit(1)

    years = sorted({parse_file_info(f)[1] for f in tiff_files if parse_file_info(f)})
    ensure_table_and_partitions(years)

    success = 0
    skipped = 0
    failed = 0
    failed_list = []

    with Pool(processes=NUM_WORKERS) as pool:
        for i, (status, name, msg) in enumerate(pool.imap_unordered(upload_one, tiff_files), 1):
            if status == "success":
                success += 1
                print(f"[{i}/{len(tiff_files)}] {name} ✓")
            elif status == "skipped":
                skipped += 1
                print(f"[{i}/{len(tiff_files)}] {name} ⏭️")
            else:
                failed += 1
                print(f"[{i}/{len(tiff_files)}] {name} ✗ {msg}")
                failed_list.append((name, msg))

    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write(f"TerraClimate Indonesia Upload Log\n")
        f.write(f"Date: {datetime.now()}\n")
        f.write(f"Total: {len(tiff_files)}\n")
        f.write(f"Success: {success}\n")
        f.write(f"Skipped: {skipped}\n")
        f.write(f"Failed: {failed}\n")
        if failed_list:
            f.write("\nFailed files:\n")
            for name, msg in failed_list:
                f.write(f"  {name}: {msg}\n")

    print("Done.")
    print(f"Log: {LOG_FILE}")
