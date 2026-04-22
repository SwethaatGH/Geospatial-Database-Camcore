"""
NASA POWER Preprocessing Script - Brazil 2025
Converts NetCDF files to GeoTIFFs and resamples to 0.02° resolution
Uses parallel processing with 16 workers
"""

import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from multiprocessing import Pool, cpu_count

# Configuration
INPUT_DIR = Path(r"C:\Users\rcavalh\Documents\Camcore25\DB_Indonesia\Brazil_NASA_POWER_2025")
OUTPUT_DIR = Path(r"P:\Brazil_NASA_POWER_2025_TIFF")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# GDAL executables path (adjust if QGIS/GDAL is installed elsewhere)
GDAL_BIN = r"C:\Program Files\QGIS 3.40.4\bin"
GDAL_TRANSLATE = os.path.join(GDAL_BIN, "gdal_translate.exe")
GDALWARP = os.path.join(GDAL_BIN, "gdalwarp.exe")

# Set PROJ_LIB to avoid conflict with PostgreSQL's old proj.db
PROJ_LIB = r"C:\Program Files\QGIS 3.40.4\share\proj"
os.environ['PROJ_LIB'] = PROJ_LIB

# Target resolution (0.02° to match CHIRPS)
TARGET_RES = "0.02"

# Parallel processing configuration
NUM_WORKERS = 16  # Matching CHIRPS/upload pipeline

# Optional: process only specific variables (set to [] to process all)
VAR_FILTER = {
    "AIRMASS_00",
    "AIRMASS_14",
    "ALLSKY_NKT",
    "ALLSKY_SFC_LW_DWN_11",
    "ALLSKY_SFC_LW_UP_SD",
    "ALLSKY_SFC_PAR_DIRH_12",
    "ALLSKY_SFC_PAR_TOT_11",
    "ALLSKY_SFC_PAR_TOT_MIN",
    "ALLSKY_SFC_SW_DIFF_11",
}

# Function to convert NetCDF to GeoTIFF (worker function for parallel processing)
def convert_netcdf_to_tiff(nc_file):
    """
    Convert NetCDF to GeoTIFF with resampling.
    
    NASA POWER is 1° resolution, we resample to 0.02° to match CHIRPS.
    Worker function for parallel processing.
    """
    var_name = nc_file.stem
    output_file = OUTPUT_DIR / f"{var_name}.tif"
    
    # Skip if already exists (unless filtered re-run)
    if output_file.exists() and (not VAR_FILTER or var_name not in VAR_FILTER):
        return {
            'var_name': var_name,
            'status': 'skipped',
            'size_mb': output_file.stat().st_size / 1024 / 1024
        }
    # If reprocessing a filtered variable, remove existing output to allow overwrite
    if output_file.exists() and VAR_FILTER and var_name in VAR_FILTER:
        output_file.unlink()
    
    try:
        # Step 1: Convert NetCDF to intermediate GeoTIFF
        # Use gdal_translate to read NetCDF
        temp_tiff = OUTPUT_DIR / f"{var_name}_temp.tif"
        if temp_tiff.exists():
            temp_tiff.unlink()
        
        cmd_translate = [
            GDAL_TRANSLATE,
            '-of', 'GTiff',
            '-a_srs', 'EPSG:4326',
            str(nc_file),
            str(temp_tiff)
        ]
        
        result = subprocess.run(cmd_translate, capture_output=True, text=True)
        if result.returncode != 0:
            return {
                'var_name': var_name,
                'status': 'error',
                'message': f"gdal_translate failed: {result.stderr[:200]}"
            }
        
        # Step 2: Resample to 0.02° resolution
        cmd_warp = [
            GDALWARP,
            '-tr', TARGET_RES, TARGET_RES,
            '-r', 'bilinear',
            '-srcnodata', '-9999.0',
            '-dstnodata', '-9999.0',
            '-co', 'COMPRESS=LZW',
            '-co', 'TILED=YES',
            '-co', 'BIGTIFF=YES',
            str(temp_tiff),
            str(output_file)
        ]
        
        result = subprocess.run(cmd_warp, capture_output=True, text=True)
        if result.returncode != 0:
            return {
                'var_name': var_name,
                'status': 'error',
                'message': f"gdalwarp failed: {result.stderr[:200]}"
            }
        
        # Clean up temporary file
        if temp_tiff.exists():
            temp_tiff.unlink()
        
        file_size_mb = output_file.stat().st_size / 1024 / 1024
        
        return {
            'var_name': var_name,
            'status': 'success',
            'size_mb': file_size_mb
        }
        
    except Exception as e:
        return {
            'var_name': var_name,
            'status': 'error',
            'message': str(e)
        }

# Main execution - protected by if __name__ guard for Windows multiprocessing
if __name__ == '__main__':
    # Print header and check input files (inside main block to avoid duplication)
    print("=" * 80)
    print("NASA POWER Preprocessing - Brazil 2025")
    print("=" * 80)
    print(f"Input directory: {INPUT_DIR}")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Target resolution: {TARGET_RES}°")
    print(f"Parallel workers: {NUM_WORKERS}")
    print("=" * 80)
    print()

    # Check if input files exist
    nc_files = list(INPUT_DIR.glob("*.nc"))
    if VAR_FILTER:
        nc_files = [f for f in nc_files if f.stem in VAR_FILTER]
    if not nc_files:
        print(f"❌ No NetCDF files found in {INPUT_DIR}")
        sys.exit(1)

    print(f"Found {len(nc_files)} NetCDF files to process\n")
    
    # Process all variables with parallel workers
    print("=" * 80)
    print("PROCESSING NETCDF FILES (Parallel Processing)")
    print("=" * 80)
    print()

    print(f"Starting preprocessing with {NUM_WORKERS} parallel workers...")
    print(f"Processing {len(nc_files)} variables\n")

    # Process files in parallel
    start_time = datetime.now()

    with Pool(processes=NUM_WORKERS) as pool:
        results = pool.map(convert_netcdf_to_tiff, sorted(nc_files))

    end_time = datetime.now()
    elapsed_time = (end_time - start_time).total_seconds()

    # Analyze results
    success_count = 0
    failed_count = 0
    skipped_count = 0
    failed_vars = []
    total_size_mb = 0

    for result in results:
        var_name = result['var_name']
        status = result['status']
        
        if status == 'success':
            success_count += 1
            total_size_mb += result['size_mb']
            print(f"✓ {var_name:<30} ({result['size_mb']:.1f} MB)")
        elif status == 'skipped':
            skipped_count += 1
            total_size_mb += result['size_mb']
            print(f"⏭️  {var_name:<30} (skipped - already exists)")
        elif status == 'error':
            failed_count += 1
            error_msg = result['message']
            print(f"✗ {var_name:<30} Error: {error_msg}")
            failed_vars.append((var_name, error_msg))

    # Summary
    print()
    print("=" * 80)
    print("PREPROCESSING COMPLETE")
    print("=" * 80)
    print(f"Total variables: {len(nc_files)}")
    print(f"Successfully processed: {success_count}")
    print(f"Already existed (skipped): {skipped_count}")
    print(f"Failed: {failed_count}")
    print(f"Total size: {total_size_mb / 1024:.2f} GB")
    print(f"Processing time: {elapsed_time:.1f} seconds ({elapsed_time/60:.1f} minutes)")
    if success_count > 0:
        print(f"Average time per file: {elapsed_time/len(nc_files):.1f} seconds")
        print(f"Throughput: {len(nc_files)/(elapsed_time/60):.1f} files/minute")

    if failed_vars:
        print("\n❌ Failed variables:")
        for var, error in failed_vars:
            print(f"   • {var}: {error}")
    else:
        print("\n✅ All files processed successfully!")

    print("\n" + "=" * 80)
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Files created: {success_count} GeoTIFF files (0.02° resolution)")
    print("\nNext steps:")
    print("1. Run upload_nasapower_brazil_2025.py to upload to database")
    print("=" * 80)

    print("\n✓ Preprocessing completed successfully!")
