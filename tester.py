import ee
import datetime
import calendar
import time

def test_gee_connection():
    print("Testing Google Earth Engine connection...")
    
    # Initialize Earth Engine
    try:
        ee.Initialize(project='ee-camcoredatabase')
        print("✅ Successfully initialized Earth Engine")
    except Exception as e:
        print(f"❌ Authentication error: {e}")
        try:
            ee.Authenticate()
            ee.Initialize(project='ee-camcoredatabase')
            print("✅ Successfully initialized Earth Engine after authentication")
        except Exception as auth_error:
            print(f"❌ Authentication failed: {auth_error}")
            return False
    
    return True

def test_chirps_data_export():
    print("Testing CHIRPS data export functionality...")
    
    # Calculate previous month as default
    today = datetime.datetime.now()
    prev_month = today.replace(day=1) - datetime.timedelta(days=1)
    year = prev_month.year
    month = prev_month.month
    
    # Calculate the first and last day of the specified month
    first_day = datetime.date(year, month, 1)
    last_day = datetime.date(year, month, calendar.monthrange(year, month)[1])
    
    # Format dates for GEE
    start_date = first_day.strftime('%Y-%m-%d')
    end_date = last_day.strftime('%Y-%m-%d')
    
    print(f"Testing with date range: {start_date} to {end_date}")
    
    # Define Brazil bounding box
    bbox = ee.Geometry.BBox(-94.187, -39.020, 37.062, 18.229)
    
    # Load CHIRPS Daily Precipitation dataset
    dataset = (
        ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
        .filterDate(start_date, end_date)
        .filterBounds(bbox)
    )
    
    # Select the 'precipitation' band
    precipitation = dataset.select('precipitation')
    
    # Get the size of the collection
    size = precipitation.size().getInfo()
    print(f"✅ Successfully fetched data: Found {size} images for the date range")
    
    # Try to export one image as a test
    if size > 0:
        print("Testing export functionality with the first image...")
        
        first_image = ee.Image(precipitation.first())
        date = ee.Date(first_image.get('system:time_start')).format('YYYY-MM-dd').getInfo()
        
        print(f"Exporting image for date: {date}")
        
        task = ee.batch.Export.image.toDrive(
            image=first_image.clip(bbox),
            description=f"Test_Precip_{date}",
            folder="CHIRPS_BBOX",
            scale=5000,
            region=bbox,
            maxPixels=1e13
        )
        
        task.start()
        print(f"✅ Successfully started export task with ID: {task.id}")
        
        # Check task status a few times
        print("Checking task status (will check 3 times):")
        for i in range(3):
            status = task.status()
            print(f"  Check {i+1}: Status = {status['state']}")
            time.sleep(5)
        
        print("Export task is now running in the background.")
        print("You can check its status in the Google Earth Engine Code Editor tasks tab.")
        
        return True
    else:
        print("❌ No images found for the specified date range")
        return False

if __name__ == "__main__":
    if test_gee_connection():
        test_chirps_data_export()
    else:
        print("Failed to establish connection to Google Earth Engine.")