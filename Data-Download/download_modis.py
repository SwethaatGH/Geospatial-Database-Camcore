"""
MODIS ET Download for Indonesia
Downloads 8-day ET data (MOD16A2GF).
Default mode exports each 8-day image clipped by the Indonesia bbox to avoid
yearly shard exports and local mosaicking.
"""

import ee

# Authenticate and initialize
ee.Authenticate()
ee.Initialize(project='ee-camcoredatabase')

# Indonesia bounding box (for reference - will clip locally after download)
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

# MODIS ET Collection
collection = (
    ee.ImageCollection('MODIS/061/MOD16A2GF')
    .select('ET')
    .filterBounds(bbox)
)

# Export parameters
START_DATE = '2000-03-14'  # resume after 2000-03-13
END_DATE = '2024-12-31'
OUTPUT_FOLDER = "Indonesia_MODIS_ET_8day"
SCALE = 500  # MODIS native resolution
EXPORT_MODE = "per_image"  # "per_image" (default) or "per_year"

print(f"Exporting MODIS ET data for Indonesia: {START_DATE} to {END_DATE}")
print(f"Export mode: {EXPORT_MODE}")
print(f"Output folder: {OUTPUT_FOLDER}")
print(f"Bounding box: {INDONESIA_BBOX}")
print(f"{'='*60}\n")

if EXPORT_MODE == "per_image":
    # Export each 8-day image clipped to bbox (avoids yearly shards)
    coll = collection.filterDate(START_DATE, END_DATE)
    count = coll.size().getInfo()
    print(f"Found {count} 8-day images")
    if count == 0:
        print("⚠️  No data found in date range")
        raise SystemExit(0)

    et_list = coll.toList(count)
    for i in range(count):
        image = ee.Image(et_list.get(i))
        date_str = ee.Date(image.get('system:time_start')).format('YYYY-MM-dd')
        date_label = date_str.getInfo()

        task = ee.batch.Export.image.toDrive(
            image=image,
            description=f"ET_Indonesia_{date_label}",
            folder=OUTPUT_FOLDER,
            fileNamePrefix=f"ET_Indonesia_{date_label}",
            scale=SCALE,
            region=bbox,
            crs='EPSG:4326',
            maxPixels=1e13,
            fileFormat='GeoTIFF'
        )

        task.start()
        print(f"  ✓ Export task started: ET_Indonesia_{date_label}")
        print(f"    Task ID: {task.id}")

else:
    # Export yearly stacks (may create shards)
    years = list(range(2000, 2025))
    for year in years:
        print(f"Processing year: {year}")

        start = ee.Date.fromYMD(year, 1, 1)
        end = start.advance(1, 'year')

        year_coll = collection.filterDate(start, end)
        count = year_coll.size().getInfo()
        print(f"  Found {count} 8-day images")

        if count == 0:
            print(f"  ⚠️  No data for {year}, skipping")
            continue

        year_img = year_coll.toBands()
        export_region = year_img.geometry().bounds()

        task = ee.batch.Export.image.toDrive(
            image=year_img,
            description=f"ET_Indonesia_{year}",
            folder=OUTPUT_FOLDER,
            fileNamePrefix=f"ET_Indonesia_{year}",
            scale=SCALE,
            region=export_region,
            crs='EPSG:4326',
            maxPixels=1e13,
            fileFormat='GeoTIFF'
        )

        task.start()
        print(f"  ✓ Export task started: ET_Indonesia_{year}")
        print(f"    Task ID: {task.id}\n")

print(f"{'='*60}")
print("All export tasks submitted!")
print(f"\nNext steps:")
print("1. Monitor tasks at: https://code.earthengine.google.com/tasks")
print("2. Resample to 0.02 degrees if needed")
print(f"{'='*60}")
