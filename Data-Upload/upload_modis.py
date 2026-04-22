import psycopg2
from datetime import datetime
DB_HOST = "localhost"
DB_PORT = "5433"
DB_NAME = "covariables_indonesia"
DB_USER = "postgres"
DB_PASS = "postgres"
"""
MODIS 8-day Indonesia Upload Script
Uploads resampled MODIS 8-day GeoTIFFs to PostGIS using raster2pgsql, one file per partition (date).
Assumes output rasters are in OUTPUT_DIR, named modis_et_YYYY_MM_DD.tif.
Parallel upload for speed.
"""

import os
from pathlib import Path
from multiprocessing import Pool, cpu_count
import subprocess
import re

OUTPUT_DIR = Path(r"Z:\ENVIROMICS\Indonesia_modis_resampled")
PG_CONN = "host=localhost dbname=covariables_indonesia user=postgres password=postgres"  # Update as needed
TABLE = "public.et_data"
SRID = 4326
NUM_WORKERS = min(16, cpu_count())
def parse_file_info(path: Path):
    # modis_et_YYYY_MM_DD.tif
    match = re.match(r"modis_et_(\d{4})_(\d{2})_(\d{2})\.tif$", path.name)
    if not match:
        return None
    year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
    date_id = f"{year}-{month:02d}-{day:02d}"
    return year, date_id

def ensure_table_and_partitions(years):
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASS
    )
    cur = conn.cursor()
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE} (
            date_id DATE NOT NULL,
            rid SERIAL,
            rast RASTER,
            PRIMARY KEY (date_id, rid)
        ) PARTITION BY RANGE (date_id)
    """)
    for y in years:
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS public.et_data_{y}
            PARTITION OF {TABLE}
            FOR VALUES FROM ('{y}-01-01') TO ('{y+1}-01-01')
        """)
    conn.commit()
    conn.close()

def fix_raster2pgsql_output(sql, date_id):
    match = re.search(r"'[0-9A-F]+'::raster", sql)
    if not match:
        return None
    raster_value = match.group(0)
    return (
        f"INSERT INTO {TABLE} (date_id, rast) "
        f"VALUES ('{date_id}', {raster_value});"
    )
def extract_date(filename):
    m = re.search(r"(\d{4})_(\d{2})_(\d{2})", filename)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return None


def build_tasks():
    tasks = []
    for tif_path in OUTPUT_DIR.glob("modis_et_*.tif"):
        info = parse_file_info(tif_path)
        if not info:
            print(f"⚠️  Skipping (no date): {tif_path.name}")
            continue
        year, date_id = info
        tasks.append((tif_path, year, date_id))
    return tasks


def modify_sql_for_dateid(sql_content, date_id):
    lines = sql_content.split('\n')
    modified_lines = []
    for line in lines:
        if 'VACUUM' in line or 'AddRasterConstraints' in line:
            continue  # Skip these lines
        if line.strip().startswith('INSERT INTO') and 'VALUES' in line:
            parts = line.split('VALUES')
            insert_part = parts[0]
            values_part = parts[1]
            # Handle both schema-qualified and unqualified table names
            insert_part = re.sub(
                r'INSERT INTO ("[^"]+"\.)?"et_data" \("rast"\)',
                'INSERT INTO "public"."et_data" ("date_id","rast")',
                insert_part
            )
            values_part = values_part.strip().rstrip(';')
            if values_part.startswith('('):
                values_part = f"('{date_id}'," + values_part[1:]
            modified_lines.append(f"{insert_part}VALUES {values_part};")
        elif line.strip().startswith('BEGIN') or line.strip().startswith('END'):
            continue
        else:
            modified_lines.append(line)
    return '\n'.join(modified_lines)

def process_task(task):
    tif_path, year, date_id = task
    cmd = [
        "raster2pgsql",
        "-a",  # append mode
        "-s", str(SRID),
        "-C",
        "-M",
        "-t", "100x100",
        str(tif_path),
        TABLE
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return "error", tif_path.name, result.stderr[:400]
        sql_content = result.stdout
        modified_sql = modify_sql_for_dateid(sql_content, date_id)
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASS
        )
        with conn.cursor() as cur:
            cur.execute(modified_sql)
            conn.commit()
        conn.close()
        return "success", tif_path.name, None
    except Exception as e:
        return "error", tif_path.name, str(e)[:400]


if __name__ == "__main__":
    tif_files = sorted(OUTPUT_DIR.glob("modis_et_*.tif"))
    if not tif_files:
        print(f"❌ No GeoTIFF files found in {OUTPUT_DIR}")
        exit(1)
    years = sorted({parse_file_info(f)[0] for f in tif_files if parse_file_info(f)})
    ensure_table_and_partitions(years)
    success = 0
    skipped = 0
    failed = 0
    failed_list = []
    tasks = build_tasks()
    total = len(tasks)
    print(f"Total upload tasks: {total}")
    with Pool(processes=NUM_WORKERS) as pool:
        for i, (status, name, msg) in enumerate(pool.imap_unordered(process_task, tasks), 1):
            if status == "success":
                success += 1
                print(f"[{i}/{total}] {name} ✓")
            elif status == "skipped":
                skipped += 1
                print(f"[{i}/{total}] {name} ⏭️")
            else:
                failed += 1
                print(f"[{i}/{total}] {name} ✗ {msg}")
                failed_list.append((name, msg))
    print(f"Completed: {success} success, {skipped} skipped, {failed} failed")

    # Verify database only (no raster constraints)
    try:
        conn = psycopg2.connect(
            host=DB_HOST, port=DB_PORT, database=DB_NAME, user=DB_USER, password=DB_PASS
        )
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(DISTINCT date_id) FROM public.et_data")
            date_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM public.et_data")
            total_rows = cur.fetchone()[0]
            cur.execute("SELECT MIN(date_id), MAX(date_id) FROM public.et_data")
            date_range = cur.fetchone()
        print(f"\nDatabase verification:")
        print(f"  Unique dates: {date_count}")
        print(f"  Total rows (tiles): {total_rows}")
        print(f"  Date range: {date_range[0]} to {date_range[1]}")
        print(f"  Note: Row count includes all raster tiles (100x100 tiling)")
    finally:
        conn.close()
