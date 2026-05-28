"""
CHIRPS Upload to PostGIS with Parallel Processing

Upload daily CHIRPS files to database with multi-core support.
Auto-detects CPU cores and handles parallel uploads efficiently.

Usage:
  # Auto-detect cores
    python chirps_upload.py \
    --input-dir "C:\data\CHIRPS_2025_Final" \
    --host localhost \
    --port 5433 \
    --database covariables \
    --table chirps_data \
    --workers auto

  # Manual worker count
    python chirps_upload.py \
    --input-dir "C:\data\CHIRPS_2025_Final" \
    --host localhost \
    --database covariables \
    --workers 8

Dependencies:
  - psycopg2-binary
  - raster2pgsql (from PostGIS installation)
  - tqdm
  - numpy
"""

import sys
import subprocess
import argparse
import logging
import multiprocessing as mp
from pathlib import Path
from multiprocessing import Pool
import psycopg2
import os
import tempfile
import re

# ===== GDAL / PROJ / PostGIS CONFIGURATION =====
GDAL_BIN = r"C:\Program Files\QGIS 3.40.4\bin"
POSTGRES_BIN = r"C:\Program Files\PostgreSQL\13\bin"
RASTER2PGSQL = os.path.join(POSTGRES_BIN, "raster2pgsql.exe")
PROJ_LIB = r"C:\Program Files\QGIS 3.40.4\share\proj"

def ensure_env():
    """Set PROJ_LIB for GDAL/PROJ."""
    os.environ["PROJ_LIB"] = PROJ_LIB

# Configure logging
import io
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('chirps_upload.log', encoding='utf-8'),
        logging.StreamHandler(stream=io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace'))
    ]
)
logger = logging.getLogger(__name__)


class CHIRPSUploader:
    """Upload CHIRPS files to PostGIS database with parallel support."""
    
    def __init__(self, input_dir, host='localhost', port=5433, database='covariables',
                 user='postgres', password='postgres', table='chirps_data',
                 workers=None, batch_size=50, srid=4326, tile_size='128x128',
                 nodata='-9999', schema='public'):
        """
        Initialize uploader.
        
        Parameters:
        -----------
        input_dir : str
            Directory with daily CHIRPS files
        host : str
            Database host (default: localhost)
        port : int
            Database port (default: 5433)
        database : str
            Database name
        user : str
            Database user
        password : str
            Database password
        table : str
            Target table name
        workers : int or 'auto'
            Number of parallel workers ('auto' for CPU count - 1)
        batch_size : int
            Files per batch
        srid : int
            Spatial reference ID (default: 4326)
        tile_size : str
            Raster tile size for tiling (e.g., '100x100')
        """
        self.input_dir = Path(input_dir)
        self.host = host
        self.port = str(port)
        self.database = database
        self.user = user
        self.password = password
        self.table = table
        self.srid = srid
        self.tile_size = tile_size
        self.nodata = str(nodata)
        self.schema = schema
        
        # Auto-detect workers
        if workers == 'auto' or workers == 'AUTO':
            cpu_count = mp.cpu_count()
            self.workers = max(1, cpu_count - 1)  # Use all cores except 1
        else:
            self.workers = int(workers) if workers else 1
        
        self.batch_size = batch_size
        
        # Use hardcoded raster2pgsql path
        self.raster2pgsql = RASTER2PGSQL
        if not Path(self.raster2pgsql).exists():
            logger.error(f"raster2pgsql not found at: {self.raster2pgsql}")
            logger.error(f"Please ensure PostgreSQL 13 is installed in: {POSTGRES_BIN}")
            sys.exit(1)
        
        # Validate input directory
        if not self.input_dir.exists():
            logger.error(f"Input directory not found: {self.input_dir}")
            sys.exit(1)
        
        # Test database connection
        if not self._test_connection():
            logger.error("Cannot connect to database")
            sys.exit(1)
        
        # Create table if needed
        self._create_table_if_needed()
        
        logger.info(f"Initialized uploader")
        logger.info(f"  Input: {self.input_dir}")
        logger.info(f"  Database: {database}@{host}:{port}")
        logger.info(f"  Table: {table}")
        logger.info(f"  Workers: {self.workers} (CPU auto-detect)")
        logger.info(f"  NoData: {self.nodata}")
        logger.info(f"  Schema: {self.schema}")
    
    def _test_connection(self):
        """Test database connection."""
        try:
            conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )
            conn.close()
            logger.info("[OK] Database connection successful")
            return True
        except Exception as e:
            logger.error(f"[FAIL] Database connection failed: {e}")
            return False
    
    def _create_table_if_needed(self):
        """Create table if it doesn't exist and handle year partitions."""
        try:
            conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )
            cursor = conn.cursor()
            
            # Check if main table exists
            cursor.execute(f"""
                SELECT EXISTS(
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = %s
                )
            """, (self.table,))
            
            exists = cursor.fetchone()[0]
            
            if not exists:
                logger.info(f"Creating main table {self.table}...")
                cursor.execute(f"""
                    CREATE TABLE {self.table} (
                        rid SERIAL PRIMARY KEY,
                        date_id DATE NOT NULL,
                        rast RASTER NOT NULL
                    )
                """)
                
                # Create indexes on main table
                cursor.execute(f"""
                    CREATE INDEX idx_{self.table}_rast_gist 
                    ON {self.table} USING gist (st_convexhull(rast))
                """)
                
                cursor.execute(f"""
                    CREATE INDEX idx_{self.table}_date 
                    ON {self.table} (date_id)
                """)
                
                conn.commit()
                logger.info(f"[OK] Table {self.table} created with indexes")
            else:
                logger.info(f"[OK] Table {self.table} already exists")
            
            # Check for 2025 partition
            partition_table = f"{self.table}_2025"
            cursor.execute(f"""
                SELECT EXISTS(
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = %s
                )
            """, (partition_table,))
            
            partition_exists = cursor.fetchone()[0]
            
            if not partition_exists:
                logger.info(f"Creating partition {partition_table} for year 2025...")
                try:
                    cursor.execute(f"""
                        CREATE TABLE {partition_table} (
                            LIKE {self.table} INCLUDING ALL
                        ) INHERITS ({self.table})
                    """)
                    
                    # Create constraint for this partition
                    cursor.execute(f"""
                        ALTER TABLE {partition_table} 
                        ADD CONSTRAINT check_year_2025 
                        CHECK (EXTRACT(YEAR FROM date_id) = 2025)
                    """)
                    
                    # Create indexes on partition
                    cursor.execute(f"""
                        CREATE INDEX idx_{partition_table}_rast_gist 
                        ON {partition_table} USING gist (st_convexhull(rast))
                    """)
                    
                    cursor.execute(f"""
                        CREATE INDEX idx_{partition_table}_date 
                        ON {partition_table} (date_id)
                    """)
                    
                    conn.commit()
                    logger.info(f"[OK] Partition {partition_table} created with indexes and constraint")
                except Exception as pe:
                    logger.warning(f"[WARN] Could not create partition: {pe}")
                    logger.warning(f"[WARN] Data will be uploaded to main table {self.table}")
            else:
                logger.info(f"[OK] Partition {partition_table} already exists")
            
            cursor.close()
            conn.close()
        except Exception as e:
            logger.error(f"Error creating table/partition: {e}")
    
    def find_files(self):
        """Find all CHIRPS daily files."""
        files = sorted(self.input_dir.glob("chirps_*.tif"))
        
        if not files:
            logger.error(f"No CHIRPS files found in {self.input_dir}")
            return []
        
        logger.info(f"Found {len(files)} CHIRPS files")
        return files
    
    def check_if_uploaded(self, date_id):
        """Check if date already in database."""
        try:
            conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT COUNT(*) FROM {self.table} WHERE date_id = %s",
                (date_id,)
            )
            count = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            return count > 0
        except Exception:
            return False
    
    def upload_file(self, file_path):
        """
        Upload a single CHIRPS file.
        
        Returns:
        --------
        tuple : (filename, status, message)
        """
        filename = file_path.name
        
        # Parse date from filename: chirps_2025_01_01.tif
        try:
            parts = filename.replace('chirps_', '').replace('.tif', '').split('_')
            year = parts[0]
            date_id = f"{parts[0]}-{parts[1]}-{parts[2]}"
        except Exception as e:
            return (filename, "error", f"Cannot parse date: {str(e)}")
        
        # Check if already uploaded
        if self.check_if_uploaded(date_id):
            return (filename, "skip", "Already exists")
        
        # Determine target table (use partition if it exists, otherwise main table)
        partition_table = f"{self.table}_{year}"
        target_table = self.table  # Default to main table
        
        # Check if partition exists
        try:
            conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = %s)",
                (partition_table,)
            )
            if cursor.fetchone()[0]:
                target_table = partition_table
            cursor.close()
            conn.close()
        except Exception:
            pass  # Fall back to main table
        
        try:
            # Generate SQL using raster2pgsql to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.sql', delete=False) as temp_sql:
                temp_sql_path = temp_sql.name
            
            try:
                cmd = [
                    self.raster2pgsql,
                    '-a',  # Append mode
                    '-s', str(self.srid),  # SRID
                    '-t', self.tile_size,  # Tile size
                    '-N', self.nodata,  # NoData
                    str(file_path),
                    target_table
                ]
                
                with open(temp_sql_path, 'w') as f:
                    result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True, timeout=300)
                
                if result.returncode != 0:
                    return (filename, "error", f"raster2pgsql failed: {result.stderr[:100]}")
                
                # Read SQL from temp file
                with open(temp_sql_path, 'r') as f:
                    sql = f.read()
            finally:
                # Clean up temp file
                if os.path.exists(temp_sql_path):
                    os.remove(temp_sql_path)
            
            # Convert raster2pgsql output into one INSERT per tile with date_id
            sql_statements = self._inject_date_into_sql(sql, date_id, target_table)
            
            if not sql_statements:
                return (filename, "error", "Failed to build tile insert SQL")
            
            # Execute all tile INSERT statements for this file
            conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )
            cursor = conn.cursor()
            
            try:
                insert_count = 0
                for statement in sql_statements:
                    cursor.execute(statement)
                    insert_count += 1
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"SQL error in {filename}: {str(e)[:100]}")
                return (filename, "error", f"Insert failed: {str(e)[:80]}")
            finally:
                cursor.close()
                conn.close()
            
            return (filename, "success", f"Uploaded ({insert_count} tiles)")
        
        except subprocess.TimeoutExpired:
            return (filename, "error", "raster2pgsql timeout")
        except Exception as e:
            return (filename, "error", str(e)[:100])
    
    @staticmethod
    def _inject_date_into_sql(sql, date_id, target_table):
        """
        Build tile INSERT statements with date_id from raster2pgsql output.
        """
        try:
            statements = []
            raster_pattern = r"'[0-9A-F]+'::raster"

            for line in sql.splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                upper = stripped.upper()
                if upper.startswith('BEGIN') or upper.startswith('END'):
                    continue
                if not upper.startswith('INSERT INTO'):
                    continue

                raster_match = re.search(raster_pattern, stripped)
                if not raster_match:
                    continue

                raster_value = raster_match.group(0)
                statements.append(
                    f'INSERT INTO "{target_table}" ("date_id", "rast") VALUES (\'{date_id}\', {raster_value});'
                )

            return statements
        
        except Exception as e:
            logger.error(f"Error injecting date: {e}")
            return None

    def add_raster_constraints(self):
        """Add raster constraints after upload (same as tested uploader flow)."""
        try:
            conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )
            cursor = conn.cursor()
            cursor.execute(
                "SELECT AddRasterConstraints(%s::name, %s::name, 'rast'::name);",
                (self.schema, self.table)
            )
            conn.commit()
            cursor.close()
            conn.close()
            logger.info("[OK] Raster constraints added")
            return True
        except Exception as exc:
            logger.warning(f"[WARN] Could not add raster constraints: {exc}")
            return False
    
    def run(self):
        """Execute the uploader."""
        logger.info("=" * 60)
        logger.info("CHIRPS Upload to PostGIS")
        logger.info("=" * 60)
        
        files = self.find_files()
        if not files:
            logger.error("No files to upload")
            return False
        
        total_files = len(files)
        success_count = 0
        skip_count = 0
        error_count = 0

        effective_workers = min(self.workers, total_files)
        logger.info(f"Uploading {total_files} files with {effective_workers} workers...")

        if effective_workers <= 1:
            results = map(self.upload_file, files)
            for filename, status, message in results:
                if status == "success":
                    success_count += 1
                    logger.info(f"  [OK] {filename}: {message}")
                elif status == "skip":
                    skip_count += 1
                    logger.info(f"  [-] {filename}: {message}")
                else:
                    error_count += 1
                    logger.warning(f"  [FAIL] {filename}: {message}")
        else:
            chunksize = max(1, total_files // (effective_workers * 4))
            with Pool(processes=effective_workers) as pool:
                results = pool.imap(self.upload_file, files, chunksize=chunksize)
                for filename, status, message in results:
                    if status == "success":
                        success_count += 1
                        logger.info(f"  [OK] {filename}: {message}")
                    elif status == "skip":
                        skip_count += 1
                        logger.info(f"  [-] {filename}: {message}")
                    else:
                        error_count += 1
                        logger.warning(f"  [FAIL] {filename}: {message}")
        
        logger.info("=" * 60)
        logger.info(f"Upload complete:")
        logger.info(f"  [OK] Success:  {success_count}")
        logger.info(f"  [-] Skipped: {skip_count}")
        logger.info(f"  [FAIL] Errors:  {error_count}")
        logger.info("=" * 60)

        if error_count == 0:
            self.add_raster_constraints()
        
        return error_count == 0


def main():
    """Command-line interface."""
    ensure_env()  # Set PROJ_LIB before initializing GDAL/PostGIS
    
    parser = argparse.ArgumentParser(
        description='Upload CHIRPS files to PostGIS with parallel processing'
    )
    
    parser.add_argument(
        '--input-dir',
        required=True,
        help='Directory with daily CHIRPS files'
    )
    parser.add_argument(
        '--host',
        default='localhost',
        help='Database host (default: localhost)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=5433,
        help='Database port (default: 5433)'
    )
    parser.add_argument(
        '--database',
        required=True,
        help='Database name'
    )
    parser.add_argument(
        '--user',
        default='postgres',
        help='Database user (default: postgres)'
    )
    parser.add_argument(
        '--password',
        default='postgres',
        help='Database password (default: postgres)'
    )
    parser.add_argument(
        '--table',
        default='chirps_data',
        help='Target table name (default: chirps_data)'
    )
    parser.add_argument(
        '--workers',
        default='auto',
        help='Number of parallel workers (default: auto = CPU count - 1)'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=50,
        help='Deprecated. Kept for backward compatibility.'
    )
    parser.add_argument(
        '--srid',
        type=int,
        default=4326,
        help='Spatial reference ID (default: 4326)'
    )
    parser.add_argument(
        '--tile-size',
        default='128x128',
        help='Raster tile size (default: 128x128)'
    )
    parser.add_argument(
        '--nodata',
        default='-9999',
        help='NoData value passed to raster2pgsql (default: -9999)'
    )
    parser.add_argument(
        '--schema',
        default='public',
        help='Database schema for AddRasterConstraints (default: public)'
    )
    
    args = parser.parse_args()
    
    uploader = CHIRPSUploader(
        input_dir=args.input_dir,
        host=args.host,
        port=args.port,
        database=args.database,
        user=args.user,
        password=args.password,
        table=args.table,
        workers=args.workers,
        batch_size=args.batch_size,
        srid=args.srid,
        tile_size=args.tile_size,
        nodata=args.nodata,
        schema=args.schema,
    )
    
    success = uploader.run()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
