"""
Unpack MODIS ET sharded files directly to 8-day period files (skip yearly merge step).

Input: ET_Indonesia_YYYY-*.tif shard files (60 shards per year, each with 46 bands)
Output: ET_YYYY-MM-DD.tif files (individual 8-day period files)

This script processes shards directly, avoiding the memory-intensive merge step.
Each shard contains the same 46 8-day periods, just different spatial tiles.
We merge spatially for each 8-day period separately.
"""

import os
from pathlib import Path
import rasterio
from rasterio.merge import merge
from datetime import datetime, timedelta
from tqdm import tqdm

# Configuration - UPDATE THESE PATHS
INPUT_DIR = r"Q:\My Drive\Indonesia_MODIS_ET_Years_Raw"  # Where your ET_Indonesia_YYYY-*.tif shard files are
OUTPUT_DIR = r"C:\Users\rcavalh\Documents\Camcore25\DB_Indonesia\Indonesia_MODIS_ET_8day"  # Where ET_YYYY-MM-DD.tif files will be saved
START_YEAR = 2000
END_YEAR = 2024

def is_leap_year(year):
    """Check if a year is a leap year."""
    return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)

def get_8day_dates_for_year(year):
    """Generate dates for 8-day MODIS composites."""
    dates = []
    start_date = datetime(year, 1, 1)
    day_of_year = 1
    
    while day_of_year <= 365 + (1 if is_leap_year(year) else 0):
        current_date = start_date + timedelta(days=day_of_year - 1)
        dates.append(current_date)
        day_of_year += 8
    
    return dates

def get_shards_for_year(input_dir, year):
    """Get all shard files for a specific year."""
    pattern = f"ET_Indonesia_{year}-*.tif"
    shards = sorted(Path(input_dir).glob(pattern))
    return shards

def extract_8day_from_shards(shards, band_idx, output_file):
    """
    Extract a single 8-day period (band) from all shards and merge spatially.
    Process shards in batches to reduce memory usage.
    
    Args:
        shards: List of shard file paths
        band_idx: Band index to extract (1-46)
        output_file: Output file path
    """
    BATCH_SIZE = 5  # Process 5 shards at a time (safer for 64GB RAM)
    
    try:
        # Process shards in batches
        temp_files = []
        
        for i in range(0, len(shards), BATCH_SIZE):
            batch = shards[i:i+BATCH_SIZE]
            
            # Open batch
            src_files = [rasterio.open(str(shard)) for shard in batch]
            
            # Merge this batch
            mosaic, out_trans = merge(src_files, indexes=band_idx)
            
            # Get metadata
            out_meta = src_files[0].meta.copy()
            out_meta.update({
                "driver": "GTiff",
                "height": mosaic.shape[1],
                "width": mosaic.shape[2],
                "count": 1,
                "transform": out_trans,
                "compress": "lzw",
                "tiled": True
            })
            
            # Save temporary batch file
            temp_file = f"{output_file}.batch{i}.tmp"
            with rasterio.open(temp_file, "w", **out_meta) as dest:
                dest.write(mosaic[0], 1)
            
            temp_files.append(temp_file)
            
            # Close batch files
            for src in src_files:
                src.close()
        
        # Now merge all temp files together
        if len(temp_files) == 1:
            # Only one batch, just rename it
            os.rename(temp_files[0], output_file)
        else:
            # Merge temp files
            temp_src = [rasterio.open(f) for f in temp_files]
            final_mosaic, final_trans = merge(temp_src)
            
            final_meta = temp_src[0].meta.copy()
            final_meta.update({
                "height": final_mosaic.shape[1],
                "width": final_mosaic.shape[2],
                "transform": final_trans,
                "blockxsize": 256,
                "blockysize": 256
            })
            
            with rasterio.open(output_file, "w", **final_meta) as dest:
                dest.write(final_mosaic[0], 1)
            
            # Close and delete temp files
            for src in temp_src:
                src.close()
            for temp_file in temp_files:
                os.remove(temp_file)
        
        return True
        
    except Exception as e:
        print(f"      ✗ Error: {str(e)}")
        # Clean up temp files
        try:
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
        except:
            pass
        return False

def process_year(year):
    """Process all 8-day periods for a given year."""
    print(f"\n{'='*70}")
    print(f"Processing Year: {year}")
    print(f"{'='*70}")
    
    # Get all shards for this year
    shards = get_shards_for_year(INPUT_DIR, year)
    
    if not shards:
        print(f"✗ No shards found for year {year}")
        return 0
    
    print(f"Found {len(shards)} shards")
    
    # Check band count
    with rasterio.open(shards[0]) as src:
        num_bands = src.count
    
    print(f"Bands per shard: {num_bands}")
    
    # Get 8-day dates for this year
    dates = get_8day_dates_for_year(year)
    
    if num_bands != len(dates):
        print(f"⚠ Warning: Expected {len(dates)} bands, got {num_bands}")
        dates = dates[:num_bands]  # Adjust if needed
    
    successful = 0
    skipped = 0
    
    # Process each 8-day period (band)
    for band_idx in tqdm(range(1, num_bands + 1), desc=f"Year {year}"):
        date = dates[band_idx - 1]
        date_str = date.strftime("%Y-%m-%d")
        
        output_file = os.path.join(OUTPUT_DIR, f"ET_{date_str}.tif")
        
        # Skip if already exists
        if os.path.exists(output_file):
            skipped += 1
            continue
        
        # Extract and merge this 8-day period from all shards
        success = extract_8day_from_shards(shards, band_idx, output_file)
        
        if success:
            successful += 1
        else:
            print(f"      Failed: {date_str}")
    
    print(f"✓ Year {year}: {successful} files created, {skipped} skipped")
    return successful

def main():
    print("="*70)
    print("MODIS ET Direct Shard-to-8day Unpacking")
    print("="*70)
    print(f"Input Directory:  {INPUT_DIR}")
    print(f"Output Directory: {OUTPUT_DIR}")
    print(f"Year Range:       {START_YEAR} - {END_YEAR}")
    print("="*70)
    print()
    print("Processing each 8-day period separately to minimize memory usage")
    print("This avoids the need to merge entire yearly files first")
    print()
    
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    total_files = 0
    
    for year in range(START_YEAR, END_YEAR + 1):
        files_created = process_year(year)
        total_files += files_created
    
    print(f"\n{'='*70}")
    print("UNPACKING COMPLETE")
    print(f"{'='*70}")
    print(f"Total 8-day files created: {total_files}")
    print(f"Output location: {OUTPUT_DIR}")
    print(f"{'='*70}")
    print()
    print("Next step: Run resampling script on the 8-day files")
    print(f"{'='*70}")

if __name__ == "__main__":
    main()
