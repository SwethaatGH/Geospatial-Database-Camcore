from datetime import datetime, timedelta, date
import os
import calendar
from pathlib import Path
import pendulum
from airflow import DAG
from airflow.decorators import task
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.models import Variable

# Define default arguments
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

# Base directories - update these paths
BASE_DIR = "/usr/local/airflow/include/spei_data"
DOWNLOAD_DIR = os.path.join(BASE_DIR, "GEE_SPEI_BBOX")
RESAMPLED_DIR = os.path.join(BASE_DIR, "GEE_SPEI_BBOX_resampled")

# Ensure directories exist
Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)
Path(RESAMPLED_DIR).mkdir(parents=True, exist_ok=True)

# Database connection ID
POSTGRES_CONN_ID = 'postgres_default'

# Create the DAG
with DAG(
    'spei_monthly_etl',
    default_args=default_args,
    description='Monthly pipeline to download and process SPEI data from 3 months prior',
    # Run on the 1st day of each month at midnight
    schedule='0 0 1 * *',
    # Start yesterday to ensure it runs today for past data
    start_date=pendulum.yesterday(),
    catchup=False,
    tags=['spei', 'drought', 'gee'],
) as dag:
    
    @task()
    def extract_spei_data(execution_date=None):
        """
        Download SPEI data for three months prior to the execution date
        On April 1st, it downloads January data
        On May 1st, it downloads February data, etc.
        """
        import ee
        import time
        import os
        
        # If running manually (execution_date is None), use current date
        if execution_date is None:
            execution_date = pendulum.now()
        
        # Get the date 3 months ago from execution date
        target_date = execution_date.subtract(months=3)
        year = target_date.year
        month = target_date.month
        
        print(f"TASK STARTING - Downloading SPEI data for {year}-{month:02d}")
        
        # Calculate dates
        first_day = date(year, month, 1)
        last_day = date(year, month, calendar.monthrange(year, month)[1])
        
        # Format dates for GEE
        start_date = first_day.strftime('%Y-%m-%d')
        end_date = last_day.strftime('%Y-%m-%d')
        
        print(f"Target date range: {start_date} to {end_date}")
        
        # Earth Engine authentication with error handling
        try:
            print("Attempting to initialize Earth Engine...")
            # Try to initialize without authenticating first
            ee.Initialize(project='ee-camcoredatabase')
            print("Earth Engine initialized successfully")
        except Exception as e:
            print(f"Initial EE authentication error: {str(e)}")
            try:
                print("Attempting authentication...")
                ee.Authenticate()
                ee.Initialize(project='ee-camcoredatabase')
                print("Authentication successful")
            except Exception as auth_error:
                print(f"Authentication failed: {str(auth_error)}")
                return {"status": "failed", "error": "Authentication failed"}
        
        # Define bounding box
        bbox = ee.Geometry.BBox(-94.187, -39.020, 37.062, 18.229)
        
        # Load the SPEI dataset
        print("Loading SPEI dataset...")
        dataset = (
            ee.ImageCollection("CSIC/SPEI/2_10")
            .filterDate(start_date, end_date)
            .filterBounds(bbox)
        )
        
        # Select the 1-month SPEI
        spei01 = dataset.select('SPEI_01_month')
        
        # Print dataset size for debugging
        size = spei01.size().getInfo()
        print(f"Dataset size: {size} images")
        
        if size == 0:
            print("No images found in the dataset. Check date range and bounding box.")
            return {"status": "no_data", "message": "No images found in the dataset"}
        
        # Direct download approach
        results = []
        
        # Create directory if it doesn't exist
        if not os.path.exists(DOWNLOAD_DIR):
            os.makedirs(DOWNLOAD_DIR)
        
        def download_image(image, index):
            try:
                date = ee.Date(image.get('system:time_start')).format('YYYY-MM')
                date_str = date.getInfo()
                print(f"Downloading image for: {date_str}")
                
                # Get download URL
                url = image.clip(bbox).getDownloadURL({
                    'name': f"SPEI01_{date_str}",
                    'scale': 5000,
                    'region': bbox,
                    'format': 'GeoTIFF'
                })
                
                # Download the file directly
                import requests
                response = requests.get(url)
                
                if response.status_code == 200:
                    # Save to the download directory
                    output_path = os.path.join(DOWNLOAD_DIR, f"SPEI01_{date_str}.tif")
                    with open(output_path, 'wb') as f:
                        f.write(response.content)
                    
                    print(f"Downloaded file to {output_path}")
                    
                    results.append({
                        'date': date_str,
                        'status': 'downloaded',
                        'path': output_path
                    })
                    return True
                else:
                    print(f"Failed to download: {response.status_code} - {response.text}")
                    return False
            
            except Exception as e:
                print(f"Error downloading image: {e}")
                import traceback
                print(traceback.format_exc())
                return False
        
        # Download images
        print("Starting downloads...")
        try:
            spei_list = spei01.toList(spei01.size())
            list_size = spei_list.size().getInfo()
            print(f"Processing {list_size} images")
            
            for i in range(list_size):
                print(f"Processing image {i+1} of {list_size}")
                image = ee.Image(spei_list.get(i))
                success = download_image(image, i)
                if not success:
                    print(f"Failed to download image {i+1}")
        
        except Exception as e:
            print(f"Error in download process: {e}")
            import traceback
            print(traceback.format_exc())
            return {
                'status': 'error',
                'error': str(e)
            }
        
        print("Download process completed")
        print(f"Results: {results}")
        
        return {
            'start_date': start_date,
            'end_date': end_date,
            'status': 'success',
            'results': results,
            'year': year,
            'month': month
        }
    
    @task()
    def transform_spei_data(extraction_result):
        """Transform the extracted SPEI data"""
        import subprocess
        import glob
        import os
        
        if not extraction_result:
            print("No extraction results to process")
            return None
        
        print("Extraction result:", extraction_result)
        
        # Get list of downloaded files
        tif_files = glob.glob(os.path.join(DOWNLOAD_DIR, "*.tif"))
        print(f"Found {len(tif_files)} .tif files in download directory")
        
        if not tif_files:
            print("No .tif files found in download directory.")
            return None
        
        # Ensure output directory exists
        os.makedirs(RESAMPLED_DIR, exist_ok=True)
        
        # Process the downloaded files
        processed_files = []
        for filename in tif_files:
            base_filename = os.path.basename(filename)
            # Extract date from filename (assuming pattern SPEI01_YYYY-MM.tif)
            parts = base_filename.split('_')
            if len(parts) > 1:
                date_part = parts[1].split('.')[0]  # Extract date part before .tif
                year = date_part.split('-')[0]
                month = date_part.split('-')[1]
                new_filename = f"spei_{year}_{month}.tif"
            else:
                # Fallback if filename doesn't match expected format
                new_filename = f"spei_{base_filename}"
            
            output_path = os.path.join(RESAMPLED_DIR, new_filename)
            
            # Skip if already processed
            if os.path.exists(output_path):
                print(f"Skipping {new_filename}, already exists.")
                continue
                
            print(f"Processing: {base_filename} -> {new_filename}")
            
            # Use GDAL to resample
            cmd = [
                "gdalwarp", 
                "-tr", "0.02", "0.02", 
                "-r", "bilinear", 
                "-co", "COMPRESS=LZW", 
                "-co", "TILED=YES",
                "-ot", "Float32", 
                "-dstnodata", "-9999.0", 
                filename, 
                output_path
            ]
            
            try:
                result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                print(f"Resampled: {new_filename}")
                processed_files.append(new_filename)
            except subprocess.CalledProcessError as e:
                print(f"Error processing {filename}: {e}")
                print(f"STDERR: {e.stderr}")
        
        return {
            'period': extraction_result.get('start_date', '') + " to " + extraction_result.get('end_date', ''),
            'processed_files': processed_files,
            'year': extraction_result.get('year'),
            'month': extraction_result.get('month')
        }
     
    @task()
    def load_spei_data(transformation_result):
        """Load transformed data into PostgreSQL using time partitioning"""
        if not transformation_result:
            return "No data to load"
            
        pg_hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
        conn_details = pg_hook.get_connection(POSTGRES_CONN_ID)
        print(f"Using connection: {conn_details.host}:{conn_details.port}/{conn_details.schema} (user: {conn_details.login})")
        
        # Get year and month from the transformation result
        year = transformation_result.get('year')
        month = transformation_result.get('month')
        
        # Ensure the parent partitioned table exists
        conn = pg_hook.get_conn()
        cursor = conn.cursor()
        
        try:
            # Create the parent table if it doesn't exist
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS spei_data (
                rid SERIAL,
                date_id DATE NOT NULL,
                rast RASTER,
                PRIMARY KEY (date_id, rid)
            ) PARTITION BY RANGE (date_id);
            """)
            
            # Check if yearly partition exists and create if needed
            cursor.execute(f"""
            SELECT EXISTS (
                SELECT FROM pg_tables 
                WHERE tablename = 'spei_data_{year}'
                AND schemaname = 'public'
            );
            """)
            
            partition_exists = cursor.fetchone()[0]
            
            if not partition_exists:
                # Create the yearly partition
                cursor.execute(f"""
                CREATE TABLE spei_data_{year} PARTITION OF spei_data
                FOR VALUES FROM ('{year}-01-01') TO ('{year+1}-01-01');
                """)
                print(f"Created partition for year {year}")
            
            conn.commit()
        except Exception as e:
            print(f"Error setting up partitioned table: {e}")
            conn.rollback()
        finally:
            cursor.close()
            conn.close()
        
        loaded_files = []
        
        for filename in transformation_result['processed_files']:
            # Extract date from filename (assuming pattern spei_YYYY_MM.tif)
            parts = filename.replace('.tif', '').split('_')
            if len(parts) >= 3:
                year_part = parts[1]
                month_part = parts[2]
                # For SPEI, use first day of month as the date
                date_str = f"{year_part}-{month_part}-01"
            else:
                print(f"Skipping {filename}: cannot parse date from filename")
                continue
            
            file_path = os.path.join(RESAMPLED_DIR, filename)
            
            print(f"Uploading {filename} for date {date_str}...")
            
            # Use raster2pgsql through shell command
            import subprocess
            import tempfile
            import re
            
            try:
                # Create SQL file
                sql_file = tempfile.NamedTemporaryFile(delete=False, suffix='.sql')
                sql_file.close()
                
                # Generate SQL without -C (VACUUM command)
                cmd = f"raster2pgsql -s 4326 -I -M -t 128x128 {file_path} _temp_rast > {sql_file.name}"
                subprocess.run(cmd, shell=True, check=True)
                
                # Read the SQL file and remove any VACUUM commands
                with open(sql_file.name, 'r') as f:
                    sql_content = f.read()
                
                # Remove any VACUUM commands and modify SQL to insert into partitioned table
                sql_content = re.sub(r'VACUUM.*?;', '', sql_content)
                
                # Replace table creation with temp table
                sql_content = sql_content.replace('CREATE TABLE "_temp_rast"', 'CREATE TEMP TABLE "_temp_rast"')
                
                # Add insert statement to copy data to the partitioned table
                # Add insert statement to copy data to the partitioned table
                sql_content += f"""
                INSERT INTO spei_data (date_id, rast)
                SELECT '{date_str}'::date, rast FROM _temp_rast;
                DROP TABLE _temp_rast;
                """
                
                # Write modified SQL back to file
                with open(sql_file.name, 'w') as f:
                    f.write(sql_content)
                
                # Execute SQL file
                conn = pg_hook.get_conn()
                cursor = conn.cursor()
                
                with open(sql_file.name, 'r') as f:
                    sql = f.read()
                    cursor.execute(sql)
                
                conn.commit()
                cursor.close()
                conn.close()
                
                # Clean up
                os.unlink(sql_file.name)
                
                loaded_files.append(filename)
                print(f"Successfully loaded {filename} into partitioned table for date {date_str}")
                
            except Exception as e:
                print(f"Error loading {filename}: {e}")
                import traceback
                print(traceback.format_exc())
        
        return {
            'period': transformation_result['period'],
            'loaded_files': loaded_files,
            'year': year,
            'month': month
        }
    
    # Define the workflow
    spei_data = extract_spei_data()
    transformed_data = transform_spei_data(spei_data)
    load_result = load_spei_data(transformed_data)
    
    # Run an extra DAG instance now to process January 2025 data (since April 26th has passed)
    if pendulum.now().day > 1 and pendulum.now().month == 4:
        # Create a special task for January data
        @task(task_id="extract_january_data")
        def extract_january_data():
            # Pass January 2025 as the data to process
            jan_date = pendulum.datetime(2025, 1, 15)
            return extract_spei_data(jan_date)
            
        # Execute special January processing
        jan_data = extract_january_data()
        jan_transformed = transform_spei_data(jan_data)
        jan_loaded = load_spei_data(jan_transformed)