"""
Merge MODIS ET sharded files into single yearly files.

GEE exports large files as shards (pieces). This script merges them back together.
Input: ET_Indonesia_2000-0000000000-0000000000.tif, ET_Indonesia_2000-0000000000-0000006912.tif, etc.
Output: ET_Indonesia_2000.tif (single merged file per year)
"""

import os
from pathlib import Path
import numpy as np
import rasterio
from rasterio.merge import merge
from rasterio.transform import from_bounds

# Configuration - UPDATE THESE PATHS FOR LOCAL EXECUTION
INPUT_DIR = r"Q:\My Drive\Indonesia_MODIS_ET_Years_Raw"  # Where your ET_Indonesia_YYYY-*.tif shard files are
OUTPUT_DIR = r"C:\Users\rcavalh\Documents\Camcore25\DB_Indonesia\Indonesia_MODIS_ET_Years_Merged"  # Where merged files will be saved
START_YEAR = 2000
END_YEAR = 2024

def get_shards_for_year(input_dir, year):
    """Get all shard files for a specific year, sorted by shard number."""
    pattern = f"ET_Indonesia_{year}-*.tif"
    shards = sorted(Path(input_dir).glob(pattern))
    return shards

def merge_shards_rasterio(shards, output_file):
    """
    Merge shards using rasterio.merge with memory-efficient band-by-band processing.
    Works with GEE sharded exports by mosaicking spatial tiles.
    """
    print(f"    Opening {len(shards)} shards...")
    
    try:
        # Open all shards
        src_files = [rasterio.open(str(shard)) for shard in shards]
        
        # Get band count from first shard (all should have same bands)
        num_bands = src_files[0].count
        print(f"    Bands per shard: {num_bands}")
        print(f"    Processing band-by-band to reduce memory usage...")
        
        # Get output metadata by merging first band only to determine dimensions
        print(f"    Calculating output dimensions...")
        mosaic_first, out_trans = merge(src_files, indexes=1)
        
        # Get metadata from first shard
        out_meta = src_files[0].meta.copy()
        
        # Update metadata for merged output
        out_meta.update({
            "driver": "GTiff",
            "height": mosaic_first.shape[1],
            "width": mosaic_first.shape[2],
            "count": num_bands,
            "transform": out_trans,
            "compress": "lzw",
            "tiled": True,
            "bigtiff": "yes",
            "blockxsize": 512,
            "blockysize": 512
        })
        
        print(f"    Output size: {mosaic_first.shape[2]} x {mosaic_first.shape[1]} pixels, {num_bands} bands")
        print(f"    Writing merged file band-by-band...")
        
        # Create output file and write band by band
        with rasterio.open(output_file, "w", **out_meta) as dest:
            # Write first band (already computed)
            dest.write(mosaic_first[0], 1)
            print(f"      Band 1/{num_bands} complete")
            
            # Process remaining bands one at a time
            for band_idx in range(2, num_bands + 1):
                mosaic_band, _ = merge(src_files, indexes=band_idx)
                dest.write(mosaic_band[0], band_idx)
                print(f"      Band {band_idx}/{num_bands} complete")
        
        # Close all source files
        for src in src_files:
            src.close()
        
        return True
        
    except Exception as e:
        print(f"    ✗ Merge failed: {str(e)}")
        # Make sure to close files on error
        try:
            for src in src_files:
                src.close()
        except:
            pass
        return False

def main():
    print("=" * 70)
    print("MODIS ET Shard Merging Script")
    print("=" * 70)
    print(f"Input Directory:  {INPUT_DIR}")
    print(f"Output Directory: {OUTPUT_DIR}")
    print(f"Year Range:       {START_YEAR} - {END_YEAR}")
    print("=" * 70)
    
    # Create output directory
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Output directory: {OUTPUT_DIR}\n")
    
    years_processed = 0
    
    for year in range(START_YEAR, END_YEAR + 1):
        print("=" * 60)
        print(f"Processing Year: {year}")
        print("=" * 60)
        
        # Get all shards for this year
        shards = get_shards_for_year(INPUT_DIR, year)
        
        if not shards:
            print(f"✗ No shards found for year {year}")
            continue
        
        output_file = os.path.join(OUTPUT_DIR, f"ET_Indonesia_{year}.tif")
        
        # Skip if already merged
        if os.path.exists(output_file):
            print(f"✓ Already merged: {output_file}")
            years_processed += 1
            continue
        
        print(f"Found {len(shards)} shards")
        print(f"Output: {os.path.basename(output_file)}")
        
        # Merge shards
        success = merge_shards_rasterio(shards, output_file)
        
        if success:
            print(f"✓ Successfully merged {year}")
            years_processed += 1
        else:
            print(f"✗ Failed to merge {year}")
        
        print()
    
    print("=" * 70)
    print("SHARD MERGING COMPLETE")
    print("=" * 70)
    print(f"Years processed:  {years_processed}/{END_YEAR - START_YEAR + 1}")
    print(f"Output location:  {OUTPUT_DIR}")
    print("=" * 70)
    print("\nNext step: Run unpack_et_yearly_to_8day.py")
    print("Update INPUT_DIR to point to the merged files directory")

if __name__ == "__main__":
    main()
