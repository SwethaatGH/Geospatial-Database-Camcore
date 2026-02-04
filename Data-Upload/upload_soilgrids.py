"""
Upload SoilGrids data to single table: soil_data
Structure: var_name (text), rast (raster)
Static data - no date_id
Compatible with API expectations
"""

import os
import subprocess
from pathlib import Path
from tqdm import tqdm
import psycopg2

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'port': 5433,
    'database': 'covariables_indonesia',
    'user': 'postgres',
    'password': 'Camcore22'
}

# Paths
INPUT_DIR = Path(r"Q:\My Drive\Indonesia_SoilGrids")
RASTER2PGSQL = r"C:\Program Files\PostgreSQL\13\bin\raster2pgsql.exe"

# Table name
TABLE_NAME = "soil_data"

def create_soil_data_table(conn):
    """Create soil_data table if it doesn't exist"""
    with conn.cursor() as cur:
        # Check if table exists
        cur.execute(f"""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = '{TABLE_NAME}'
            );
        """)
        exists = cur.fetchone()[0]
        
        if exists:
            print(f"Table {TABLE_NAME} already exists")
            return
        
        print(f"Creating table {TABLE_NAME}...")
        
        # Create table with raster column (NO date_id - static data)
        cur.execute(f"""
            CREATE TABLE {TABLE_NAME} (
                rid SERIAL PRIMARY KEY,
                var_name TEXT NOT NULL,
                rast RASTER
            );
        """)
        
        # Create indexes
        cur.execute(f"""
            CREATE INDEX idx_{TABLE_NAME}_var ON {TABLE_NAME}(var_name);
            CREATE INDEX idx_{TABLE_NAME}_rast_gist ON {TABLE_NAME} USING GIST (ST_ConvexHull(rast));
        """)
        
        conn.commit()
        print(f"Table {TABLE_NAME} created successfully")


def parse_filename(filename):
    """
    Parse SoilGrids filename to extract variable name
    Example: bdod_0-5cm_mean.tif -> 'bdod'
    Example: ocs_0-30cm_mean.tif -> 'ocs'
    """
    stem = filename.stem
    parts = stem.split('_')
    
    if len(parts) >= 1:
        var_name = parts[0]  # First part is always the variable
        return var_name
    
    return None


def upload_file(file_path, var_name, conn):
    """Upload a single raster file directly to soil_data table"""
    
    # Use raster2pgsql to generate INSERT statements
    raster2pgsql_cmd = [
        RASTER2PGSQL,
        '-s', '4326',
        '-t', '128x128',
        str(file_path),
        'dummy_table'  # Placeholder, we'll replace in SQL
    ]
    
    try:
        # Run raster2pgsql to generate SQL
        result = subprocess.run(
            raster2pgsql_cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        # Parse SQL output and modify INSERT statements
        sql_lines = result.stdout.split('\n')
        modified_sql = []
        
        for line in sql_lines:
            # Skip table creation statements
            if line.strip().startswith(('CREATE TABLE', 'DROP TABLE', 'ALTER TABLE', 
                                       'CREATE INDEX', 'ANALYZE', 'SELECT AddRaster', 'BEGIN', 'END')):
                continue
            
            # Modify INSERT statements to include metadata
            if 'INSERT INTO' in line and 'dummy_table' in line:
                # Extract just the VALUES part
                values_start = line.find('VALUES')
                if values_start != -1:
                    values_part = line[values_start:]
                    # Add metadata values at the start (only var_name, no date_id)
                    values_part = values_part.replace('VALUES (', f"VALUES ('{var_name}', ")
                    # Rebuild complete INSERT statement
                    line = f"INSERT INTO {TABLE_NAME} (var_name, rast) {values_part}"
            
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


def main():
    """Main upload process"""
    
    # Find all .tif files
    all_files = sorted(INPUT_DIR.glob("*.tif"))
    
    if not all_files:
        print(f"No SoilGrids files found in {INPUT_DIR}")
        return
    
    print(f"Found {len(all_files)} SoilGrids files")
    print(f"Target table: {TABLE_NAME}")
    print(f"Database: {DB_CONFIG['database']}")
    print(f"{'='*60}\n")
    
    # Connect to database
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        print("Connected to database")
    except Exception as e:
        print(f"Failed to connect to database: {e}")
        return
    
    try:
        # Create table if needed
        create_soil_data_table(conn)
        
        # Process each file
        uploaded = 0
        skipped = 0
        
        for file_path in tqdm(all_files, desc="Uploading SoilGrids"):
            # Parse filename
            var_name = parse_filename(file_path)
            
            if not var_name:
                print(f"\n⚠️  Skipping unrecognized file: {file_path.name}")
                skipped += 1
                continue
            
            # Upload
            if upload_file(file_path, var_name, conn):
                uploaded += 1
            else:
                skipped += 1
        
        print(f"\n{'='*60}")
        print(f"Upload complete!")
        print(f"  Uploaded: {uploaded} files")
        print(f"  Skipped: {skipped} files")
        print(f"{'='*60}")
        
        # Show summary
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT 
                    var_name,
                    COUNT(*) as tile_count
                FROM {TABLE_NAME}
                GROUP BY var_name
                ORDER BY var_name;
            """)
            
            print(f"\n{TABLE_NAME} summary:")
            print(f"{'Variable':<15} {'Tiles'}")
            print("-" * 30)
            for row in cur.fetchall():
                print(f"{row[0]:<15} {row[1]}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
