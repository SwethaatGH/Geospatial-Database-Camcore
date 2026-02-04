"""
Download all 14 SoilGrids variables for Indonesia from ISRIC WCS
"""

import os
import requests
from pathlib import Path
from tqdm import tqdm

# Indonesia bounding box
INDONESIA_BBOX = {
    'lat_min': -10.3599874813,
    'lat_max': 5.47982086834,
    'lon_min': 95.2930261576,
    'lon_max': 141.03385176
}

# Output directory
OUTPUT_DIR = Path(r"Q:\My Drive\Indonesia_SoilGrids")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# All 14 soil properties
ALL_PROPERTIES = {
    'bdod': 'Bulk Density (g/cm³)',
    'cec': 'Cation Exchange Capacity (mmol(c)/kg)',
    'cfvo': 'Coarse Fragments Volumetric (%)',
    'clay': 'Clay Content (%)',
    'nitrogen': 'Nitrogen Content (g/kg)',
    'ocd': 'Organic Carbon Density (kg/m³)',
    'ocs': 'Organic Carbon Stocks (t/ha)',
    'phh2o': 'pH in H2O',
    'sand': 'Sand Content (%)',
    'silt': 'Silt Content (%)',
    'soc': 'Soil Organic Carbon (g/kg)',
    'wv0010': 'Water Content at 10kPa (cm³/dm³)',
    'wv0033': 'Water Content at 33kPa (cm³/dm³)',
    'wv1500': 'Water Content at 1500kPa (cm³/dm³)',
}

# Depth layers (ocs uses different depth)
DEPTH_BY_PROPERTY = {
    'ocs': '0-30cm',      # Only available at 0-30cm depth
    'bdod': '0-5cm',
    'cec': '0-5cm',
    'cfvo': '0-5cm',
    'clay': '0-5cm',
    'nitrogen': '0-5cm',
    'ocd': '0-5cm',
    'phh2o': '0-5cm',
    'sand': '0-5cm',
    'silt': '0-5cm',
    'soc': '0-5cm',
    'wv0010': '0-5cm',
    'wv0033': '0-5cm',
    'wv1500': '0-5cm',
}

def download_soilgrids_property(property_name, description):
    """
    Download a single SoilGrids property for Indonesia
    
    Args:
        property_name: Soil property code (e.g., 'bdod', 'clay')
        description: Human-readable description
    """
    
    # Get appropriate depth for this property
    depth = DEPTH_BY_PROPERTY.get(property_name, '0-5cm')
    
    # Output filename
    output_file = OUTPUT_DIR / f"{property_name}_{depth}_mean.tif"
    
    # Check if already downloaded and valid (>1MB)
    if output_file.exists():
        file_size = output_file.stat().st_size
        if file_size > 1_000_000:  # At least 1 MB
            print(f"✓ Already exists: {property_name} ({file_size / (1024 * 1024):.2f} MB)")
            return True
        else:
            print(f"⚠️  Existing file too small ({file_size} bytes), re-downloading...")
            output_file.unlink()
    
    # Construct WCS URL
    base_url = f"https://maps.isric.org/mapserv?map=/map/{property_name}.map"
    
    # Coverage ID format: property_depth_mean
    coverage_id = f"{property_name}_{depth}_mean"
    
    # WCS parameters
    params = {
        'SERVICE': 'WCS',
        'VERSION': '2.0.1',
        'REQUEST': 'GetCoverage',
        'COVERAGEID': coverage_id,
        'FORMAT': 'image/tiff',
    }
    
    # Build URL with SUBSET parameters
    url_parts = [base_url]
    for key, value in params.items():
        url_parts.append(f"{key}={value}")
    
    # Add SUBSET parameters
    url_parts.append(f"SUBSET=long({INDONESIA_BBOX['lon_min']},{INDONESIA_BBOX['lon_max']})")
    url_parts.append(f"SUBSET=lat({INDONESIA_BBOX['lat_min']},{INDONESIA_BBOX['lat_max']})")
    url_parts.append("SUBSETTINGCRS=http://www.opengis.net/def/crs/EPSG/0/4326")
    url_parts.append("OUTPUTCRS=http://www.opengis.net/def/crs/EPSG/0/4326")
    # Downsample to ~1km resolution to stay within server limits
    url_parts.append("SCALEFACTOR=0.25")  # 250m * 4 = 1km resolution
    
    full_url = "&".join(url_parts)
    
    print(f"\nDownloading: {property_name} - {description}")
    print(f"Coverage ID: {coverage_id}")
    
    try:
        # Send request with streaming
        response = requests.get(full_url, stream=True, timeout=600)
        
        if response.status_code == 200:
            # Get file size if available
            total_size = int(response.headers.get('content-length', 0))
            
            # Download with progress bar
            with open(output_file, 'wb') as f:
                if total_size > 0:
                    with tqdm(total=total_size, unit='B', unit_scale=True, 
                             desc=property_name) as pbar:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                            pbar.update(len(chunk))
                else:
                    # No content-length header, download without progress
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
            
            file_size = output_file.stat().st_size / (1024 * 1024)  # MB
            print(f"✓ Downloaded: {output_file.name} ({file_size:.2f} MB)")
            return True
            
        else:
            print(f"✗ Failed: HTTP {response.status_code}")
            print(f"  Response: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"✗ Timeout: Request took longer than 10 minutes")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def main():
    print(f"{'='*70}")
    print(f"Download All SoilGrids Variables for Indonesia")
    print(f"{'='*70}")
    print(f"Bounding Box: Lat [{INDONESIA_BBOX['lat_min']}, {INDONESIA_BBOX['lat_max']}]")
    print(f"              Lon [{INDONESIA_BBOX['lon_min']}, {INDONESIA_BBOX['lon_max']}]")
    print(f"Output Directory: {OUTPUT_DIR}")
    print(f"Variables to download: {len(ALL_PROPERTIES)}")
    print(f"Note: ocs uses 0-30cm depth, others use 0-5cm")
    print(f"{'='*70}")
    
    # Download all properties
    successful = []
    failed = []
    
    total = len(ALL_PROPERTIES)
    
    for idx, (prop_name, description) in enumerate(ALL_PROPERTIES.items(), 1):
        print(f"\n[{idx}/{total}] Processing: {prop_name}")
        print("-" * 70)
        
        success = download_soilgrids_property(prop_name, description)
        
        if success:
            successful.append(prop_name)
        else:
            failed.append(prop_name)
    
    # Summary
    print(f"\n{'='*70}")
    print(f"DOWNLOAD SUMMARY")
    print(f"{'='*70}")
    print(f"✓ Successful: {len(successful)}/{total}")
    print(f"✗ Failed: {len(failed)}/{total}")
    
    if successful:
        print(f"\nSuccessfully downloaded:")
        for prop in successful:
            print(f"  ✓ {prop}")
    
    if failed:
        print(f"\nFailed to download:")
        for prop in failed:
            print(f"  ✗ {prop}")
    
    print(f"\nOutput location: {OUTPUT_DIR}")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()
