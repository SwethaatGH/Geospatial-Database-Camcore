"""
Upload ERA5-Land daily multi-band files to PostgreSQL database.

This script processes daily ERA5 files where each file contains 15 bands (one per variable).
Each band is extracted and uploaded separately with its corresponding variable name.

Input: era5land_YYYY-MM-DD.tif files with 15 bands
Output: era5_data table with (rid, date_id, var_name, rast)
"""

import os
import subprocess
import psycopg2
from datetime import datetime
from pathlib import Path
import tempfile
import shutil
import rasterio

# Configuration
ERA5_FOLDER = r"Q:\My Drive\Indonesia_ERA5_Daily"
DB_CONFIG = {
    'host': 'localhost',
    'port': 5433,
    'database': 'covariables_indonesia',
    'user': 'postgres',
    'password': 'kenan1996'
}

RASTER2PGSQL_PATH = r"C:\Program Files\PostgreSQL\13\bin\raster2pgsql.exe"
PSQL_PATH = r"C:\Program Files\PostgreSQL\13\bin\psql.exe"

# Band order from GEE download script → database variable names
BAND_TO_VARNAME = {
    1: "temp",                # temperature_2m
    2: "sktemp",             # skin_temperature
    3: "sotemp1",            # soil_temperature_level_1
    4: "sotemp2",            # soil_temperature_level_2
    5: "sotemp3",            # soil_temperature_level_3
    6: "volsowat1",          # volumetric_soil_water_layer_1
    7: "volsowat2",          # volumetric_soil_water_layer_2
    8: "volsowat3",          # volumetric_soil_water_layer_3
    9: "uwind",              # u_component_of_wind_10m
    10: "vwind",             # v_component_of_wind_10m
    11: "press",             # surface_pressure
    12: "totprec",           # total_precipitation_sum
    13: "latheat",           # surface_latent_heat_flux_sum
    14: "netsolrad",         # surface_net_solar_radiation_sum
    15: "evaptrans"          # evaporation_from_vegetation_transpiration_sum
}

def parse_filename(filename):
    """Extract date from filename: era5land_YYYY-MM-DD.tif (original format)"""
    try:
        # Remove extension and prefix
        date_str = filename.replace("era5land_", "").replace(".tif", "")
        # Handle original dash format: YYYY-MM-DD
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        date_id = date_obj.strftime("%Y-%m-%d")
        return date_id
    except Exception as e:
        print(f"Error parsing filename {filename}: {e}")
        return None

def create_table_if_not_exists(conn):
    """Create era5_data table if it doesn't exist."""
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS era5_data (
        rid SERIAL PRIMARY KEY,
        date_id DATE NOT NULL,
        var_name TEXT NOT NULL,
        rast RASTER
    );
    
    CREATE INDEX IF NOT EXISTS era5_data_date_idx ON era5_data(date_id);
    CREATE INDEX IF NOT EXISTS era5_data_var_idx ON era5_data(var_name);
    CREATE INDEX IF NOT EXISTS era5_data_rast_idx ON era5_data USING GIST(ST_ConvexHull(rast));
    """
    with conn.cursor() as cur:
        cur.execute(create_table_sql)
        conn.commit()
    print("✓ Table era5_data ready")

def extract_band_to_temp_file(input_file, band_num, temp_dir):
    """Extract a single band from multi-band file using rasterio."""
    temp_file = os.path.join(temp_dir, f"band_{band_num}.tif")
    
    with rasterio.open(input_file) as src:
        # Read the specific band (bands are 1-indexed)
        band_data = src.read(band_num)
        
        # Copy metadata and update for single band
        profile = src.profile.copy()
        profile.update({
            'count': 1,
            'compress': 'lzw'
        })
        
        # Write single band to temp file
        with rasterio.open(temp_file, 'w', **profile) as dst:
            dst.write(band_data, 1)
    
    return temp_file

def process_file(filepath, conn):
    """Process one ERA5 daily file - extract all 15 bands and upload."""
    filename = os.path.basename(filepath)
    date_id = parse_filename(filename)
    
    if not date_id:
        print(f"✗ Skipping {filename} - cannot parse date")
        return False
    
    print(f"\n→ Processing {filename} ({date_id})")
    
    # Check if already uploaded
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(DISTINCT var_name) FROM era5_data WHERE date_id = %s",
            (date_id,)
        )
        existing_count = cur.fetchone()[0]
        
        if existing_count == 15:
            print(f"  ⊙ All 15 variables already uploaded")
            return True
        elif existing_count > 0:
            print(f"  ⚠ Found {existing_count}/15 variables, re-uploading all")
            cur.execute("DELETE FROM era5_data WHERE date_id = %s", (date_id,))
            conn.commit()
    
    # Create temporary directory for band extraction
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Process each band
            for band_num, var_name in BAND_TO_VARNAME.items():
                print(f"  [{band_num}/15] Uploading {var_name}...", end=" ", flush=True)
                
                # Extract band to temporary file
                temp_band_file = extract_band_to_temp_file(filepath, band_num, temp_dir)
                
                # Generate SQL using raster2pgsql
                temp_sql_file = os.path.join(temp_dir, f"band_{band_num}.sql")
                
                cmd = [
                    RASTER2PGSQL_PATH,
                    "-a",  # Append mode
                    "-t", "100x100",  # Tile size
                    "-C",  # Add raster constraints
                    temp_band_file,
                    "era5_data"
                ]
                
                with open(temp_sql_file, 'w') as f:
                    result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True)
                    if result.returncode != 0:
                        raise Exception(f"raster2pgsql failed: {result.stderr}")
                
                # Modify SQL to add date_id and var_name
                with open(temp_sql_file, 'r') as f:
                    sql_content = f.read()
                
                modified_sql = modify_sql_for_dateid_varname(sql_content, date_id, var_name)
                
                # Execute modified SQL
                with conn.cursor() as cur:
                    cur.execute(modified_sql)
                    conn.commit()
                
                print("✓")
            
            print(f"✓ Completed {filename} - all 15 variables uploaded")
            return True
            
        except Exception as e:
            print(f"\n✗ Error processing {filename}: {e}")
            conn.rollback()
            return False

def modify_sql_for_dateid_varname(sql_content, date_id, var_name):
    """Modify raster2pgsql SQL to include date_id and var_name."""
    lines = sql_content.split('\n')
    modified_lines = []
    
    for line in lines:
        if line.strip().startswith('INSERT INTO'):
            # Extract the VALUES clause
            if 'VALUES' in line:
                parts = line.split('VALUES')
                insert_part = parts[0]
                values_part = parts[1]
                
                # Modify INSERT clause to include date_id and var_name columns
                insert_part = insert_part.replace(
                    'INSERT INTO "era5_data" ("rast")',
                    'INSERT INTO "era5_data" ("date_id","var_name","rast")'
                )
                
                # Modify VALUES clause to include date_id and var_name
                values_part = values_part.replace(
                    '(',
                    f"('{date_id}','{var_name}',",
                    1
                )
                
                modified_lines.append(insert_part + 'VALUES' + values_part)
            else:
                modified_lines.append(line)
        elif line.strip().startswith('COPY') or 'FROM stdin' in line:
            # Skip COPY statements if any
            continue
        else:
            modified_lines.append(line)
    
    return '\n'.join(modified_lines)

def get_all_files():
    """Get all ERA5 daily files sorted by date."""
    files = [f for f in os.listdir(ERA5_FOLDER) if f.startswith("era5land_") and f.endswith(".tif")]
    files.sort()
    return [os.path.join(ERA5_FOLDER, f) for f in files]

def main():
    print("="*70)
    print("ERA5-Land Daily Data Upload to PostgreSQL")
    print("="*70)
    print(f"Source folder: {ERA5_FOLDER}")
    print(f"Database: {DB_CONFIG['database']}")
    print(f"Table: era5_data")
    print("="*70)
    
    # Get all files
    files = get_all_files()
    print(f"\nFound {len(files)} ERA5 daily files")
    
    if not files:
        print("No files found to process!")
        return
    
    # Connect to database
    conn = psycopg2.connect(**DB_CONFIG)
    
    try:
        # Create table
        create_table_if_not_exists(conn)
        
        # Process each file
        successful = 0
        failed = 0
        
        for idx, filepath in enumerate(files, 1):
            print(f"\n[{idx}/{len(files)}]", end=" ")
            if process_file(filepath, conn):
                successful += 1
            else:
                failed += 1
        
        # Summary
        print("\n" + "="*70)
        print("UPLOAD COMPLETE")
        print("="*70)
        print(f"Total files: {len(files)}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        print("="*70)
        
        # Verify database
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(DISTINCT date_id) FROM era5_data")
            date_count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(DISTINCT var_name) FROM era5_data")
            var_count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM era5_data")
            total_rows = cur.fetchone()[0]
            
            cur.execute("SELECT MIN(date_id), MAX(date_id) FROM era5_data")
            date_range = cur.fetchone()
        
        print(f"\nDatabase verification:")
        print(f"  Unique dates: {date_count}")
        print(f"  Unique variables: {var_count}")
        print(f"  Total rows: {total_rows}")
        print(f"  Date range: {date_range[0]} to {date_range[1]}")
        print(f"  Expected rows: {date_count * 15} (dates × 15 variables)")
        
    finally:
        conn.close()

if __name__ == "__main__":
    main()
