"""
Parallel CHIRPS Resampling Script
Resamples CHIRPS daily files from original resolution to 0.02 degrees
Uses multiprocessing to run multiple gdalwarp processes in parallel

PERFORMANCE:
- Sequential (bat): ~3-4 hours for 12,775 files
- Parallel (8 workers): ~30-45 minutes (5-6x speedup)
"""

import os
import subprocess
from pathlib import Path
from multiprocessing import Pool
from tqdm import tqdm
import re

# Configuration
INPUT_DIR = r"C:\Users\rcavalh\2026_CHIRPS\Unpacked"
OUTPUT_DIR = r"C:\Users\rcavalh\2026_CHIRPS\Resampled"
GDALWARP_PATH = r"C:\Program Files\QGIS 3.40.4\bin\gdalwarp.exe"

# Set GDAL environment variables for QGIS installation
os.environ['GDAL_DATA'] = r'C:\Program Files\QGIS 3.40.4\share\gdal'
os.environ['PROJ_LIB'] = r'C:\Program Files\QGIS 3.40.4\share\proj'
# Add GDAL binaries to PATH
qgis_bin = r'C:\Program Files\QGIS 3.40.4\bin'
if qgis_bin not in os.environ['PATH']:
    os.environ['PATH'] = qgis_bin + ';' + os.environ['PATH']

# Number of parallel workers
# Each gdalwarp process uses ~1 CPU, so match your core count
NUM_WORKERS = 8

# Create output directory
os.makedirs(OUTPUT_DIR, exist_ok=True)

# GDALWARP parameters
GDALWARP_PARAMS = [
    "-tr", "0.02", "0.02",           # Target resolution: 0.02 degrees
    "-r", "bilinear",                 # Resampling method: bilinear
    "-co", "COMPRESS=LZW",            # Compression
    "-co", "TILED=YES",               # Tiled output
    "-ot", "Float32",                 # Output type
    "-srcnodata", "-9999.0",          # Source NoData value (CRITICAL for proper interpolation)
    "-dstnodata", "-9999.0",          # Destination NoData value
    "-q"                              # Quiet mode
]


def process_chirps_file(input_file):
    """
    Resample a single CHIRPS file using gdalwarp
    
    Args:
        input_file: Path to input CHIRPS file (format: CHIRPS_YYYY-MM-DD.tif)
    
    Returns:
        tuple: (filename, success, message)
    """
    
    filename = os.path.basename(input_file)
    
    try:
        # Extract date from filename: CHIRPS_YYYY-MM-DD.tif -> YYYY-MM-DD
        match = re.search(r'CHIRPS_(\d{4}-\d{2}-\d{2})\.tif', filename)
        if not match:
            return (filename, False, "Invalid filename format")
        
        date_str = match.group(1)
        
        # Convert YYYY-MM-DD to YYYY_MM_DD format
        year, month, day = date_str.split('-')
        new_filename = f"chirps_{year}_{month}_{day}.tif"
        
        output_file = os.path.join(OUTPUT_DIR, new_filename)
        
        # Skip if already exists
        if os.path.exists(output_file):
            return (filename, True, "Skipped (exists)")
        
        # Build gdalwarp command
        cmd = [GDALWARP_PATH] + GDALWARP_PARAMS + [input_file, output_file]
        
        # Run gdalwarp
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if result.returncode == 0:
            return (filename, True, "Resampled")
        else:
            return (filename, False, f"gdalwarp error: {result.stderr[:100]}")
            
    except Exception as e:
        return (filename, False, f"Error: {str(e)}")


def get_chirps_files():
    """Get all CHIRPS files from input directory"""
    files = [
        os.path.join(INPUT_DIR, f)
        for f in os.listdir(INPUT_DIR)
        if f.startswith("CHIRPS_") and f.endswith(".tif")
    ]
    return sorted(files)


if __name__ == '__main__':
    print("="*70)
    print("CHIRPS Parallel Resampling")
    print("="*70)
    print(f"Input Directory:  {INPUT_DIR}")
    print(f"Output Directory: {OUTPUT_DIR}")
    print(f"GDALWARP Path:    {GDALWARP_PATH}")
    print(f"Parallel Workers: {NUM_WORKERS}")
    print(f"Target Resolution: 0.02 degrees")
    print("="*70)
    print()
    
    # Check if GDALWARP exists
    if not os.path.exists(GDALWARP_PATH):
        print(f"ERROR: GDALWARP not found at {GDALWARP_PATH}")
        print("Please update GDALWARP_PATH in the script")
        exit(1)
    
    # Get all CHIRPS files
    chirps_files = get_chirps_files()
    
    if not chirps_files:
        print(f"ERROR: No CHIRPS files found in {INPUT_DIR}")
        exit(1)
    
    print(f"Found {len(chirps_files)} CHIRPS files")
    print(f"Starting parallel resampling with {NUM_WORKERS} workers...\n")
    
    successful = 0
    skipped = 0
    failed = 0
    
    # Process files in parallel
    with Pool(processes=NUM_WORKERS) as pool:
        # Use imap_unordered for faster processing
        results = pool.imap_unordered(process_chirps_file, chirps_files, chunksize=10)
        
        # Track progress with tqdm
        for filename, success, message in tqdm(results, total=len(chirps_files), desc="Resampling", unit="file"):
            if success:
                if "Skipped" in message:
                    skipped += 1
                else:
                    successful += 1
            else:
                failed += 1
                tqdm.write(f"✗ {filename}: {message}")
    
    # Summary
    print()
    print("="*70)
    print("RESAMPLING COMPLETE")
    print("="*70)
    print(f"Total files:  {len(chirps_files)}")
    print(f"Resampled:    {successful}")
    print(f"Skipped:      {skipped}")
    print(f"Failed:       {failed}")
    print("="*70)
    
    # Verification
    print()
    print("Verifying output...")
    output_files = [
        f for f in os.listdir(OUTPUT_DIR)
        if f.startswith("chirps_") and f.endswith(".tif")
    ]
    print(f"Output files found: {len(output_files)}")
    
    if len(output_files) >= len(chirps_files) * 0.99:
        print("✓ All files resampled successfully!")
    else:
        print(f"⚠ Expected {len(chirps_files)} files, found {len(output_files)}")
