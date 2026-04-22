"""
SPEI Download for Indonesia
Downloads monthly SPEI (Standardized Precipitation-Evapotranspiration Index)
Exports yearly stacks to avoid clipping errors
"""

import ee

# Authenticate and initialize
ee.Authenticate()
ee.Initialize(project='ee-camcoredatabase')

# Indonesia bounding box
INDONESIA_BBOX = {
    'lat_min': -10.3599874813,
    'lat_max': 5.47982086834,
    'lon_min': 95.2930261576,
    'lon_max': 141.03385176
}

# Create GEE geometry for filtering (not clipping)
bbox = ee.Geometry.BBox(
    INDONESIA_BBOX['lon_min'],
    INDONESIA_BBOX['lat_min'],
    INDONESIA_BBOX['lon_max'],
    INDONESIA_BBOX['lat_max']
)

# SPEI dataset
collection = (
    ee.ImageCollection("CSIC/SPEI/2_10")
    .select('SPEI_01_month')  # 1-month SPEI
    .filterBounds(bbox)  # Filter to reduce data, but don't clip yet
)

# Export parameters
YEARS = list(range(1990, 2025))  # 1990-2024
OUTPUT_FOLDER = "Indonesia_SPEI_Years"
SCALE = 5566  # SPEI native resolution (0.05 degrees ≈ 5.5km)

print(f"Exporting SPEI data for Indonesia: {YEARS[0]}-{YEARS[-1]}")
print(f"Output folder: {OUTPUT_FOLDER}")
print(f"Bounding box: {INDONESIA_BBOX}")
print(f"{'='*60}\n")

for year in YEARS:
    print(f"Processing year: {year}")
    
    # Define date range
    start = ee.Date.fromYMD(year, 1, 1)
    end = start.advance(1, 'year')
    
    # Filter collection by year
    year_coll = collection.filterDate(start, end)
    
    # Check if collection has images
    count = year_coll.size().getInfo()
    print(f"  Found {count} monthly images")
    
    if count == 0:
        print(f"  ⚠️  No data for {year}, skipping")
        continue
    
    # Stack all bands (one per month)
    year_img = year_coll.toBands()
    
    # Get the actual geometry that covers Indonesia tiles
    # This exports the full SPEI tiles without clipping
    export_region = year_img.geometry().bounds()
    
    # Export task
    task = ee.batch.Export.image.toDrive(
        image=year_img,
        description=f"SPEI_Indonesia_{year}",
        folder=OUTPUT_FOLDER,
        fileNamePrefix=f"SPEI_Indonesia_{year}",
        scale=SCALE,
        region=export_region,  # Export full tiles
        crs='EPSG:4326',  # Ensure WGS84
        maxPixels=1e13,
        fileFormat='GeoTIFF'
    )
    
    task.start()
    print(f"  ✓ Export task started: SPEI_Indonesia_{year}")
    print(f"    Task ID: {task.id}\n")

print(f"{'='*60}")
print(f"All {len(YEARS)} export tasks submitted!")
print(f"\nNext steps:")
print(f"1. Monitor tasks at: https://code.earthengine.google.com/tasks")
print(f"2. After download, clip rasters to exact Indonesia bbox using GDAL/rioxarray")
print(f"3. Resample to 0.02 degrees if needed")
print(f"{'='*60}")
