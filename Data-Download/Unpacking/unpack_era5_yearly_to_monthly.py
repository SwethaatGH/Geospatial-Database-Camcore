"""
Unpack ERA5 Yearly Variable Stacks to Monthly Multi-Variable Files
Converts yearly single-variable GeoTIFFs to monthly multi-variable files
Input: ERA5_{variable}_{year}.tif (1 variable × 12 months)
Output: era5land_{year}_{month}.tif (15 variables × 1 month)

Run this script in Google Colab to reorganize ERA5 data from Google Drive
"""

import os
import rasterio
import numpy as np
from tqdm import tqdm
from collections import defaultdict

# Mount Google Drive
from google.colab import drive
if not os.path.exists('/content/drive/MyDrive'):
    drive.mount('/content/drive')
else:
    print("Drive already mounted")

# Directories (all on Google Drive)
INPUT_DIR = "/content/drive/MyDrive/Indonesia_ERA5_Variables/"
OUTPUT_DIR = "/content/drive/MyDrive/Indonesia_ERA5_Monthly/"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ERA5 variables (must match your download script)
VARIABLES = [
    "temperature_2m",
    "skin_temperature",
    "soil_temperature_level_1",
    "soil_temperature_level_2",
    "soil_temperature_level_3",
    "volumetric_soil_water_layer_1",
    "volumetric_soil_water_layer_2",
    "volumetric_soil_water_layer_3",
    "u_component_of_wind_10m",
    "v_component_of_wind_10m",
    "surface_pressure",
    "total_precipitation_sum",
    "surface_latent_heat_flux_sum",
    "surface_net_solar_radiation_sum",
    "evaporation_from_vegetation_transpiration_sum"
]

print(f"{'='*70}")
print(f"ERA5 Variable-Year to Monthly Multi-Variable Conversion")
print(f"{'='*70}")
print(f"Input Directory:  {INPUT_DIR}")
print(f"Output Directory: {OUTPUT_DIR}")
print(f"Variables: {len(VARIABLES)}")
print(f"{'='*70}\n")


def process_year(year):
    """
    Process all variables for a single year
    Reorganize from variable-yearly to monthly-multivariable
    
    Args:
        year: Year integer (e.g., 2020)
    """
    
    print(f"\n{'='*60}")
    print(f"Processing year: {year}")
    print(f"{'='*60}")
    
    # Storage for each month's bands from all variables
    # month_data[month_idx] = [(var_name, band_data), ...]
    month_data = defaultdict(list)
    profile = None
    
    # Read each variable file for this year
    for var_idx, var_name in enumerate(VARIABLES, 1):
        
        input_file = os.path.join(INPUT_DIR, f"ERA5_{var_name}_{year}.tif")
        
        if not os.path.exists(input_file):
            print(f"  ⚠ Missing: {var_name}")
            continue
        
        print(f"  [{var_idx:2d}/{len(VARIABLES)}] Reading {var_name}...", end=" ")
        
        try:
            with rasterio.open(input_file) as src:
                
                # Save profile from first file
                if profile is None:
                    profile = src.profile.copy()
                
                num_bands = src.count  # Should be 12 (months)
                
                if num_bands != 12:
                    print(f"✗ Expected 12 bands, got {num_bands}")
                    continue
                
                # Read all 12 months for this variable
                for month_idx in range(1, 13):
                    band_data = src.read(month_idx)
                    month_data[month_idx].append((var_name, band_data))
                
                print(f"✓ {num_bands} months")
                
        except Exception as e:
            print(f"✗ Error: {e}")
            continue
    
    # Now write monthly files
    if profile is None:
        print(f"  ✗ No data read for year {year}")
        return False
    
    print(f"\n  Writing monthly files...")
    
    # Update profile for multi-band output
    profile.update(count=len(VARIABLES))
    
    # Create year subdirectory
    year_dir = os.path.join(OUTPUT_DIR, str(year))
    os.makedirs(year_dir, exist_ok=True)
    
    success_count = 0
    
    for month in range(1, 13):
        
        month_str = f"{month:02d}"
        output_file = os.path.join(year_dir, f"era5land_{year}_{month_str}.tif")
        
        # Skip if already exists
        if os.path.exists(output_file):
            print(f"    {month_str}: Already exists")
            success_count += 1
            continue
        
        # Check if we have all variables for this month
        if len(month_data[month]) != len(VARIABLES):
            print(f"    {month_str}: ✗ Incomplete data ({len(month_data[month])}/{len(VARIABLES)} variables)")
            continue
        
        try:
            # Write all variables as bands to monthly file
            with rasterio.open(output_file, 'w', **profile) as dst:
                for band_idx, (var_name, band_data) in enumerate(month_data[month], 1):
                    dst.write(band_data, band_idx)
                    dst.set_band_description(band_idx, var_name)
            
            print(f"    {month_str}: ✓ Saved ({len(VARIABLES)} variables)")
            success_count += 1
            
        except Exception as e:
            print(f"    {month_str}: ✗ Error: {e}")
    
    print(f"\n  ✓ Year {year}: {success_count}/12 monthly files created")
    return success_count == 12


# Main processing loop
print("\nStarting conversion process...\n")

successful_years = []
failed_years = []

# Process years 1990-2024
START_YEAR = 1990  # Change this to resume from specific year
for year in range(START_YEAR, 2025):
    
    if process_year(year):
        successful_years.append(year)
    else:
        failed_years.append(year)

# Summary
print(f"\n{'='*70}")
print(f"CONVERSION SUMMARY")
print(f"{'='*70}")
print(f"✓ Successful: {len(successful_years)} years")
print(f"✗ Failed/Incomplete: {len(failed_years)} years")

if successful_years:
    print(f"\nSuccessfully converted:")
    for year in successful_years[:10]:  # Show first 10
        print(f"  ✓ {year}")
    if len(successful_years) > 10:
        print(f"  ... and {len(successful_years) - 10} more")

if failed_years:
    print(f"\nFailed or incomplete years:")
    for year in failed_years:
        print(f"  ✗ {year}")

print(f"\nMonthly files saved to: {OUTPUT_DIR}")
print(f"Total expected files: 420 (12 months × 35 years)")
print(f"Format: era5land_YYYY_MM.tif (15 bands per file)")
print(f"{'='*70}")
