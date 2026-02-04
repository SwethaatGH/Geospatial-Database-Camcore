"""
Unpack ERA5-Land yearly files (365/366 daily bands per variable) into daily multi-variable files.

Input: ERA5_{variable}_{year}.tif files with 365 or 366 bands (one per day)
Output: era5land_YYYY-MM-DD.tif files with 15 bands (one per variable)

This script processes all 15 ERA5 variables and creates daily multi-variable rasters
compatible with the existing processing pipeline (resampling, clipping, upload).
"""

import os
from pathlib import Path
import rasterio
from rasterio.transform import from_bounds
from datetime import datetime, timedelta
import numpy as np

# Configuration - CHANGE THESE PATHS FOR LOCAL EXECUTION
INPUT_DIR = r"C:\Path\To\ERA5_Indonesia_Variables"  # Where your ERA5_{var}_{year}.tif files are
OUTPUT_DIR = r"C:\Path\To\Indonesia_ERA5_Daily"      # Where daily multi-band files will be saved
START_YEAR = 1990
END_YEAR = 2024

# ERA5-Land variables in the order they should appear as bands
# Based on actual filenames in the folder
VARIABLES = [
    'evaporation_from_vegetation_transpiration_sum',
    'skin_temperature',
    'soil_temperature_level_1',
    'soil_temperature_level_2',
    'soil_temperature_level_3',
    'surface_latent_heat_flux_sum',
    'surface_net_solar_radiation_sum',
    'surface_pressure',
    'temperature_2m',
    'total_precipitation_sum',
    'u_component_of_wind_10m',
    'v_component_of_wind_10m',
    'volumetric_soil_water_layer_1',
    'volumetric_soil_water_layer_2',
    'volumetric_soil_water_layer_3'
]

def is_leap_year(year):
    """Check if a year is a leap year."""
    return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)

def get_dates_for_year(year):
    """Generate list of dates for a given year."""
    num_days = 366 if is_leap_year(year) else 365
    start_date = datetime(year, 1, 1)
    return [start_date + timedelta(days=i) for i in range(num_days)]

def create_output_directory():
    """Create output directory if it doesn't exist."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Output directory: {OUTPUT_DIR}")

def get_reference_metadata(variable, year):
    """Get metadata from first variable file for the year."""
    filepath = f"{INPUT_DIR}ERA5_{variable}_{year}.tif"
    
    if not os.path.exists(filepath):
        return None
    
    with rasterio.open(filepath) as src:
        return {
            'crs': src.crs,
            'transform': src.transform,
            'width': src.width,
            'height': src.height,
            'dtype': src.dtypes[0],
            'nodata': src.nodata,
            'num_bands': src.count
        }

def unpack_year(year):
    """Unpack all daily data for a given year into multi-variable daily files.
    
    DATA QUALITY APPROACH:
    1. Validate ALL source files exist upfront (fail fast)
    2. Verify metadata consistency across all variables
    3. Process one variable at a time with shape validation
    4. Final validation pass on all output files
    """
    print(f"\n{'='*60}")
    print(f"Processing Year: {year}")
    print(f"{'='*60}")
    
    # STEP 1: Verify ALL source files exist before processing
    print("→ Validating source files...")
    missing = []
    for var in VARIABLES:
        if not os.path.exists(f"{INPUT_DIR}ERA5_{var}_{year}.tif"):
            missing.append(var)
    if missing:
        print(f"✗ Missing {len(missing)} files: {', '.join(missing[:3])}...")
        return False
    
    # STEP 2: Get and validate reference metadata
    ref_meta = get_reference_metadata(VARIABLES[0], year)
    if ref_meta is None:
        print(f"✗ Reference file not found for year {year}")
        return False
    
    num_days = ref_meta['num_bands']
    expected_days = 366 if is_leap_year(year) else 365
    
    if num_days != expected_days:
        print(f"⚠ Warning: Expected {expected_days} days, got {num_days} bands")
    
    # STEP 3: Validate metadata consistency across ALL variables
    print("→ Validating metadata consistency...")
    for var in VARIABLES[1:]:
        meta = get_reference_metadata(var, year)
        if not meta:
            print(f"✗ Cannot read {var}")
            return False
        if (meta['num_bands'] != num_days or 
            meta['width'] != ref_meta['width'] or 
            meta['height'] != ref_meta['height'] or
            meta['crs'] != ref_meta['crs']):
            print(f"✗ Metadata mismatch for {var}")
            return False
    
    print(f"✓ Validated: {num_days} days, {len(VARIABLES)} vars, {ref_meta['width']}x{ref_meta['height']}")
    
    # Get dates for this year
    dates = get_dates_for_year(year)
    
    # Count files to process and validate existing files
    output_files = [f"{OUTPUT_DIR}era5land_{date.strftime('%Y-%m-%d')}.tif" for date in dates]
    files_to_create = []
    files_exist = 0
    files_incomplete = 0
    
    for output_file in output_files:
        if os.path.exists(output_file):
            # Validate existing file has correct number of bands
            try:
                with rasterio.open(output_file) as dst:
                    if dst.count == len(VARIABLES):
                        files_exist += 1
                    else:
                        # Incomplete file - needs to be recreated
                        print(f"  ⚠ Incomplete file detected (has {dst.count}/{len(VARIABLES)} bands): {os.path.basename(output_file)}")
                        os.remove(output_file)
                        files_to_create.append(output_file)
                        files_incomplete += 1
            except Exception as e:
                # Corrupt file - needs to be recreated
                print(f"  ⚠ Corrupt file detected: {os.path.basename(output_file)}")
                try:
                    os.remove(output_file)
                except:
                    pass
                files_to_create.append(output_file)
                files_incomplete += 1
        else:
            files_to_create.append(output_file)
    
    if files_exist > 0:
        print(f"⊙ Skipping {files_exist} complete files")
    if files_incomplete > 0:
        print(f"⚠ Recreating {files_incomplete} incomplete/corrupt files")
    
    if not files_to_create:
        print(f"✓ All files already exist for {year}")
        return True
    
    print(f"→ Processing {len(files_to_create)} new files")
    
    # Profile for output files
    profile = {
        'driver': 'GTiff',
        'dtype': ref_meta['dtype'],
        'width': ref_meta['width'],
        'height': ref_meta['height'],
        'count': len(VARIABLES),
        'crs': ref_meta['crs'],
        'transform': ref_meta['transform'],
        'nodata': ref_meta['nodata'],
        'compress': 'lzw',
        'tiled': True,
        'blockxsize': 256,
        'blockysize': 256
    }
    
    # OPTIMIZED: Open all variable files once, process day-by-day
    print(f"→ Opening all {len(VARIABLES)} variable files...")
    datasets = {}
    all_data = {}
    
    try:
        # Open all files and read data once
        for var_idx, var in enumerate(VARIABLES, 1):
            filepath = f"{INPUT_DIR}ERA5_{var}_{year}.tif"
            print(f"  [{var_idx}/{len(VARIABLES)}] Loading {var}...")
            
            with rasterio.open(filepath) as src:
                # Verify band count
                if src.count != num_days:
                    print(f"    ✗ Band count mismatch: {src.count} vs {num_days}")
                    raise ValueError(f"Band mismatch: {var}")
                
                # Read all bands at once
                data = src.read()  # Shape: (num_days, height, width)
                
                # DATA QUALITY CHECK: Validate array shape
                if data.shape != (num_days, ref_meta['height'], ref_meta['width']):
                    print(f"    ✗ Shape error: {data.shape} vs ({num_days}, {ref_meta['height']}, {ref_meta['width']})")
                    raise ValueError(f"Shape mismatch: {var}")
                
                all_data[var] = data
        
        print(f"✓ All data loaded into memory")
        
        # Process each day (write all variables at once)
        print(f"→ Writing {len(files_to_create)} daily files...")
        for day_idx in range(num_days):
            output_file = output_files[day_idx]
            
            # Skip existing complete files
            if output_file not in files_to_create:
                continue
            
            temp_file = output_file + ".tmp"
            
            try:
                # Collect all variable data for this day
                daily_bands = np.stack([all_data[var][day_idx] for var in VARIABLES], axis=0)
                
                # Write multi-band file atomically
                with rasterio.open(temp_file, 'w', **profile) as dst:
                    for band_idx in range(len(VARIABLES)):
                        dst.write(daily_bands[band_idx], band_idx + 1)
                
                # Rename to final name (atomic operation)
                os.rename(temp_file, output_file)
                
                # Progress indicator every 30 days
                if (day_idx + 1) % 30 == 0:
                    print(f"  Progress: {day_idx + 1}/{num_days} days written")
                
            except Exception as e:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                raise e
        
        print(f"✓ All daily files written")
        
    except Exception as e:
        print(f"✗ Error during processing: {e}")
        # Clean up any incomplete files
        for output_file in files_to_create:
            if os.path.exists(output_file):
                try:
                    os.remove(output_file)
                except:
                    pass
        return False
    
    # STEP 4: FINAL VALIDATION - Verify all output files are complete and correct
    print("\n→ Final validation...")
    invalid = []
    for output_file in files_to_create:
        try:
            with rasterio.open(output_file) as dst:
                if dst.count != len(VARIABLES):
                    invalid.append((output_file, f"{dst.count}/{len(VARIABLES)} bands"))
                elif (dst.width, dst.height) != (ref_meta['width'], ref_meta['height']):
                    invalid.append((output_file, "wrong dimensions"))
                elif dst.crs != ref_meta['crs']:
                    invalid.append((output_file, "wrong CRS"))
        except Exception as e:
            invalid.append((output_file, f"read error: {str(e)[:40]}"))
    
    if invalid:
        print(f"✗ VALIDATION FAILED - {len(invalid)} files invalid:")
        for f, reason in invalid[:5]:
            print(f"    {os.path.basename(f)}: {reason}")
        if len(invalid) > 5:
            print(f"    ... +{len(invalid)-5} more")
        # Clean up all invalid files
        for f, _ in invalid:
            try: os.remove(f)
            except: pass
        return False
    
    print(f"✓ Year {year} COMPLETE & VALIDATED: {len(files_to_create)} files")
    return True

def main():
    """Main execution function."""
    print("="*70)
    print("ERA5-Land Daily Data Unpacking Script")
    print("="*70)
    print(f"Input Directory:  {INPUT_DIR}")
    print(f"Output Directory: {OUTPUT_DIR}")
    print(f"Year Range:       {START_YEAR} - {END_YEAR}")
    print(f"Variables:        {len(VARIABLES)}")
    print("="*70)
    
    # Create output directory
    create_output_directory()
    
    # Process each year
    total_years = END_YEAR - START_YEAR + 1
    successful_years = 0
    
    for year in range(START_YEAR, END_YEAR + 1):
        if unpack_year(year):
            successful_years += 1
    
    # Final summary
    print("\n" + "="*70)
    print("UNPACKING COMPLETE")
    print("="*70)
    print(f"Years processed:  {successful_years}/{total_years}")
    print(f"Output location:  {OUTPUT_DIR}")
    print("="*70)
    
    # Calculate expected output files
    total_days = 0
    for year in range(START_YEAR, END_YEAR + 1):
        total_days += 366 if is_leap_year(year) else 365
    
    print(f"\nExpected daily files: {total_days}")
    print(f"Each file contains {len(VARIABLES)} bands (one per variable)")
    print("\nVariable order in each daily file:")
    for idx, var in enumerate(VARIABLES, 1):
        print(f"  Band {idx}: {var}")

if __name__ == "__main__":
    main()
