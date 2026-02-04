"""
Upload CHIRPS resampled rasters to PostgreSQL using Python.
Alternative to raster2pgsql when PostGIS raster tools aren't available.
"""

import os
import subprocess
from pathlib import Path

# Configuration
DATA_DIR = r"C:\Poorna\Camcore-db\Geospatial-Database-Camcore\Data-Processing\Indonesia_CHIRPS_Resampled"  # UPDATE THIS TO YOUR ACTUAL PATH!
DB_USER = "postgres"
DB_PASS = "postgres"
DB_HOST = "localhost"
DB_PORT = "5433"
DB_NAME = "covariables_indonesia"

def upload_raster(tif_file, table_name, is_first):
    """Upload a single raster file to the chirps_data table."""
    
    # Extract date_id from filename (e.g., chirps_1990_01_01.tif -> 1990-01-01)
    filename = tif_file.stem  # e.g., chirps_1990_01_01
    parts = filename.split('_')
    if len(parts) >= 4:
        date_id = f"{parts[1]}-{parts[2]}-{parts[3]}"  # Format: YYYY-MM-DD
    else:
        date_id = filename  # Fallback
    
    # Build raster2pgsql command
    # First file creates table (-c), subsequent files append (-a)
    mode = "-c" if is_first else "-a"
    
    cmd = [
        "raster2pgsql",
        mode,              # Create or append
        "-s", "4326",      # SRID
        "-t", "128x128",   # Tile size
        "-F",              # Add filename column (for date tracking)
        str(tif_file),
        f"public.{table_name}"
    ]
    
    # Add index and constraints only for first file
    if is_first:
        cmd.insert(2, "-I")  # Create spatial index
        cmd.insert(3, "-C")  # Apply constraints
    
    # Pipe to psql
    psql_cmd = [
        "psql",
        "-U", DB_USER,
        "-d", DB_NAME,
        "-h", DB_HOST,
        "-p", DB_PORT,
        "-q"  # Quiet mode
    ]
    
    try:
        # Set password environment variable
        env = os.environ.copy()
        env["PGPASSWORD"] = DB_PASS
        
        # Run raster2pgsql and pipe to psql
        raster_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )
        
        psql_process = subprocess.Popen(
            psql_cmd,
            stdin=raster_process.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )
        
        # Wait for completion
        raster_process.stdout.close()
        stdout, stderr = psql_process.communicate()
        
        if psql_process.returncode == 0:
            # After successful upload, update filename to date_id format
            if not is_first:  # Skip for first as we'll do it after all uploads
                return True, None
            return True, None
        else:
            return False, stderr.decode()
            
    except Exception as e:
        return False, str(e)

def main():
    data_path = Path(DATA_DIR)
    
    if not data_path.exists():
        print(f"Error: Directory not found: {DATA_DIR}")
        return
    
    # Get all TIFF files
    tif_files = sorted(data_path.glob("*.tif"))
    
    if not tif_files:
        print(f"No .tif files found in {DATA_DIR}")
        return
    
    print("=" * 70)
    print("CHIRPS Raster Upload to PostgreSQL")
    print("=" * 70)
    print(f"Data directory: {DATA_DIR}")
    print(f"Database:       {DB_NAME}")
    print(f"Total files:    {len(tif_files)}")
    print("=" * 70)
    print()
    
    success_count = 0
    fail_count = 0
    table_name = "chirps_data"  # Single table for all CHIRPS data
    
    for i, tif_file in enumerate(tif_files, 1):
        is_first = (i == 1)
        
        print(f"[{i}/{len(tif_files)}] Uploading: {tif_file.name} → {table_name}...", end=" ")
        
        success, error = upload_raster(tif_file, table_name, is_first)
        
        if success:
            print("✓")
            success_count += 1
        else:
            print(f"✗")
            print(f"    Error: {error}")
            fail_count += 1
    
    print()
    print("=" * 70)
    print("UPLOAD COMPLETE")
    print("=" * 70)
    print(f"Successful: {success_count}/{len(tif_files)}")
    print(f"Failed:     {fail_count}/{len(tif_files)}")
    print("=" * 70)
    
    # Add date_id column and populate from filename
    if success_count > 0:
        print("\nAdding date_id column...")
        try:
            env = os.environ.copy()
            env["PGPASSWORD"] = DB_PASS
            
            # Add date_id column
            add_col_cmd = [
                "psql", "-U", DB_USER, "-d", DB_NAME, "-h", DB_HOST, "-p", DB_PORT,
                "-c", "ALTER TABLE chirps_data ADD COLUMN IF NOT EXISTS date_id DATE;"
            ]
            subprocess.run(add_col_cmd, env=env, check=True)
            
            # Update date_id from filename (chirps_1990_01_01.tif -> 1990-01-01)
            update_cmd = [
                "psql", "-U", DB_USER, "-d", DB_NAME, "-h", DB_HOST, "-p", DB_PORT,
                "-c", """UPDATE chirps_data SET date_id = TO_DATE(
                    SUBSTRING(filename FROM '_(\\d{4})_(\\d{2})_(\\d{2})\\.'), 
                    'YYYY_MM_DD'
                ) WHERE date_id IS NULL;"""
            ]
            subprocess.run(update_cmd, env=env, check=True)
            
            print("✓ date_id column added and populated")
        except Exception as e:
            print(f"✗ Error adding date_id: {e}")

if __name__ == "__main__":
    main()
