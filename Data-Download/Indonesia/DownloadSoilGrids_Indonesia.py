"""
SoilGrids Download for Indonesia
Uses remote VRT streaming to avoid downloading huge global files
Clips each variable to Indonesia bounding box (+0.1° buffer)
"""

import os
import rioxarray as rxr
from tqdm import tqdm

# Mount Google Drive
from google.colab import drive
if not os.path.exists('/content/drive/MyDrive'):
    drive.mount('/content/drive')
else:
    print("Drive already mounted")

# Output directory
OUTPUT_DIR = "/content/drive/MyDrive/Indonesia_SoilGrids/"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Indonesia bounding box (exact from you)
INDO_BBOX = {
    'minx': 95.2930261576,
    'miny': -10.3599874813,
    'maxx': 141.03385176,
    'maxy': 5.47982086834
}

# Add small grid alignment buffer
BUFFER = 0.1

# SoilGrids variables
SOIL_PROPERTIES = [
    'bdod', 'cec', 'cfvo', 'clay', 'nitrogen', 'ocd', 'ocs',
    'phh2o', 'sand', 'silt', 'soc', 'wv0010', 'wv0033', 'wv1500'
]

DEPTH = "0-5cm"
BASE_URL = "https://files.isric.org/soilgrids/latest/data"


def process_property(prop):
    print(f"\nProcessing: {prop}")

    vrt_url = f"{BASE_URL}/{prop}/{prop}_{DEPTH}_mean.vrt"
    output_file = f"{OUTPUT_DIR}/{prop}_{DEPTH}_Indonesia.tif"

    # Skip if already exists
    if os.path.exists(output_file):
        print(f"✓ Already exists: {output_file}")
        return True

    try:
        print(f"  Opening remote VRT: {vrt_url}")
        ds = rxr.open_rasterio(vrt_url, masked=True)
        ds = ds.rio.write_crs("EPSG:4326", inplace=True)

        print(f"  Clipping to Indonesia bbox (+buffer {BUFFER}°)")

        clipped = ds.rio.clip_box(
            minx=INDO_BBOX['minx'] - BUFFER,
            miny=INDO_BBOX['miny'] - BUFFER,
            maxx=INDO_BBOX['maxx'] + BUFFER,
            maxy=INDO_BBOX['maxy'] + BUFFER,
            allow_one_dimensional_raster=True
        )

        print("  Saving clipped TIFF...")
        clipped.rio.to_raster(output_file, compress="LZW")

        size_mb = os.path.getsize(output_file) / (1024 * 1024)
        print(f"✓ Saved: {output_file} ({size_mb:.2f} MB)")

        return True

    except Exception as e:
        print(f"✗ Error processing {prop}: {e}")
        return False


# Run download for all properties
success, failed = [], []

print("\n=========== STARTING SOILGRIDS INDONESIA DOWNLOAD ===========\n")

for idx, prop in enumerate(SOIL_PROPERTIES, 1):
    print(f"[{idx}/{len(SOIL_PROPERTIES)}] ====================================================")
    if process_property(prop):
        success.append(prop)
    else:
        failed.append(prop)

# Summary
print("\n======================== SUMMARY ===========================")
print(f"Successful ({len(success)}): {success}")
print(f"Failed ({len(failed)}): {failed}")
print(f"Files stored in: {OUTPUT_DIR}")
print("============================================================\n")
