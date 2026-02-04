"""
MODIS ET Download for USA
Downloads yearly stacks of 8-day ET data (MOD16A2GF)
Exports full global tiles to avoid GEE projection errors
Clip to USA bbox during post-processing
"""

import ee

# Authenticate and initialize
ee.Authenticate()
ee.Initialize(project='ee-camcoredatabase')

# USA bounding box (includes Alaska and Hawaii)
USA_BBOX = {
    'lat_min': 18.91619,
    'lat_max': 71.3577635769,
    'lon_min': -171.791110603,
    'lon_max': -66.96466
}

# Create GEE geometry for filtering (not clipping)
bbox = ee.Geometry.BBox(
    USA_BBOX['lon_min'],
    USA_BBOX['lat_min'],
    USA_BBOX['lon_max'],
    USA_BBOX['lat_max']
)

# MODIS ET Collection
collection = (
    ee.ImageCollection('MODIS/061/MOD16A2GF')
    .select('ET')
    .filterBounds(bbox)  # Filter to reduce data, but don't clip yet
)

# Export parameters
YEARS = list(range(2000, 2025))
OUTPUT_FOLDER = "USA_MODIS_ET_Years"
SCALE = 500  # MODIS native resolution

print(f"Exporting MODIS ET data for USA: {YEARS[0]}-{YEARS[-1]}")
print(f"Output folder: {OUTPUT_FOLDER}")
print(f"Bounding box: {USA_BBOX}")
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
    print(f"  Found {count} 8-day images")
    
    if count == 0:
        print(f"  ⚠️  No data for {year}, skipping")
        continue
    
    # Stack all bands (one per 8-day period)
    year_img = year_coll.toBands()
    
    # Use bbox directly for export region (avoids geometry bounds error)
    # For large regions like USA, computing bounds can fail without error margin
    export_region = bbox
    
    # Export task
    task = ee.batch.Export.image.toDrive(
        image=year_img.clip(bbox),  # Clip to exact bbox
        description=f"ET_USA_{year}",
        folder=OUTPUT_FOLDER,
        fileNamePrefix=f"ET_USA_{year}",
        scale=SCALE,
        region=export_region,
        crs='EPSG:4326',  # Ensure WGS84
        maxPixels=1e13,
        fileFormat='GeoTIFF'
    )
    
    task.start()
    print(f"  ✓ Export task started: ET_USA_{year}")
    print(f"    Task ID: {task.id}\n")

print(f"{'='*60}")
print(f"All {len(YEARS)} export tasks submitted!")
print(f"\nNext steps:")
print(f"1. Monitor tasks at: https://code.earthengine.google.com/tasks")
print(f"2. After download, clip rasters to exact USA bbox using GDAL/rioxarray")
print(f"3. Resample to 0.02 degrees if needed")
print(f"{'='*60}")
