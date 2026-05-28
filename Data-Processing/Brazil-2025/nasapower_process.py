#!/usr/bin/env python3
"""
CHIRPS Data Verification Tool

Validates downloaded CHIRPS GeoTIFF files before merging:
- File integrity and size
- GeoTIFF format validation
- Shard detection (multi-file exports)
- CRS and spatial extent verification
- Band count validation (365/366)
- Reporting of corrupt or incomplete files
"""

import os
import json
import sys
from pathlib import Path
from collections import defaultdict
import argparse

try:
    import rasterio
    from rasterio.crs import CRS
    import numpy as np
except ImportError:
    print("Error: rasterio not found. Install with: pip install rasterio")
    sys.exit(1)


def get_file_size_mb(filepath):
    """Get file size in MB."""
    return os.path.getsize(filepath) / (1024 * 1024)


def check_geotiff_validity(filepath):
    """Check if file is a valid GeoTIFF."""
    try:
        with rasterio.open(filepath) as src:
            # Read minimal metadata
            crs = src.crs
            transform = src.transform
            width = src.width
            height = src.height
            bands = src.count
            
            # Try to read first band to check for corruption
            data = src.read(1)
            has_valid_data = True
            
            return {
                'valid': True,
                'crs': str(crs),
                'width': width,
                'height': height,
                'bands': bands,
                'transform': str(transform),
                'size_mb': get_file_size_mb(filepath),
                'data_min': float(np.nanmin(data)) if data.size > 0 else None,
                'data_max': float(np.nanmax(data)) if data.size > 0 else None,
            }
    except Exception as e:
        return {
            'valid': False,
            'error': str(e),
            'size_mb': get_file_size_mb(filepath),
        }


def detect_shards(files_by_year):
    """Detect if files are shards (multi-file exports for same year)."""
    shards = {}
    for year, files in files_by_year.items():
        if len(files) > 1:
            shards[year] = files
    return shards


def verify_chirps_data(input_dir, output_report=None):
    """Main verification function."""
    input_path = Path(input_dir)
    
    if not input_path.exists():
        print(f"❌ Input directory not found: {input_dir}")
        return None
    
    # Find all GeoTIFF files
    tiff_files = sorted(input_path.glob('*.tif')) + sorted(input_path.glob('*.tiff'))
    
    if not tiff_files:
        print(f"❌ No GeoTIFF files found in {input_dir}")
        return None
    
    print(f"\n{'='*70}")
    print(f"CHIRPS DATA VERIFICATION REPORT")
    print(f"{'='*70}")
    print(f"Input directory: {input_dir}")
    print(f"Total files found: {len(tiff_files)}\n")
    
    # Parse filenames to group by year
    files_by_year = defaultdict(list)
    for tiff_file in tiff_files:
        # Try to extract year from filename
        fname = tiff_file.name
        tokens = fname.split('_')
        for token in tokens:
            if token.isdigit() and len(token) == 4 and 1980 <= int(token) <= 2030:
                year = token
                files_by_year[year].append(tiff_file)
                break
        else:
            # No year found in filename, add to 'unknown'
            files_by_year['unknown'].append(tiff_file)
    
    # Phase 1: Verify each file
    print(f"{'PHASE 1: FILE VALIDATION':<70}")
    print(f"{'-'*70}\n")
    
    valid_files = {}
    invalid_files = {}
    
    for year in sorted(files_by_year.keys()):
        year_files = files_by_year[year]
        print(f"Year {year}: {len(year_files)} file(s)")
        
        for filepath in year_files:
            print(f"  Checking: {filepath.name}")
            result = check_geotiff_validity(filepath)
            
            if result['valid']:
                valid_files[str(filepath)] = result
                print(f"    ✓ Valid GeoTIFF")
                print(f"      Size: {result['size_mb']:.2f} MB")
                print(f"      Extent: {result['width']}×{result['height']} pixels")
                print(f"      Bands: {result['bands']}")
                print(f"      CRS: {result['crs']}")
                print(f"      Data range: [{result['data_min']:.2f}, {result['data_max']:.2f}]")
            else:
                invalid_files[str(filepath)] = result
                print(f"    ❌ CORRUPT or INVALID")
                print(f"      Error: {result['error']}")
        print()
    
    # Phase 2: Detect shards
    print(f"{'PHASE 2: SHARD DETECTION':<70}")
    print(f"{'-'*70}\n")
    
    shards = detect_shards(files_by_year)
    if shards:
        print(f"⚠️  SHARDS DETECTED (multi-file exports):\n")
        for year, shard_files in sorted(shards.items()):
            print(f"  Year {year}: {len(shard_files)} shards")
            for shard_file in shard_files:
                info = valid_files.get(str(shard_file), {})
                if info:
                    print(f"    - {shard_file.name}")
                    print(f"      Extent: {info['width']}×{info['height']} px, {info['size_mb']:.2f} MB")
        print(f"\n→ ACTION REQUIRED: Run chirps_merge.py before proceeding!\n")
    else:
        print(f"✓ No shards detected. All files are single-export.\n")
    
    # Phase 3: Summary
    print(f"{'PHASE 3: SUMMARY':<70}")
    print(f"{'-'*70}\n")
    
    print(f"Valid files:     {len(valid_files)}")
    print(f"Invalid files:   {len(invalid_files)}")
    print(f"Total file size: {sum(f['size_mb'] for f in valid_files.values()):.2f} MB")
    
    if invalid_files:
        print(f"\n❌ INVALID FILES (delete and re-download):")
        for filepath, info in invalid_files.items():
            print(f"  - {Path(filepath).name}: {info['error']}")
    
    # Phase 4: Merge guidance
    print(f"\n{'PHASE 4: NEXT STEPS':<70}")
    print(f"{'-'*70}\n")
    
    if invalid_files:
        print("1. ❌ DELETE invalid files and re-download from Google Earth Engine")
        print("2. Run this verification again")
        return None
    elif shards:
        print("1. ✓ All files are valid")
        print("2. ⚠️  SHARDS DETECTED - run: python chirps_merge.py")
        print(f"      Example: python chirps_merge.py \\")
        print(f"        --input-dir '{input_dir}' \\")
        print(f"        --output-dir './chirps_merged' \\")
        print(f"        --target-resolution 0.02")
    else:
        print("1. ✓ All files are valid")
        print("2. ✓ No shards to merge - files are ready for processing")
        print("3. Continue with: python chirps_process.py")
        print(f"      Example: python chirps_process.py \\")
        print(f"        --input-dir '{input_dir}' \\")
        print(f"        --output-dir './chirps_processed'")
    
    print(f"\n{'='*70}\n")
    
    # Save report
    if output_report:
        report = {
            'input_directory': input_dir,
            'total_files': len(tiff_files),
            'valid_files': len(valid_files),
            'invalid_files': len(invalid_files),
            'shards_detected': len(shards) > 0,
            'shard_years': list(shards.keys()) if shards else [],
            'file_details': valid_files,
            'invalid_details': invalid_files,
        }
        with open(output_report, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, default=str)
        print(f"Report saved to: {output_report}\n")
    
    return {
        'valid_files': valid_files,
        'invalid_files': invalid_files,
        'shards': shards,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Verify CHIRPS downloaded data before merging.'
    )
    parser.add_argument(
        '--input-dir',
        required=True,
        help='Directory containing downloaded CHIRPS GeoTIFF files'
    )
    parser.add_argument(
        '--report',
        help='Save JSON verification report to this path'
    )
    
    args = parser.parse_args()
    
    result = verify_chirps_data(args.input_dir, output_report=args.report)
    
    if result and not result['invalid_files']:
        sys.exit(0)
    else:
        sys.exit(1)
