  
# from datetime import datetime, timedelta, date
# import os
# import calendar
# from pathlib import Path
# import pendulum
# from airflow import DAG
# from airflow.decorators import task
# from airflow.providers.postgres.hooks.postgres import PostgresHook
# from airflow.models import Variable
# # Define default arguments
# default_args = {
#     'owner': 'airflow',
#     'depends_on_past': False,
#     'email_on_failure': False,
#     'email_on_retry': False,
#     'retries': 1,
#     'retry_delay': timedelta(minutes=5),
# }
# # Base directories - update these paths
# BASE_DIR = "/usr/local/airflow/include/chirps_data"
# DOWNLOAD_DIR = os.path.join(BASE_DIR, "CHIRPS_BBOX")
# RESAMPLED_DIR = os.path.join(BASE_DIR, "CHIRPS_BBOX_resampled")
# # Ensure directories exist
# Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)
# Path(RESAMPLED_DIR).mkdir(parents=True, exist_ok=True)
# # Database connection ID
# POSTGRES_CONN_ID = 'postgres_default'
# # Create the DAG
# with DAG(
#     'chirps_monthly_etl',
#     default_args=default_args,
#     description='Monthly pipeline to download and process CHIRPS data',
#     schedule='@monthly',  # Updated from schedule_interval to schedule
#     # Replace days_ago with pendulum datetime
#     start_date=pendulum.yesterday(),
#     catchup=False,
#     tags=['chirps', 'precipitation', 'gee'],
# ) as dag:
    

#     @task()
#     def extract_chirps_data():
#         """Download CHIRPS data for January 2025 (3 months ago)"""
#         import ee
#         import time
#         import os
#         from google.cloud import storage
        
#         # Set target for January 2025 (3 months ago)
#         year = 2025
#         month = 1
        
#         print(f"TASK STARTING - Downloading CHIRPS data for {year}-{month}")
        
#         # Calculate dates
#         first_day = date(year, month, 1)
#         last_day = date(year, month, calendar.monthrange(year, month)[1])
        
#         # Format dates for GEE
#         start_date = first_day.strftime('%Y-%m-%d')
#         end_date = last_day.strftime('%Y-%m-%d')
        
#         print(f"Target date range: {start_date} to {end_date}")
        
#         # Earth Engine authentication with better error handling
#         try:
#             print("Attempting to initialize Earth Engine...")
#             # Try to initialize without authenticating first
#             ee.Initialize()
#             print("Earth Engine initialized successfully")
#         except Exception as e:
#             print(f"Initial EE authentication error: {str(e)}")
#             try:
#                 print("Attempting interactive notebook authentication...")
#                 # Use notebook mode which doesn't require gcloud
#                 ee.Authenticate(auth_mode='notebook')
#                 ee.Initialize()
#                 print("Notebook authentication successful")
#             except Exception as notebook_error:
#                 print(f"Notebook authentication failed: {str(notebook_error)}")
#                 try:
#                     print("Attempting localhost authentication...")
#                     # Try localhost mode as a fallback
#                     ee.Authenticate(auth_mode='localhost')
#                     ee.Initialize()
#                     print("Localhost authentication successful")
#                 except Exception as localhost_error:
#                     print(f"All authentication attempts failed:")
#                     print(f"  - Initial error: {str(e)}")
#                     print(f"  - Notebook error: {str(notebook_error)}")
#                     print(f"  - Localhost error: {str(localhost_error)}")
#                     return {"status": "failed", "error": "Authentication failed"}
        
#         # Define Brazil bounding box
#         bbox = ee.Geometry.BBox(-94.187, -39.020, 37.062, 18.229)
        
#         # Load CHIRPS Daily Precipitation dataset
#         print("Loading CHIRPS dataset...")
#         dataset = (
#             ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
#             .filterDate(start_date, end_date)
#             .filterBounds(bbox)
#         )
        
#         # Print dataset size for debugging
#         size = dataset.size().getInfo()
#         print(f"Dataset size: {size} images")
        
#         if size == 0:
#             print("No images found in the dataset. Check date range and bounding box.")
#             return {"status": "no_data", "message": "No images found in the dataset"}
        
#         # Select the 'precipitation' band
#         precipitation = dataset.select('precipitation')
        
#         # Direct download approach instead of Google Drive
#         results = []
        
#         # Create directory if it doesn't exist
#         if not os.path.exists(DOWNLOAD_DIR):
#             os.makedirs(DOWNLOAD_DIR)
        
#         def download_image(image, index):
#             try:
#                 date = ee.Date(image.get('system:time_start')).format('YYYY-MM-dd')
#                 date_str = date.getInfo()
#                 print(f"Downloading image for: {date_str}")
                
#                 # Get download URL
#                 url = image.clip(bbox).getDownloadURL({
#                     'name': f"Precip_{date_str}",
#                     'scale': 5000,
#                     'region': bbox,
#                     'format': 'GeoTIFF'
#                 })
                
#                 # Download the file directly
#                 import requests
#                 response = requests.get(url)
                
#                 if response.status_code == 200:
#                     # Save to the download directory
#                     output_path = os.path.join(DOWNLOAD_DIR, f"Precip_{date_str}.tif")
#                     with open(output_path, 'wb') as f:
#                         f.write(response.content)
                    
#                     print(f"Downloaded file to {output_path}")
                    
#                     results.append({
#                         'date': date_str,
#                         'status': 'downloaded',
#                         'path': output_path
#                     })
#                     return True
#                 else:
#                     print(f"Failed to download: {response.status_code} - {response.text}")
#                     return False
            
#             except Exception as e:
#                 print(f"Error downloading image: {e}")
#                 import traceback
#                 print(traceback.format_exc())
#                 return False
        
#         # Download a limited number of images (e.g., first 3 days) for testing
#         print("Starting downloads...")
#         try:
#             precip_list = precipitation.toList(precipitation.size())
#             list_size = precip_list.size().getInfo()
#             print(f"Processing {list_size} images")
            
#             # Limit to 3 images for testing
#             limit = min(3, list_size)
#             for i in range(limit):
#                 print(f"Processing image {i+1} of {limit}")
#                 image = ee.Image(precip_list.get(i))
#                 success = download_image(image, i)
#                 if not success:
#                     print(f"Failed to download image {i+1}")
        
#         except Exception as e:
#             print(f"Error in download process: {e}")
#             import traceback
#             print(traceback.format_exc())
#             return {
#                 'status': 'error',
#                 'error': str(e)
#             }
        
#         print("Download process completed")
#         print(f"Results: {results}")
        
#         return {
#             'start_date': start_date,
#             'end_date': end_date,
#             'status': 'success',
#             'results': results
#         }
        
    

#     @task()
#     def transform_chirps_data(extraction_result):
#         """Transform the extracted CHIRPS data"""
#         import subprocess
#         import glob
#         import os
        
#         if not extraction_result:
#             print("No extraction results to process")
#             return None
        
#         print("Extraction result:", extraction_result)
        
#         # Get list of downloaded files
#         tif_files = glob.glob(os.path.join(DOWNLOAD_DIR, "*.tif"))
#         print(f"Found {len(tif_files)} .tif files in download directory")
        
#         if not tif_files:
#             print("No .tif files found in download directory.")
#             return None
        
#         # Ensure output directory exists
#         os.makedirs(RESAMPLED_DIR, exist_ok=True)
        
#         # Process the downloaded files
#         processed_files = []
#         for filename in tif_files:
#             base_filename = os.path.basename(filename)
#             # Extract date from filename (assuming pattern Precip_YYYY-MM-DD.tif)
#             parts = base_filename.split('_')
#             if len(parts) > 1:
#                 date_part = parts[1].split('.')[0]  # Extract date part before .tif
#                 new_filename = f"chirps_{date_part.replace('-', '_')}.tif"
#             else:
#                 # Fallback if filename doesn't match expected format
#                 new_filename = f"chirps_{base_filename}"
            
#             output_path = os.path.join(RESAMPLED_DIR, new_filename)
            
#             # Skip if already processed
#             if os.path.exists(output_path):
#                 print(f"Skipping {new_filename}, already exists.")
#                 continue
                
#             print(f"Processing: {base_filename} -> {new_filename}")
            
#             # Use GDAL to resample - safer to use list of arguments instead of shell=True
#             cmd = [
#                 "gdalwarp", 
#                 "-tr", "0.02", "0.02", 
#                 "-r", "bilinear", 
#                 "-co", "COMPRESS=LZW", 
#                 "-co", "TILED=YES",
#                 "-ot", "Float32", 
#                 "-dstnodata", "-9999.0", 
#                 filename, 
#                 output_path
#             ]
            
#             try:
#                 # Use shell=False (default) for better security and argument handling
#                 result = subprocess.run(cmd, check=True, capture_output=True, text=True)
#                 print(f"Resampled: {new_filename}")
#                 processed_files.append(new_filename)
#             except subprocess.CalledProcessError as e:
#                 print(f"Error processing {filename}: {e}")
#                 print(f"STDERR: {e.stderr}")
        
#         return {
#             'period': extraction_result.get('start_date', '') + " to " + extraction_result.get('end_date', ''),
#             'processed_files': processed_files
#         }
 
#     #     """Load transformed data into PostgreSQL"""
#     #     if not transformation_result:
#     #         return "No data to load"
            
#     #     pg_hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
#     #     conn = pg_hook.get_conn()
#     #     cursor = conn.cursor()
        
#     #     loaded_tables = []
        
#     #     for filename in transformation_result['processed_files']:
#     #         table_name = filename.replace('.tif', '')
#     #         file_path = os.path.join(RESAMPLED_DIR, filename)
            
#     #         print(f"Uploading {table_name}...")
            
#     #         # Use raster2pgsql through shell command
#     #         import subprocess
#     #         import tempfile
            
#     #         # Create SQL file
#     #         sql_file = tempfile.NamedTemporaryFile(delete=False, suffix='.sql')
#     #         sql_file.close()
            
#     #         cmd = f"raster2pgsql -s 4326 -I -C -M -t 128x128 {file_path} public.{table_name} > {sql_file.name}"
#     #         subprocess.run(cmd, shell=True, check=True)
            
#     #         # Execute SQL file
#     #         with open(sql_file.name, 'r') as f:
#     #             sql = f.read()
#     #             cursor.execute(sql)
            
#     #         # Clean up
#     #         os.unlink(sql_file.name)
            
#     #         loaded_tables.append(table_name)
        
#     #     conn.commit()
#     #     cursor.close()
        
#     #     return {
#     #         'period': transformation_result['period'],
#     #         'loaded_tables': loaded_tables
#     #     }
#     @task()
#     def load_chirps_data(transformation_result):
#         """Load transformed data into PostgreSQL"""
#         if not transformation_result:
#             return "No data to load"
            
#         pg_hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
#         conn_details = pg_hook.get_connection(POSTGRES_CONN_ID)
#         print(f"Using connection: {conn_details.host}:{conn_details.port}/{conn_details.schema} (user: {conn_details.login})")
        
#         loaded_tables = []
        
#         for filename in transformation_result['processed_files']:
#             table_name = filename.replace('.tif', '')
#             file_path = os.path.join(RESAMPLED_DIR, filename)
            
#             print(f"Uploading {table_name}...")
            
#             # Check if table exists first
#             conn = pg_hook.get_conn()
#             cursor = conn.cursor()
#             cursor.execute(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{table_name}');")
#             table_exists = cursor.fetchone()[0]
#             cursor.close()
#             conn.close()
            
#             if table_exists:
#                 print(f"Table {table_name} already exists. Dropping it before recreating...")
#                 conn = pg_hook.get_conn()
#                 cursor = conn.cursor()
#                 cursor.execute(f"DROP TABLE IF EXISTS {table_name};")
#                 conn.commit()
#                 cursor.close()
#                 conn.close()
            
#             # Use raster2pgsql through shell command
#             import subprocess
#             import tempfile
#             import re
            
#             # Create SQL file
#             sql_file = tempfile.NamedTemporaryFile(delete=False, suffix='.sql')
#             sql_file.close()
            
#             # Generate SQL without VACUUM command
#             cmd = f"raster2pgsql -s 4326 -I -M -t 128x128 {file_path} public.{table_name} > {sql_file.name}"
#             subprocess.run(cmd, shell=True, check=True)
            
#             # Read the SQL file and remove any VACUUM commands
#             with open(sql_file.name, 'r') as f:
#                 sql_content = f.read()
            
#             # Remove any VACUUM commands using regex
#             sql_content = re.sub(r'VACUUM.*?;', '', sql_content)
            
#             # Write cleaned SQL back to file
#             with open(sql_file.name, 'w') as f:
#                 f.write(sql_content)
            
#             # Execute SQL file
#             conn = pg_hook.get_conn()
#             cursor = conn.cursor()
#             with open(sql_file.name, 'r') as f:
#                 sql = f.read()
#                 cursor.execute(sql)
            
#             conn.commit()
#             cursor.close()
#             conn.close()
            
#             # Clean up
#             os.unlink(sql_file.name)
            
#             loaded_tables.append(table_name)
        
#         return {
#             'period': transformation_result['period'],
#             'loaded_tables': loaded_tables
#         }
#     # Define the workflow
#     chirps_data = extract_chirps_data()
#     transformed_data = transform_chirps_data(chirps_data)
#     load_result = load_chirps_data(transformed_data)



# WITH TIME PARTITIONING


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
BASE_DIR = "/usr/local/airflow/include/chirps_data"
DOWNLOAD_DIR = os.path.join(BASE_DIR, "CHIRPS_BBOX")
RESAMPLED_DIR = os.path.join(BASE_DIR, "CHIRPS_BBOX_resampled")

# Ensure directories exist
Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)
Path(RESAMPLED_DIR).mkdir(parents=True, exist_ok=True)

# Database connection ID
POSTGRES_CONN_ID = 'postgres_default'

# Create the DAG
with DAG(
    'chirps_monthly_etl',
    default_args=default_args,
    description='Monthly pipeline to download and process CHIRPS data from 3 months prior',
    # Run on the 1st day of each month at midnight
    schedule='0 0 1 * *',
    # Start yesterday to ensure it runs today for past data
    start_date=pendulum.yesterday(),
    catchup=False,
    tags=['chirps', 'precipitation', 'gee'],
) as dag:
    
    @task()
    def extract_chirps_data(execution_date=None):
        """
        Download CHIRPS data for three months prior to the execution date
        On April 1st, it downloads January data
        On May 1st, it downloads February data, etc.
        """
        import ee
        import time
        import os
        from google.cloud import storage
        
        # If running manually (execution_date is None), use current date
        if execution_date is None:
            execution_date = pendulum.now()
        
        # Get the date 3 months ago from execution date
        target_date = execution_date.subtract(months=3)
        year = target_date.year
        month = target_date.month
        
        print(f"TASK STARTING - Downloading CHIRPS data for {year}-{month:02d}")
        
        # Calculate dates
        first_day = date(year, month, 1)
        last_day = date(year, month, calendar.monthrange(year, month)[1])
        
        # Format dates for GEE
        start_date = first_day.strftime('%Y-%m-%d')
        end_date = last_day.strftime('%Y-%m-%d')
        
        print(f"Target date range: {start_date} to {end_date}")
        
        # Earth Engine authentication with better error handling
        try:
            print("Attempting to initialize Earth Engine...")
            # Try to initialize without authenticating first
            ee.Initialize()
            print("Earth Engine initialized successfully")
        except Exception as e:
            print(f"Initial EE authentication error: {str(e)}")
            try:
                print("Attempting interactive notebook authentication...")
                # Use notebook mode which doesn't require gcloud
                ee.Authenticate(auth_mode='notebook')
                ee.Initialize()
                print("Notebook authentication successful")
            except Exception as notebook_error:
                print(f"Notebook authentication failed: {str(notebook_error)}")
                try:
                    print("Attempting localhost authentication...")
                    # Try localhost mode as a fallback
                    ee.Authenticate(auth_mode='localhost')
                    ee.Initialize()
                    print("Localhost authentication successful")
                except Exception as localhost_error:
                    print(f"All authentication attempts failed:")
                    print(f"  - Initial error: {str(e)}")
                    print(f"  - Notebook error: {str(notebook_error)}")
                    print(f"  - Localhost error: {str(localhost_error)}")
                    return {"status": "failed", "error": "Authentication failed"}
        
        # Define Brazil bounding box
        bbox = ee.Geometry.BBox(-94.187, -39.020, 37.062, 18.229)
        
        # Load CHIRPS Daily Precipitation dataset
        print("Loading CHIRPS dataset...")
        dataset = (
            ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
            .filterDate(start_date, end_date)
            .filterBounds(bbox)
        )
        
        # Print dataset size for debugging
        size = dataset.size().getInfo()
        print(f"Dataset size: {size} images")
        
        if size == 0:
            print("No images found in the dataset. Check date range and bounding box.")
            return {"status": "no_data", "message": "No images found in the dataset"}
        
        # Select the 'precipitation' band
        precipitation = dataset.select('precipitation')
        
        # Direct download approach instead of Google Drive
        results = []
        
        # Create directory if it doesn't exist
        if not os.path.exists(DOWNLOAD_DIR):
            os.makedirs(DOWNLOAD_DIR)
        
        def download_image(image, index):
            try:
                date = ee.Date(image.get('system:time_start')).format('YYYY-MM-dd')
                date_str = date.getInfo()
                print(f"Downloading image for: {date_str}")
                
                # Get download URL
                url = image.clip(bbox).getDownloadURL({
                    'name': f"Precip_{date_str}",
                    'scale': 5000,
                    'region': bbox,
                    'format': 'GeoTIFF'
                })
                
                # Download the file directly
                import requests
                response = requests.get(url)
                
                if response.status_code == 200:
                    # Save to the download directory
                    output_path = os.path.join(DOWNLOAD_DIR, f"Precip_{date_str}.tif")
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
        
        print("Starting downloads...")
        try:
            precip_list = precipitation.toList(precipitation.size())
            list_size = precip_list.size().getInfo()
            print(f"Processing {list_size} images")
            
            # Download all images for the month
            for i in range(list_size):
                print(f"Processing image {i+1} of {list_size}")
                image = ee.Image(precip_list.get(i))
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
    def transform_chirps_data(extraction_result):
        """Transform the extracted CHIRPS data"""
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
            # Extract date from filename (assuming pattern Precip_YYYY-MM-DD.tif)
            parts = base_filename.split('_')
            if len(parts) > 1:
                date_part = parts[1].split('.')[0]  # Extract date part before .tif
                new_filename = f"chirps_{date_part.replace('-', '_')}.tif"
            else:
                # Fallback if filename doesn't match expected format
                new_filename = f"chirps_{base_filename}"
            
            output_path = os.path.join(RESAMPLED_DIR, new_filename)
            
            # Skip if already processed
            if os.path.exists(output_path):
                print(f"Skipping {new_filename}, already exists.")
                continue
                
            print(f"Processing: {base_filename} -> {new_filename}")
            
            # Use GDAL to resample - safer to use list of arguments instead of shell=True
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
                # Use shell=False (default) for better security and argument handling
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
    def load_chirps_data(transformation_result):
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
            CREATE TABLE IF NOT EXISTS chirps_data (
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
                WHERE tablename = 'chirps_data_{year}'
                AND schemaname = 'public'
            );
            """)
            
            partition_exists = cursor.fetchone()[0]
            
            if not partition_exists:
                # Create the yearly partition
                cursor.execute(f"""
                CREATE TABLE chirps_data_{year} PARTITION OF chirps_data
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
            # Extract date from filename (assuming pattern chirps_YYYY_MM_DD.tif)
            parts = filename.replace('.tif', '').split('_')
            if len(parts) >= 4:
                year_part = parts[1]
                month_part = parts[2]
                day_part = parts[3]
                date_str = f"{year_part}-{month_part}-{day_part}"
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
                sql_content += f"""
                INSERT INTO chirps_data (date_id, rast)
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
    chirps_data = extract_chirps_data()
    transformed_data = transform_chirps_data(chirps_data)
    load_result = load_chirps_data(transformed_data)
    
    # Run an extra DAG instance now to process January 2025 data (since April 26th has passed)
    if pendulum.now().day > 1 and pendulum.now().month == 4:
        # Create a special task for January data
        @task(task_id="extract_january_data")
        def extract_january_data():
            # Pass January 2025 as the data to process
            jan_date = pendulum.datetime(2025, 1, 15)
            return extract_chirps_data(jan_date)
            
        # Execute special January processing
        jan_data = extract_january_data()
        jan_transformed = transform_chirps_data(jan_data)
        jan_loaded = load_chirps_data(jan_transformed)