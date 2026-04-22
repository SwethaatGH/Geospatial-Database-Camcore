"""
Upload CHIRPS 2025/2026 daily files to covariables_indonesia.chirps_data table.

Input: resampled daily files (chirps_YYYY_MM_DD.tif) at 0.02° resolution
Table structure: (rid SERIAL, date_id DATE, rast RASTER) — partitioned by year
Each file = multiple tiles with NoData=-9999

Expected: ~730 files (2025 + 2026) across two yearly partitions
"""

import os
import subprocess
from pathlib import Path
from datetime import datetime
import psycopg2
from multiprocessing import Pool
from tqdm import tqdm

# Configuration
INPUT_DIR = r"Z:\ENVIROMICS\chirps\Indonesia_CHIRPS_Resampled"
DB_HOST = "localhost"
DB_PORT = "5433"
DB_NAME = "covariables_indonesia"
DB_USER = "postgres"
DB_PASSWORD = "postgres"
TABLE_NAME = "chirps_data"
NUM_WORKERS = 16
RASTER2PGSQL = r"C:\Program Files\PostgreSQL\13\bin\raster2pgsql.exe"


def ensure_partitions(years):
    """Create yearly partitions if they don't exist."""
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, database=DB_NAME,
        user=DB_USER, password=DB_PASSWORD
    )
    cur = conn.cursor()
    for y in years:
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME}_{y}
            PARTITION OF {TABLE_NAME}
            FOR VALUES FROM ('{y}-01-01') TO ('{y+1}-01-01')
        """)
        print(f"  Partition {TABLE_NAME}_{y} ready.")
    conn.commit()
    conn.close()


def check_if_uploaded(date_id):
    """Check if this date already exists in database."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE date_id = %s",
            (date_id,)
        )
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return count > 0
    except Exception as e:
        print(f"Error checking database: {e}")
        return False


def upload_chirps_file(file_path):
    """Upload a single CHIRPS daily file."""
    
    filename = os.path.basename(file_path)
    
    # Extract date from filename: chirps_2025_01_01.tif -> 2025-01-01
    try:
        parts = filename.replace('chirps_', '').replace('.tif', '').split('_')
        date_id = f"{parts[0]}-{parts[1]}-{parts[2]}"
    except Exception as e:
        return (filename, "error", f"Cannot parse date: {str(e)}")
    
    # Check if already uploaded
    if check_if_uploaded(date_id):
        return (filename, "skip", "Already exists")
    
    try:
        # Use raster2pgsql to convert to SQL
        cmd = [
            RASTER2PGSQL,
            "-a",  # Append mode
            "-s", "4326",  # SRID
            "-t", "100x100",  # Tile size - will generate multiple tiles
            "-N", "-9999",   # NoData value
            file_path,
            TABLE_NAME
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        sql = result.stdout
        
        # Extract ALL raster hex values directly (handles multi-tile output correctly)
        import re
        
        raster_values = re.findall(r"'[0-9A-F]+'::raster", sql)
        
        if not raster_values:
            return (filename, "error", "Cannot parse raster2pgsql output")
        
        # Build INSERT statements for all tiles with date_id
        final_sqls = []
        for raster_value in raster_values:
            sql_insert = f'INSERT INTO "{TABLE_NAME}" ("date_id", "rast") VALUES (\'{date_id}\', {raster_value});'
            final_sqls.append(sql_insert)
        
        # Execute all INSERT statements
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cursor = conn.cursor()
        for sql_stmt in final_sqls:
            cursor.execute(sql_stmt)
        conn.commit()
        cursor.close()
        conn.close()
        
        return (filename, "success", f"Uploaded ({len(final_sqls)} tiles)")
        
    except Exception as e:
        return (filename, "error", str(e))


def main():
    print("=" * 70)
    print("CHIRPS 2025 Upload to covariablesv1.chirps_data")
    print("=" * 70)
    print(f"Input directory: {INPUT_DIR}")
    print(f"Database: {DB_NAME}")
    print(f"Table: {TABLE_NAME}")
    print(f"Workers: {NUM_WORKERS}")
    print("=" * 70)
    
    # Get all CHIRPS 2025 + 2026 files
    files = sorted(Path(INPUT_DIR).glob("chirps_202*.tif"))

    if not files:
        print(f"\nERROR: No CHIRPS 2025/2026 files found in {INPUT_DIR}")
        return

    years = sorted({int(f.name.split('_')[1]) for f in files})
    print(f"Years detected: {years}")
    ensure_partitions(years)
    
    print(f"\nFound {len(files)} files to process")
    print(f"Expected records: {len(files)} (one per day)")
    print("\nStarting upload...\n")
    
    total_success = 0
    total_skipped = 0
    total_errors = 0
    
    with Pool(processes=NUM_WORKERS) as pool:
        results = pool.imap_unordered(upload_chirps_file, files)
        
        for filename, status, message in tqdm(results, total=len(files), desc="Uploading", unit="file"):
            if status == "success":
                total_success += 1
            elif status == "skip":
                total_skipped += 1
            else:
                total_errors += 1
                tqdm.write(f"  ✗ {filename}: {message}")
    
    print("\n" + "=" * 70)
    print("UPLOAD COMPLETE")
    print("=" * 70)
    print(f"Successful: {total_success}")
    print(f"Skipped:    {total_skipped}")
    print(f"Errors:     {total_errors}")
    print("=" * 70)


if __name__ == "__main__":
    main()
