"""
Unpack Yearly SPEI/MODIS Stacks to Monthly Files
Converts yearly multi-band GeoTIFFs to individual monthly files
Matches original repository structure for processing compatibility
"""

import os
import rasterio
from tqdm import tqdm
from datetime import datetime

def unpack_yearly_stack(input_file, output_dir, dataset_type='SPEI'):
    """
    Unpack a yearly multi-band GeoTIFF into individual monthly files
    
    Args:
        input_file: Path to yearly stack (e.g., SPEI_Indonesia_2020.tif)
        output_dir: Directory to save individual monthly files
        dataset_type: 'SPEI', 'MODIS', 'CHIRPS', or 'ERA5'
    """
    
    # Extract year from filename
    basename = os.path.basename(input_file)
    year = basename.split('_')[-1].replace('.tif', '')
    
    print(f"Processing {year}...")
    
    with rasterio.open(input_file) as src:
        num_bands = src.count
        print(f"  Found {num_bands} bands (months)")
        
        # Create year subdirectory
        year_dir = os.path.join(output_dir, year)
        os.makedirs(year_dir, exist_ok=True)
        
        # Extract each band as a separate file
        for band_idx in range(1, num_bands + 1):
            month = f"{band_idx:02d}"
            
            # Generate output filename based on dataset type
            if dataset_type == 'SPEI':
                # Original format: SPEI01_YYYY-MM.tif
                output_filename = f"SPEI01_{year}-{month}.tif"
            elif dataset_type == 'MODIS':
                # Original format: ET_YYYY-MM-dd.tif (use first day of month)
                output_filename = f"ET_{year}-{month}-01.tif"
            elif dataset_type == 'CHIRPS':
                # Original format: chirps_YYYY_MM.tif
                output_filename = f"chirps_{year}_{month}.tif"
            elif dataset_type == 'ERA5':
                # Original format: era5land_YYYY_MM.tif
                output_filename = f"era5land_{year}_{month}.tif"
            else:
                output_filename = f"{dataset_type}_{year}_{month}.tif"
            
            output_path = os.path.join(year_dir, output_filename)
            
            # Skip if already exists
            if os.path.exists(output_path):
                continue
            
            # Read band data
            data = src.read(band_idx)
            
            # Get metadata from source and update for single-band output
            meta = src.meta.copy()
            meta.update({
                'count': 1,
                'compress': 'lzw',
                'tiled': True
            })
            
            # Write single-band file
            with rasterio.open(output_path, 'w', **meta) as dst:
                dst.write(data, 1)
        
        print(f"  ✓ Created {num_bands} monthly files in {year_dir}")


def unpack_dataset(input_folder, output_folder, dataset_type='SPEI'):
    """
    Unpack all yearly stacks in a folder
    
    Args:
        input_folder: Folder containing yearly stacks
        output_folder: Folder to save unpacked monthly files
        dataset_type: 'SPEI', 'MODIS', 'CHIRPS', or 'ERA5'
    """
    
    print(f"{'='*70}")
    print(f"Unpacking {dataset_type} Yearly Stacks to Monthly Files")
    print(f"{'='*70}")
    print(f"Input folder: {input_folder}")
    print(f"Output folder: {output_folder}")
    print(f"{'='*70}\n")
    
    os.makedirs(output_folder, exist_ok=True)
    
    # Find all .tif files
    tif_files = [f for f in os.listdir(input_folder) if f.endswith('.tif')]
    
    if not tif_files:
        print("❌ No .tif files found in input folder")
        return
    
    print(f"Found {len(tif_files)} yearly files to unpack\n")
    
    # Process each yearly file
    for tif_file in tqdm(sorted(tif_files), desc="Unpacking years"):
        input_path = os.path.join(input_folder, tif_file)
        unpack_yearly_stack(input_path, output_folder, dataset_type)
    
    # Summary
    print(f"\n{'='*70}")
    print(f"UNPACKING COMPLETE")
    print(f"{'='*70}")
    
    # Count output files
    total_files = sum([len([f for f in files if f.endswith('.tif')]) 
                      for _, _, files in os.walk(output_folder)])
    
    print(f"✓ Total monthly files created: {total_files}")
    print(f"✓ Output directory: {output_folder}")
    print(f"\nYour existing processing scripts can now use these files!")
    print(f"{'='*70}")


# ============================================================================
# USAGE EXAMPLES - Run these after downloading from GEE
# ============================================================================

if __name__ == "__main__":
    
    # Example 1: Unpack SPEI data
    unpack_dataset(
        input_folder="/content/drive/MyDrive/Indonesia_SPEI_Years/",
        output_folder="/content/drive/MyDrive/Indonesia_SPEI_Monthly/",
        dataset_type='SPEI'
    )
    
    # Example 2: Unpack MODIS ET data
    # unpack_dataset(
    #     input_folder="/content/drive/MyDrive/Indonesia_MODIS_ET_Years/",
    #     output_folder="/content/drive/MyDrive/Indonesia_MODIS_Monthly/",
    #     dataset_type='MODIS'
    # )
    
    # Example 3: Unpack CHIRPS data
    # unpack_dataset(
    #     input_folder="/content/drive/MyDrive/Indonesia_CHIRPS_Years/",
    #     output_folder="/content/drive/MyDrive/Indonesia_CHIRPS_Monthly/",
    #     dataset_type='CHIRPS'
    # )
    
    # Example 4: Unpack ERA5-Land data
    # unpack_dataset(
    #     input_folder="/content/drive/MyDrive/Indonesia_ERA5_Years/",
    #     output_folder="/content/drive/MyDrive/Indonesia_ERA5_Monthly/",
    #     dataset_type='ERA5'
    # )
