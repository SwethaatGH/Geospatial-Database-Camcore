"""
Unpack MODIS ET yearly files (46 8-day bands per year) into individual 8-day period files.

Input: ET_Indonesia_{year}.tif files with ~46 bands (8-day composites)
Output: ET_YYYY-MM-DD.tif files (individual 8-day period files)

MODIS MOD16A2GF produces 8-day composites, resulting in ~46 images per year.
Each band represents an 8-day period starting from January 1st.
"""

import os
from pathlib import Path
import rasterio
from datetime import datetime, timedelta

# Configuration - UPDATE THESE PATHS FOR LOCAL EXECUTION
INPUT_DIR = r"C:\Path\To\Indonesia_MODIS_ET_Years"  # Where your ET_Indonesia_{year}.tif files are
OUTPUT_DIR = r"C:\Path\To\Indonesia_MODIS_ET_8day"  # Where ET_YYYY-MM-DD.tif files will be saved
START_YEAR = 2000
END_YEAR = 2024

def get_8day_dates_for_year(year):
    """
    Generate dates for 8-day MODIS composites.
    MODIS uses 8-day periods starting Jan 1, with the last period being shorter in some years.
    """
    dates = []
    start_date = datetime(year, 1, 1)
    day_of_year = 1
    
    while day_of_year <= 365 + (1 if is_leap_year(year) else 0):
        current_date = start_date + timedelta(days=day_of_year - 1)
        dates.append(current_date)
        day_of_year += 8
    
    return dates

def is_leap_year(year):
    """Check if a year is a leap year."""
    return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)

def create_output_directory():
    """Create output directory if it doesn't exist."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Output directory: {OUTPUT_DIR}")

def unpack_year(year):
    """Unpack all 8-day periods for a given year into individual files."""
    print(f"\n{'='*60}")
    print(f"Processing Year: {year}")
    print(f"{'='*60}")
    
    input_file = f"{INPUT_DIR}ET_Indonesia_{year}.tif"
    
    # Check if input file exists
    if not os.path.exists(input_file):
        print(f"✗ File not found: {input_file}")
        return False
    
    try:
        with rasterio.open(input_file) as src:
            num_bands = src.count
            print(f"Bands in file: {num_bands}")
            
            # Get 8-day period dates
            dates = get_8day_dates_for_year(year)
            expected_periods = len(dates)
            
            if num_bands != expected_periods:
                print(f"⚠ Warning: Expected {expected_periods} bands, got {num_bands}")
            
            # Get metadata for output files
            profile = src.profile.copy()
            profile.update({
                'count': 1,  # Single band per output file
                'compress': 'lzw',
                'tiled': True,
                'blockxsize': 256,
                'blockysize': 256
            })
            
            successful = 0
            skipped = 0
            
            # Process each band (8-day period)
            for band_idx in range(1, num_bands + 1):
                # Get date for this period
                if band_idx - 1 < len(dates):
                    date = dates[band_idx - 1]
                    date_str = date.strftime("%Y-%m-%d")
                else:
                    # Fallback for extra bands
                    print(f"⚠ Band {band_idx} exceeds expected periods, using approximate date")
                    date = dates[-1] + timedelta(days=8 * (band_idx - len(dates)))
                    date_str = date.strftime("%Y-%m-%d")
                
                output_file = f"{OUTPUT_DIR}ET_{date_str}.tif"
                
                # Skip if already exists
                if os.path.exists(output_file):
                    skipped += 1
                    continue
                
                # Read band data
                data = src.read(band_idx)
                
                # Write to individual file
                temp_file = output_file + ".tmp"
                try:
                    with rasterio.open(temp_file, 'w', **profile) as dst:
                        dst.write(data, 1)
                    
                    # Rename to final name
                    os.rename(temp_file, output_file)
                    successful += 1
                    
                    # Progress indicator
                    if band_idx % 10 == 0:
                        print(f"  [{band_idx}/{num_bands}] ✓ {date_str}")
                
                except Exception as e:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                    raise e
            
            print(f"\nYear {year} Summary:")
            print(f"  ✓ Created: {successful} files")
            print(f"  ⊙ Skipped: {skipped} existing files")
            
            return True
            
    except Exception as e:
        print(f"✗ Error processing {year}: {e}")
        return False

def main():
    """Main execution function."""
    print("="*70)
    print("MODIS ET 8-day Period Unpacking Script")
    print("="*70)
    print(f"Input Directory:  {INPUT_DIR}")
    print(f"Output Directory: {OUTPUT_DIR}")
    print(f"Year Range:       {START_YEAR} - {END_YEAR}")
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
    
    # Calculate expected files
    total_periods = 0
    for year in range(START_YEAR, END_YEAR + 1):
        total_periods += len(get_8day_dates_for_year(year))
    
    print(f"\nExpected output files: ~{total_periods} (8-day periods)")
    print("Output format: ET_YYYY-MM-DD.tif")
    print("\nNote: Each file represents an 8-day composite period")

if __name__ == "__main__":
    main()
