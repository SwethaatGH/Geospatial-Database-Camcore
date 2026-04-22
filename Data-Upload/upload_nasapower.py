"""
Upload NASA Power data to single table: np_data
Structure: date_id (date), var_name (text), rast (raster)
Monthly data - compatible with API expectations
47 variables, native 1 degree resolution
"""

import os
import subprocess
from pathlib import Path
import psycopg2
from multiprocessing import Pool

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'port': 5433,
    'database': 'covariables_indonesia',
    'user': 'postgres',
    'password': 'Camcore22'
}

# Paths
INPUT_DIR = Path(r"C:\Users\rcavalh\Documents\Camcore25\DB_Indonesia\Brazil_NASA_POWER_2025_Monthly")
RASTER2PGSQL = r"C:\Program Files\PostgreSQL\13\bin\raster2pgsql.exe"

# Parallel workers
NUM_WORKERS = 16

# Table name
TABLE_NAME = "np_data_2025"

def create_np_data_table(conn):
    """Create np_data table if it doesn't exist"""
    with conn.cursor() as cur:
        # Check if table exists
        cur.execute(f"""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = '{TABLE_NAME}'
            );
        """)
        exists = cur.fetchone()[0]

        # Safety: for partition targets, do not drop/recreate automatically
        if TABLE_NAME != "np_data":
            if not exists:
                raise RuntimeError(
                    f"Target table '{TABLE_NAME}' does not exist. "
                    "Create/attach the partition first, then run upload."
                )
            print(f"Using existing partition table: {TABLE_NAME}")
            return
        
        if exists:
            print(f"Table {TABLE_NAME} already exists - will append data")
            # DROP TABLE commented out - just append to existing table
            # response = input("Drop and recreate table? (yes/no): ").strip().lower()
            # if response == 'yes':
            #     print(f"Dropping table {TABLE_NAME}...")
            #     cur.execute(f"DROP TABLE {TABLE_NAME} CASCADE;")
            #     conn.commit()
            return
        
        print(f"Creating table {TABLE_NAME}...")
        
        # Create table with date_id and var_name (like WorldClim and SPEI)
        cur.execute(f"""
            CREATE TABLE {TABLE_NAME} (
                rid SERIAL PRIMARY KEY,
                date_id DATE NOT NULL,
                var_name TEXT NOT NULL,
                rast RASTER
            );
        """)
        
        # Create indexes
        cur.execute(f"""
            CREATE INDEX idx_{TABLE_NAME}_date_var ON {TABLE_NAME}(date_id, var_name);
            CREATE INDEX idx_{TABLE_NAME}_rast_gist ON {TABLE_NAME} USING GIST (ST_ConvexHull(rast));
        """)
        
        conn.commit()
        print(f"Table {TABLE_NAME} created successfully")


def parse_filename(filename):
    """
    Parse NASA Power filename to extract date and variable
    Example: allsky_nkt_2012_04.tif -> ('2012-04-01', 'allsky_nkt')
    """
    stem = filename.stem
    parts = stem.split('_')
    
    # Format: {var}_{year}_{month}.tif or {var}_{subvar}_{year}_{month}.tif
    # Need to find year (4 digits) and month (2 digits) at the end
    if len(parts) >= 3:
        year = parts[-2]   # Second to last part
        month = parts[-1]  # Last part
        var_name = '_'.join(parts[:-2])  # Everything before year and month
        
        # Construct date (first day of month)
        date_id = f"{year}-{month}-01"
        
        return date_id, var_name
    
    raise ValueError(f"Cannot parse filename: {filename.name}")


def get_all_files_by_variable(input_dir):
    """
    Group all files by variable
    Returns: dict of {var_name: [list of file paths]}
    """
    all_files = sorted(input_dir.glob("*/*.tif"))  # Files are in subdirectories
    
    files_by_var = {}
    for file_path in all_files:
        try:
            date_id, var_name = parse_filename(file_path)
            if var_name not in files_by_var:
                files_by_var[var_name] = []
            files_by_var[var_name].append(file_path)
        except ValueError as e:
            print(f"Warning: {e}")
            continue
    
    return files_by_var


def upload_file(file_path, conn):
    """
    Upload a single GeoTIFF file to PostgreSQL
    Modifies SQL to include date_id and var_name
    """
    try:
        # Parse filename
        date_id, var_name = parse_filename(file_path)
        
        # Run raster2pgsql to generate SQL
        result = subprocess.run(
            [
                RASTER2PGSQL,
                '-a',  # Append mode
                '-s', '4326',  # Set SRID to WGS84
                '-N', '-9999',  # Set nodata value
                '-t', '100x100',  # Tile size (small tiles for 1 degree data)
                str(file_path),
                'dummy_table'
            ],
            capture_output=True,
            text=True,
            check=True
        )
        
        sql_output = result.stdout
        
        # Modify SQL to include metadata
        modified_sql = []
        for line in sql_output.split('\n'):
            # Skip unwanted statements
            if any(skip in line for skip in ['BEGIN;', 'COMMIT;', 'CREATE TABLE', 'DROP TABLE', 'ANALYZE']):
                continue
            
            # Modify INSERT statements to include metadata
            if 'INSERT INTO' in line and 'dummy_table' in line:
                # Extract just the VALUES part
                values_start = line.find('VALUES')
                if values_start != -1:
                    values_part = line[values_start:]
                    # Add metadata values at the start
                    values_part = values_part.replace('VALUES (', f"VALUES ('{date_id}', '{var_name}', ")
                    # Rebuild complete INSERT statement
                    line = f"INSERT INTO {TABLE_NAME} (date_id, var_name, rast) {values_part}"
            
            modified_sql.append(line)
        
        # Execute modified SQL
        with conn.cursor() as cur:
            cur.execute('\n'.join(modified_sql))
        
        conn.commit()
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"\nError running raster2pgsql: {e.stderr}")
        conn.rollback()
        return False
    except Exception as e:
        print(f"\nError uploading {file_path.name}: {e}")
        conn.rollback()
        return False


def process_file_worker(file_path_str):
    """
    Parallel worker: uploads one file with its own DB connection.
    Returns (file_path, success, message)
    """
    file_path = Path(file_path_str)
    try:
        conn = psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        return file_path_str, False, f"DB connect error: {e}"

    try:
        success = upload_file(file_path, conn)
        if success:
            return file_path_str, True, "uploaded"
        return file_path_str, False, "upload failed"
    except Exception as e:
        return file_path_str, False, str(e)
    finally:
        conn.close()


def main():
    """Main upload process"""
    print(f"Input directory: {INPUT_DIR.resolve()}")
    print(f"Target table: {TABLE_NAME}")
    print(f"Parallel workers: {NUM_WORKERS}")
    
    # Get all files grouped by variable
    files_by_var = get_all_files_by_variable(INPUT_DIR)
    
    if not files_by_var:
        print(f"No NASA Power files found in {INPUT_DIR}")
        return
    
    total_files = sum(len(files) for files in files_by_var.values())
    print(f"Found {len(files_by_var)} variables, {total_files} total files")
    print(f"Variables: {', '.join(sorted(files_by_var.keys()))}")

    # Flat file list for parallel processing
    all_files = []
    for files in files_by_var.values():
        all_files.extend(files)
    all_files = sorted(all_files)
    
    # Connect to database
    conn = psycopg2.connect(**DB_CONFIG)
    
    try:
        # Create table
        create_np_data_table(conn)
        
        # Upload files in parallel
        success_count = 0
        error_count = 0

        print(f"\nStarting parallel upload with {NUM_WORKERS} workers...")
        with Pool(processes=NUM_WORKERS) as pool:
            results = pool.imap_unordered(process_file_worker, [str(path) for path in all_files])
            for index, (file_path_str, success, message) in enumerate(results, 1):
                file_name = Path(file_path_str).name
                if success:
                    success_count += 1
                    print(f"[{index}/{total_files}] ✓ {file_name}")
                else:
                    error_count += 1
                    print(f"[{index}/{total_files}] ✗ {file_name} - {message}")
        
        print(f"\n{'='*60}")
        print(f"Upload Summary:")
        print(f"  Total files: {total_files}")
        print(f"  Successful: {success_count}")
        print(f"  Errors: {error_count}")
        print(f"{'='*60}")
        
        # Verify upload
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT var_name, COUNT(*) as tiles, COUNT(DISTINCT date_id) as months
                FROM {TABLE_NAME}
                GROUP BY var_name
                ORDER BY var_name
            """)
            
            print(f"\nDatabase Summary for {TABLE_NAME}:")
            print(f"{'Variable':<30} {'Tiles':<10} {'Months':<10}")
            print('-' * 50)
            for row in cur.fetchall():
                print(f"{row[0]:<30} {row[1]:<10} {row[2]:<10}")
    
    finally:
        conn.close()


if __name__ == "__main__":
    main()
