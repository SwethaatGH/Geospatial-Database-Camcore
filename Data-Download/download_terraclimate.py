"""
Download TerraClimate data for Indonesia region

TerraClimate provides monthly climate data at ~4km resolution (1/24 degree)
Data source: https://www.climatologylab.org/terraclimate.html
Variables: aet, def, pdsi, pet, ppt, q, soil, srad, tmax, tmin, vap, vpd, ws
Period: 1982-2024
"""

import requests
import os
from pathlib import Path
from datetime import datetime

# Configuration
OUTPUT_FOLDER = r"Q:\My Drive\Indonesia_TerraClimate"
START_YEAR = 1982
END_YEAR = 2024

# TerraClimate variables
VARIABLES = [
    'aet',    # Actual Evapotranspiration (mm)
    'def',    # Climate Water Deficit (mm)
    'pdsi',   # Palmer Drought Severity Index
    'pet',    # Potential Evapotranspiration (mm)
    'ppt',    # Precipitation (mm)
    'q',      # Runoff (mm)
    'soil',   # Soil Moisture (mm)
    'srad',   # Downward Surface Shortwave Radiation (W/m²)
    'tmax',   # Max Temperature (°C)
    'tmin',   # Min Temperature (°C)
    'vap',    # Vapor Pressure (kPa)
    'vpd',    # Vapor Pressure Deficit (kPa)
    'ws'      # Wind Speed (m/s)
]

# TerraClimate download URL pattern
BASE_URL = "https://climate.northwestknowledge.net/TERRACLIMATE-DATA"

def download_file(url, output_path):
    """Download a file with progress indication."""
    try:
        response = requests.get(url, stream=True, timeout=300)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        
        with open(output_path, 'wb') as f:
            if total_size == 0:
                f.write(response.content)
            else:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        progress = (downloaded / total_size) * 100
                        print(f"\r  Progress: {progress:.1f}%", end='', flush=True)
        
        print()  # New line after progress
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"\n  ERROR: {e}")
        return False

def main():
    print("="*70)
    print("TerraClimate Data Download for Indonesia")
    print("="*70)
    print(f"Output folder: {OUTPUT_FOLDER}")
    print(f"Years: {START_YEAR}-{END_YEAR}")
    print(f"Variables: {len(VARIABLES)}")
    print("="*70)
    
    # Create output folder
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    
    total_files = len(VARIABLES) * (END_YEAR - START_YEAR + 1)
    downloaded = 0
    skipped = 0
    failed = 0
    
    print(f"\nTotal files to download: {total_files}\n")
    
    for var in VARIABLES:
        print(f"\n{'='*70}")
        print(f"Variable: {var.upper()}")
        print(f"{'='*70}")
        
        for year in range(START_YEAR, END_YEAR + 1):
            # TerraClimate filename pattern: TerraClimate_var_YYYY.nc
            filename = f"TerraClimate_{var}_{year}.nc"
            output_path = os.path.join(OUTPUT_FOLDER, filename)
            
            # Check if file already exists
            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                if file_size > 1000000:  # At least 1MB
                    print(f"[{downloaded + skipped + failed + 1}/{total_files}] ⊙ {filename} (already exists, {file_size/1024/1024:.1f} MB)")
                    skipped += 1
                    continue
            
            # Download URL
            url = f"{BASE_URL}/{filename}"
            
            print(f"[{downloaded + skipped + failed + 1}/{total_files}] ↓ {filename}")
            print(f"  URL: {url}")
            
            success = download_file(url, output_path)
            
            if success:
                file_size = os.path.getsize(output_path)
                print(f"  ✓ Downloaded ({file_size/1024/1024:.1f} MB)")
                downloaded += 1
            else:
                if os.path.exists(output_path):
                    os.remove(output_path)
                print(f"  ✗ Failed")
                failed += 1
    
    # Summary
    print("\n" + "="*70)
    print("DOWNLOAD COMPLETE")
    print("="*70)
    print(f"Total files: {total_files}")
    print(f"Downloaded: {downloaded}")
    print(f"Skipped (already exists): {skipped}")
    print(f"Failed: {failed}")
    print("="*70)
    
    if failed > 0:
        print("\nNote: Some downloads failed. You can re-run this script to retry failed downloads.")
    
    print(f"\nNext steps:")
    print(f"1. Convert NetCDF to GeoTIFF using scripts in Data-Processing/netcdf2raster/")
    print(f"2. Clip to Indonesia extent and resample to 0.02° resolution")
    print(f"3. Upload to PostgreSQL database")

if __name__ == "__main__":
    main()
