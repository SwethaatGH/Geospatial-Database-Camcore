"""
Process WorldClim data for Indonesia
- Clip to Indonesia bounding box
- Resample to 0.02 degrees
- Rename to standard format: wc_{variable}_{year}_{month}.tif
"""

import os
# Fix PROJ database conflict - must be before importing rasterio
os.environ['PROJ_LIB'] = r'C:\Users\rcavalh\AppData\Local\Programs\Python\Python312\Lib\site-packages\pyproj\proj_dir\share\proj'

import rasterio
from rasterio.warp import reproject, Resampling, calculate_default_transform
from pathlib import Path
from tqdm import tqdm

# Indonesia bounding box
BBOX = {
    'lat_min': -10.3599874813,
    'lat_max': 5.47982086834,
    'lon_min': 95.2930261576,
    'lon_max': 141.03385176
}

# Paths
INPUT_DIR = Path(r"Q:\My Drive\Indonesia_WorldClim_2.5m")
OUTPUT_DIR = Path(r"C:\Users\rcavalh\Documents\Indonesia_WorldClim_Resampled")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Target resolution
TARGET_RES = 0.02

def process_worldclim_file(input_file, output_file):
    """Clip and resample a single WorldClim file"""
    
    with rasterio.open(input_file) as src:
        # Define output bounds and resolution
        dst_transform, dst_width, dst_height = calculate_default_transform(
            src.crs,
            'EPSG:4326',
            src.width,
            src.height,
            left=BBOX['lon_min'],
            bottom=BBOX['lat_min'],
            right=BBOX['lon_max'],
            top=BBOX['lat_max'],
            resolution=TARGET_RES
        )
        
        # Define output metadata
        dst_kwargs = src.meta.copy()
        dst_kwargs.update({
            'crs': 'EPSG:4326',
            'transform': dst_transform,
            'width': dst_width,
            'height': dst_height,
            'compress': 'lzw',
            'tiled': True,
            'dtype': 'float32',
            'nodata': -9999.0
        })
        
        # Create output file
        with rasterio.open(output_file, 'w', **dst_kwargs) as dst:
            for band in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, band),
                    destination=rasterio.band(dst, band),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=dst_transform,
                    dst_crs='EPSG:4326',
                    resampling=Resampling.bilinear,
                    dst_nodata=-9999.0
                )


def parse_filename(filename):
    """
    Parse WorldClim filename to extract variable, year, month
    Example: wc2.1_2.5m_prec_2016-05.tif -> prec, 2016, 05
    """
    parts = filename.stem.split('_')
    
    # Find variable (prec, tmax, tmin)
    if 'prec' in filename.stem:
        var_type = 'prec'
        # Extract date from end: ...prec_2016-05.tif
        date_str = filename.stem.split('_')[-1]  # "2016-05"
    elif 'tmax' in filename.stem:
        var_type = 'tmax'
        date_str = filename.stem.split('_')[-1]
    elif 'tmin' in filename.stem:
        var_type = 'tmin'
        date_str = filename.stem.split('_')[-1]
    else:
        return None, None, None
    
    # Parse year-month
    year, month = date_str.split('-')
    
    return var_type, year, month


def main():
    """Process all WorldClim files"""
    
    # Find all .tif files
    all_files = list(INPUT_DIR.rglob("*.tif"))
    
    print(f"Found {len(all_files)} WorldClim files")
    print(f"Input: {INPUT_DIR}")
    print(f"Output: {OUTPUT_DIR}")
    print(f"Clipping to: {BBOX}")
    print(f"Target resolution: {TARGET_RES}°")
    print(f"{'='*60}\n")
    
    processed = 0
    skipped = 0
    
    for input_file in tqdm(all_files, desc="Processing WorldClim"):
        # Parse filename
        var_type, year, month = parse_filename(input_file)
        
        if not var_type:
            print(f"  ⚠️  Skipping unrecognized file: {input_file.name}")
            skipped += 1
            continue
        
        # Create output filename: wc_prec_2016_05.tif
        output_filename = f"wc_{var_type}_{year}_{month}.tif"
        output_file = OUTPUT_DIR / output_filename
        
        # Skip if already processed
        if output_file.exists():
            skipped += 1
            continue
        
        try:
            process_worldclim_file(input_file, output_file)
            processed += 1
        except Exception as e:
            print(f"\n  ❌ Error processing {input_file.name}: {e}")
            continue
    
    print(f"\n{'='*60}")
    print(f"Processing complete!")
    print(f"  Processed: {processed} files")
    print(f"  Skipped: {skipped} files (already exist or unrecognized)")
    print(f"  Total output files: {len(list(OUTPUT_DIR.glob('*.tif')))}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
