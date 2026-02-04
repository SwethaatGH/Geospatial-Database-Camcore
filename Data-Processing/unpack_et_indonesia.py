"""
Unpack MODIS ET yearly files (46 8-day bands per year) into individual 8-day period files.

Input: ET_Indonesia_{year}.tif files with ~46 bands (8-day composites)
Output: et_YYYY-MM-DD.tif files (individual 8-day period files)

MODIS MOD16A2GF produces 8-day composites, resulting in ~46 images per year.
Each band represents an 8-day period starting from January 1st.
"""

import os
from pathlib import Path
import rasterio
from datetime import datetime, timedelta
from tqdm import tqdm

# Configuration
INPUT_DIR = Path(r"Q:\My Drive\Indonesia_MODIS_ET_Years_Raw")
OUTPUT_DIR = Path(r"Q:\My Drive\Indonesia_MODIS_ET_8day")
START_YEAR = 2000
END_YEAR = 2024

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

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

def unpack_year(year):
    """Unpack all 8-day periods for a given year into individual files."""
    print(f"\nProcessing Year: {year}")
    
    # Try different possible filenames
    possible_names = [
        INPUT_DIR / f"ET_Indonesia_{year}.tif",
        INPUT_DIR / f"MODIS_ET_Indonesia_{year}.tif",
        INPUT_DIR / f"Indonesia_ET_{year}.tif"
    ]
    
    input_file = None
    for path in possible_names:
        if path.exists():
            input_file = path
            break
    
    if not input_file:
        print(f"  ✗ File not found for year {year}")
        return 0
    
    try:
        with rasterio.open(input_file) as src:
            num_bands = src.count
            print(f"  Found {num_bands} bands")
            
            # Get 8-day period dates
            dates = get_8day_dates_for_year(year)
            expected_periods = len(dates)
            
            if num_bands != expected_periods:
                print(f"  ⚠ Warning: Expected {expected_periods} bands, got {num_bands}")
            
            # Get metadata for output files
            profile = src.profile.copy()
            profile.update({
                'count': 1,  # Single band per output file
                'compress': 'lzw',
                'tiled': True
            })
            
            successful = 0
            skipped = 0
            
            # Process each band (8-day period)
            for band_idx in range(1, num_bands + 1):
                # Get date for this period
                if band_idx - 1 < len(dates):
                    date = dates[band_idx - 1]
                else:
                    # Fallback for extra bands
                    date = dates[-1] + timedelta(days=8 * (band_idx - len(dates)))
                
                date_str = date.strftime("%Y-%m-%d")
                output_file = OUTPUT_DIR / f"et_{date_str}.tif"
                
                # Skip if already exists
                if output_file.exists():
                    skipped += 1
                    continue
                
                # Read band data
                data = src.read(band_idx)
                
                # Write to individual file
                with rasterio.open(output_file, 'w', **profile) as dst:
                    dst.write(data, 1)
                
                successful += 1
            
            print(f"  ✓ Created: {successful} files, Skipped: {skipped} existing")
            return successful
            
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return 0

def main():
    """Main execution function."""
    print("="*70)
    print("MODIS ET 8-day Period Unpacking for Indonesia")
    print("="*70)
    print(f"Input:  {INPUT_DIR}")
    print(f"Output: {OUTPUT_DIR}")
    print(f"Years:  {START_YEAR} - {END_YEAR}")
    print("="*70 + "\n")
    
    # Process each year
    total_created = 0
    successful_years = 0
    
    for year in tqdm(range(START_YEAR, END_YEAR + 1), desc="Unpacking years"):
        created = unpack_year(year)
        if created > 0:
            successful_years += 1
            total_created += created
    
    # Final summary
    print("\n" + "="*70)
    print("UNPACKING COMPLETE")
    print("="*70)
    print(f"Years processed:  {successful_years}/{END_YEAR - START_YEAR + 1}")
    print(f"Total files created: {total_created}")
    print(f"Output location:  {OUTPUT_DIR}")
    
    # Calculate expected files
    total_periods = sum(len(get_8day_dates_for_year(year)) for year in range(START_YEAR, END_YEAR + 1))
    print(f"\nExpected files: ~{total_periods} (8-day periods from {START_YEAR}-{END_YEAR})")
    print("Output format: et_YYYY-MM-DD.tif")
    print("="*70)

if __name__ == "__main__":
    main()
