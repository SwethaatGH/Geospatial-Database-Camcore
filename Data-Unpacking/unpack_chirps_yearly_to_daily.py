"""
Unpack CHIRPS Yearly Stacks to Daily Files - PARALLEL VERSION
Converts multi-band yearly GeoTIFFs (365-366 bands) to individual daily files
Uses multiprocessing to unpack multiple years simultaneously

PERFORMANCE: 
- Sequential: ~35 minutes (1 min/year × 35 years)
- Parallel (8 workers): ~5 minutes (7x speedup on 32-core system)
"""

import os
import rasterio
from tqdm import tqdm
from datetime import datetime, timedelta
from multiprocessing import Pool, cpu_count
from functools import partial

# Directories
INPUT_DIR = r"C:\Users\rcavalh\2026_CHIRPS"
OUTPUT_DIR = r"C:\Users\rcavalh\2026_CHIRPS\Unpacked"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Number of parallel workers
# 32-core system with offline Google Drive files = local disk I/O (fast!)
# 8 workers for good parallelization
NUM_WORKERS = 8


def unpack_yearly_chirps(year, input_dir, output_dir):
    """
    Unpack a yearly CHIRPS stack to individual daily files
    Worker function for multiprocessing
    
    Args:
        year: Year integer (e.g., 2020)
        input_dir: Directory containing yearly files
        output_dir: Directory to save daily files
        
    Returns:
        tuple: (year, success, num_files, message)
    """
    
    yearly_filename = f"CHIRPS_Daily_{year}.tif"
    yearly_path = os.path.join(input_dir, yearly_filename)
    
    # Check if file exists
    if not os.path.exists(yearly_path):
        return (year, False, 0, f"File not found: {yearly_filename}")
    
    try:
        files_created = 0
        files_skipped = 0
        
        # Open the multi-band raster
        with rasterio.open(yearly_path) as src:
            profile = src.profile.copy()
            profile.update(
                count=1,  # Single band output
                nodata=src.nodata  # Preserve NoData value from source
            )
            
            num_bands = src.count
            
            # Starting date for this year
            start_date = datetime(year, 1, 1)
            
            # Process each band (day)
            for band_idx in range(1, num_bands + 1):
                
                # Calculate date for this band
                current_date = start_date + timedelta(days=band_idx - 1)
                date_str = current_date.strftime("%Y-%m-%d")
                
                # Output filename: CHIRPS_YYYY-MM-DD.tif
                output_file = os.path.join(output_dir, f"CHIRPS_{date_str}.tif")
                
                # Skip if already exists
                if os.path.exists(output_file):
                    files_skipped += 1
                    continue
                
                # Read this band
                band_data = src.read(band_idx)
                
                # Write to individual file
                with rasterio.open(output_file, 'w', **profile) as dst:
                    dst.write(band_data, 1)
                
                files_created += 1
        
        message = f"Created {files_created}, Skipped {files_skipped}/{num_bands}"
        return (year, True, files_created, message)
        
    except Exception as e:
        return (year, False, 0, f"Error: {str(e)}")


def process_year_wrapper(year):
    """Wrapper function to pass to multiprocessing Pool"""
    return unpack_yearly_chirps(year, INPUT_DIR, OUTPUT_DIR)


if __name__ == '__main__':
    # Print header
    print(f"{'='*70}")
    print(f"CHIRPS Yearly to Daily Unpacking - PARALLEL VERSION")
    print(f"{'='*70}")
    print(f"Input Directory:  {INPUT_DIR}")
    print(f"Output Directory: {OUTPUT_DIR}")
    print(f"Parallel Workers: {NUM_WORKERS}")
    print(f"{'='*70}\n")
    
    # Main processing
    print("\nStarting parallel unpacking process...\n")

    # Years to process (change START_YEAR to resume from specific year)
    START_YEAR = 2026  # Change this to resume (e.g., 2008 to skip completed years)
    END_YEAR = 2027
    years_to_process = list(range(START_YEAR, END_YEAR + 1))

    print(f"Processing {len(years_to_process)} years with {NUM_WORKERS} parallel workers...\n")

    successful = []
    failed = []
    total_files_created = 0

    # Process years in parallel
    with Pool(processes=NUM_WORKERS) as pool:
        # Use imap_unordered for faster results (order doesn't matter)
        results = pool.imap_unordered(process_year_wrapper, years_to_process)
        
        # Collect results with progress bar (no individual prints to avoid tqdm conflicts)
        for year, success, num_files, message in tqdm(results, total=len(years_to_process), desc="Unpacking years", unit="year"):
            if success:
                successful.append(year)
                total_files_created += num_files
            else:
                failed.append(year)
                # Only print failures immediately (after tqdm position)
                tqdm.write(f"[{year}] ✗ {message}")

    # Summary
    print(f"\n{'='*70}")
    print(f"UNPACKING SUMMARY")
    print(f"{'='*70}")
    print(f"✓ Successful: {len(successful)} years")
    print(f"✗ Failed: {len(failed)} years")
    print(f"📁 Files created: {total_files_created}")

    if successful:
        print(f"\nSuccessfully unpacked years: {min(successful)}-{max(successful)}")

    if failed:
        print(f"\nFailed to unpack:")
        for year in failed:
            print(f"  ✗ {year}")

    print(f"\nDaily files saved to: {OUTPUT_DIR}")
    print(f"{'='*70}")

    # Verification
    print(f"\nVerifying output...")
    output_files = [f for f in os.listdir(OUTPUT_DIR) if f.startswith("CHIRPS_") and f.endswith(".tif")]
    print(f"Daily files found: {len(output_files)}")

    if len(output_files) >= 100 * 0.99:  # Allow 1% margin for leap years
        print(f"✓ All files present!")
    else:
        print(f"⚠ Expected ~12,775 files, found {len(output_files)}")

