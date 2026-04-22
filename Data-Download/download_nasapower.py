"""
NASA POWER Download Script - Brazil 2025
Downloads all 47 NASA POWER variables for Brazil in 2025 from AWS S3 Zarr
Saves as individual NetCDF files to local C drive
"""

import os
import sys
import subprocess
from pathlib import Path

# Install required dependencies
print("Installing required packages...")
try:
    import xarray as xr
    import fsspec
    import zarr
except ImportError:
    print("Installing xarray, fsspec, s3fs, zarr, netCDF4...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", 
                          "xarray", "fsspec", "s3fs", "zarr", "netCDF4"])
    import xarray as xr
    import fsspec
    import zarr

print("✓ Dependencies ready\n")

# Configuration
LAT_MIN = -39.0208
LAT_MAX = 18.2292
LON_MIN = -94.1875
LON_MAX = 37.0625

NASA_POWER_URL = 'https://nasa-power.s3.us-west-2.amazonaws.com/syn1deg/temporal/power_syn1deg_monthly_temporal_lst.zarr'

# Output directory (C drive)
OUTPUT_DIR = Path(r"C:\Users\rcavalh\Documents\Camcore25\DB_Indonesia\Brazil_NASA_POWER_2025")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TIME_START = "2025-01-01"
TIME_END = "2025-12-31"

# Print configuration
print("=" * 80)
print("NASA POWER Download - Brazil 2025")
print("=" * 80)
print(f"Source: {NASA_POWER_URL}")
print(f"Region: Brazil ({LAT_MIN}°, {LON_MIN}°) to ({LAT_MAX}°, {LON_MAX}°)")
print(f"Time: {TIME_START} to {TIME_END}")
print(f"Output: {OUTPUT_DIR}")
print("=" * 80)
print()

# Open the Zarr dataset
print("Opening NASA POWER Zarr dataset...")
try:
    ds = xr.open_dataset(NASA_POWER_URL, engine='zarr')
    print("✓ Dataset opened successfully!")
    print(f"\nDataset dimensions: {dict(ds.dims)}")
    print(f"Total variables: {len(list(ds.data_vars))}")
    print(f"\nVariables: {list(ds.data_vars)}\n")
except Exception as e:
    print(f"✗ Error opening dataset: {e}")
    sys.exit(1)

# Function to download one variable
def download_variable(ds, var_name, output_dir):
    """
    Extract and save one variable for Brazil 2025.
    Saves as individual NetCDF file.
    """
    output_file = output_dir / f"{var_name}.nc"
    
    # Skip if already exists
    if output_file.exists():
        return True, "exists"
    
    try:
        # Select Brazil region and 2025 time range
        ds_region = ds[var_name].sel(
            lat=slice(LAT_MIN, LAT_MAX),
            lon=slice(LON_MIN, LON_MAX),
            time=slice(TIME_START, TIME_END)
        ).load()
        
        # Save to NetCDF
        ds_region.to_netcdf(output_file)
        
        file_size = output_file.stat().st_size / 1024  # KB
        return True, file_size
        
    except Exception as e:
        return False, str(e)

# Download all variables
print("=" * 80)
print("DOWNLOADING ALL VARIABLES")
print("=" * 80)
print()

variables = list(ds.data_vars)
success_count = 0
failed_count = 0
skipped_count = 0
failed_vars = []
total_size_kb = 0

for i, var in enumerate(variables, 1):
    print(f"[{i:2d}/{len(variables)}] {var:<30}", end=" ... ")
    sys.stdout.flush()
    
    success, result = download_variable(ds, var, OUTPUT_DIR)
    
    if success:
        if result == "exists":
            print("⏭️  Skipped (already exists)")
            skipped_count += 1
        else:
            file_size_kb = result
            total_size_kb += file_size_kb
            print(f"✓ Downloaded ({file_size_kb:.1f} KB)")
            success_count += 1
    else:
        error_msg = result
        print(f"✗ Error: {error_msg}")
        failed_count += 1
        failed_vars.append((var, error_msg))

# Summary
print()
print("=" * 80)
print("DOWNLOAD COMPLETE")
print("=" * 80)
print(f"Total variables: {len(variables)}")
print(f"Successfully downloaded: {success_count}")
print(f"Already existed (skipped): {skipped_count}")
print(f"Failed: {failed_count}")
print(f"Total size downloaded: {total_size_kb / 1024 / 1024:.2f} GB")

if failed_vars:
    print("\n❌ Failed variables:")
    for var, error in failed_vars:
        print(f"   • {var}: {error}")
else:
    print("\n✅ All variables downloaded successfully!")

print("\n" + "=" * 80)
print(f"Output directory: {OUTPUT_DIR}")
print(f"Files created: {success_count} NetCDF files")
print("\nNext steps:")
print("1. Process NetCDFs to monthly GeoTIFFs (using gdal_translate or rasterio)")
print("2. Resample to 0.02° if needed (gdalwarp)")
print("3. Upload to covariables1 database (raster2pgsql)")
print("=" * 80)

# Close dataset
ds.close()
print("\nDataset closed.")
print("✓ Script completed successfully!")
