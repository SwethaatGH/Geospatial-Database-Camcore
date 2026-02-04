"""
Unpack CHIRPS Yearly Stacks to Daily Files
Converts multi-band yearly GeoTIFFs (365-366 bands) to individual daily files
Compatible with existing processing scripts

Run this script in Google Colab to unpack yearly files from Google Drive
Output daily files will be saved back to Google Drive
"""

import os
import rasterio
from tqdm import tqdm
from datetime import datetime, timedelta

# Mount Google Drive
from google.colab import drive
if not os.path.exists('/content/drive/MyDrive'):
    drive.mount('/content/drive')
else:
    print("Drive already mounted")

# Directories (all on Google Drive)
INPUT_DIR = "/content/drive/MyDrive/Indonesia_CHIRPS_Daily_Years/"
OUTPUT_DIR = "/content/drive/MyDrive/Indonesia_CHIRPS_Daily/"
os.makedirs(OUTPUT_DIR, exist_ok=True)

print(f"{'='*70}")
print(f"CHIRPS Yearly to Daily Unpacking")
print(f"{'='*70}")
print(f"Input Directory:  {INPUT_DIR}")
print(f"Output Directory: {OUTPUT_DIR}")
print(f"{'='*70}\n")


def unpack_yearly_chirps(yearly_file, year):
    """
    Unpack a yearly CHIRPS stack to individual daily files
    
    Args:
        yearly_file: Path to yearly multi-band GeoTIFF
        year: Year integer (e.g., 2020)
    """
    
    print(f"\nProcessing year: {year}")
    print(f"Input file: {yearly_file}")
    
    try:
        # Open the multi-band raster
        with rasterio.open(yearly_file) as src:
            profile = src.profile.copy()
            profile.update(count=1)  # Single band output
            
            num_bands = src.count
            print(f"  Total bands (days): {num_bands}")
            
            # Starting date for this year
            start_date = datetime(year, 1, 1)
            
            # Process each band (day)
            for band_idx in tqdm(range(1, num_bands + 1), desc=f"  Year {year}"):
                
                # Calculate date for this band
                current_date = start_date + timedelta(days=band_idx - 1)
                date_str = current_date.strftime("%Y-%m-%d")
                
                # Output filename: CHIRPS_YYYY-MM-DD.tif
                output_file = os.path.join(OUTPUT_DIR, f"CHIRPS_{date_str}.tif")
                
                # Skip if already exists
                if os.path.exists(output_file):
                    continue
                
                # Read this band
                band_data = src.read(band_idx)
                
                # Write to individual file
                with rasterio.open(output_file, 'w', **profile) as dst:
                    dst.write(band_data, 1)
            
            print(f"✓ Completed year {year}: {num_bands} daily files")
            return True
            
    except Exception as e:
        print(f"✗ Error processing year {year}: {e}")
        return False


# Main processing loop
print("\nStarting unpacking process...\n")

successful = []
failed = []

# Process years 1990-2024 (change start year to resume from specific year)
START_YEAR = 1990  # Change this to resume (e.g., 2008 to skip completed years)
for year in range(START_YEAR, 2025):
    
    # Construct yearly filename
    yearly_filename = f"CHIRPS_Daily_{year}.tif"
    yearly_path = os.path.join(INPUT_DIR, yearly_filename)
    
    # Check if file exists
    if not os.path.exists(yearly_path):
        print(f"⚠ Skipping {year}: File not found - {yearly_filename}")
        failed.append(year)
        continue
    
    # Unpack this year
    if unpack_yearly_chirps(yearly_path, year):
        successful.append(year)
    else:
        failed.append(year)

# Summary
print(f"\n{'='*70}")
print(f"UNPACKING SUMMARY")
print(f"{'='*70}")
print(f"✓ Successful: {len(successful)} years")
print(f"✗ Failed: {len(failed)} years")

if successful:
    print(f"\nSuccessfully unpacked:")
    for year in successful:
        print(f"  ✓ {year}")

if failed:
    print(f"\nFailed to unpack:")
    for year in failed:
        print(f"  ✗ {year}")

print(f"\nDaily files saved to: {OUTPUT_DIR}")
print(f"Total expected files: ~12,775 (365-366 days × 35 years)")
print(f"{'='*70}")
