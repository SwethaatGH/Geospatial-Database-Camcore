#!/usr/bin/env python
"""
NetCDF to Daily Rasters Conversion Script
----------------------------------------
Converts NetCDF time series data to individual daily GeoTIFF rasters
without using -a_srs parameter to avoid PROJ database conflicts.

Requirements:
- GDAL
- xarray
- netCDF4
- numpy
- python-dateutil
"""

import os
import sys
import glob
import logging
import subprocess
import xarray as xr
import numpy as np
from datetime import datetime
from dateutil.parser import parse
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Set GDAL path - adjust as needed
GDAL_BIN = r"C:\Program Files\QGIS 3.40.4\bin"
gdal_translate = os.path.join(GDAL_BIN, "gdal_translate.exe")

# Set input and output directories
DATA_DIR = r"Q:\My Drive\Indonesia_NASA_POWER_Daily"
OUTPUT_BASE_DIR = r"Q:\My Drive\Indonesia_NASA_POWER_Monthly"

# Target resolution in degrees (can be removed if you want to keep original resolution)
TARGET_RES = 0.02

def get_time_info(ds):
    """
    Extract time information from the dataset.
    Returns the first date in the time series.
    """
    if 'time' in ds.dims:
        times = ds.time.values
        if len(times) > 0:
            # Try to get the first time value
            try:
                # Handle different time formats
                if isinstance(times[0], (int, float, np.integer, np.floating)):
                    # Likely a numeric timestamp
                    return datetime.fromtimestamp(float(times[0]))
                else:
                    # String or datetime64 object
                    return parse(str(times[0]))
            except (ValueError, TypeError):
                logger.warning(f"Could not parse time value: {times[0]}")
                
    # Default to January 1, 1900 if no valid time found
    return datetime(1900, 1, 1)

def process_netcdf_file(nc_file):
    """Process a single NetCDF file."""
    logger.info(f"Processing NetCDF file: {os.path.basename(nc_file)}")
    
    try:
        # Open NetCDF file using xarray
        ds = xr.open_dataset(nc_file)
        
        # Get time information
        start_date = get_time_info(ds)
        logger.info(f"Start date detected: {start_date.strftime('%Y-%m-%d')}")
        
        # Process each variable in the dataset
        for var_name in ds.data_vars:
            # Skip coordinate variables and variables without time dimension
            if 'time' not in ds[var_name].dims:
                continue
                
            # Create lowercase variable name for output
            var_name_lower = var_name.lower()
            
            logger.info(f"Processing variable: {var_name}")
            
            # Create output directory for this variable
            output_dir = os.path.join(OUTPUT_BASE_DIR, var_name_lower)
            os.makedirs(output_dir, exist_ok=True)
            
            # Get the number of time steps
            num_times = len(ds.time)
            logger.info(f"Total time steps: {num_times}")
            
            # Process each time step
            for i, time_value in enumerate(ds.time.values):
                try:
                    # Parse time value to get year, month, and day
                    if isinstance(time_value, (int, float, np.integer, np.floating)):
                        dt = datetime.fromtimestamp(float(time_value))
                    else:
                        dt = parse(str(time_value))
                    
                    year = dt.year
                    month = dt.month
                    day = dt.day
                    
                    # Format month and day with leading zeros
                    month_str = f"{month:02d}"
                    day_str = f"{day:02d}"
                    
                    # Create output filename
                    # For monthly data, use this naming format (without day)
                    output_file = os.path.join(output_dir, f"{var_name_lower}_{year}_{month_str}.tif")
                    
                    logger.info(f"Processing time step {i+1}/{num_times}: {year}-{month_str}-{day_str}")
                    
                    # Get band number (1-based index for GDAL)
                    band_num = i + 1
                    
                    # Build GDAL command without -a_srs to avoid PROJ errors
                    cmd = [
                        gdal_translate,
                        f"NETCDF:{nc_file}:{var_name}",
                        "-of", "GTiff",
                        "-b", str(band_num),
                        "-co", "COMPRESS=LZW", 
                        "-co", "TILED=YES",
                        "-r", "bilinear",
                        "-ot", "Float32",
                        "-a_nodata", "-9999.0",
                        output_file
                    ]
                    
                    # Add resolution parameters if specified
                    if TARGET_RES:
                        cmd.extend(["-tr", str(TARGET_RES), str(TARGET_RES)])
                    
                    # Execute the command
                    subprocess.run(cmd, check=True)
                    
                except Exception as e:
                    logger.error(f"Error processing time step {i+1}: {str(e)}")
                    continue
                    
    except Exception as e:
        logger.error(f"Error processing file {nc_file}: {str(e)}")
    finally:
        # Close the dataset
        if 'ds' in locals():
            ds.close()

def main():
    """Main processing function."""
    logger.info("Starting NetCDF to Daily Rasters Conversion")
    
    # Create output base directory if it doesn't exist
    os.makedirs(OUTPUT_BASE_DIR, exist_ok=True)
    
    # Find all NetCDF files in the data directory
    nc_files = glob.glob(os.path.join(DATA_DIR, "*.nc"))
    
    if not nc_files:
        logger.error(f"No NetCDF files found in {DATA_DIR}")
        return
        
    logger.info(f"Found {len(nc_files)} NetCDF files")
    
    # Process each NetCDF file
    for nc_file in nc_files:
        process_netcdf_file(nc_file)
        
    logger.info("All NetCDF files have been processed")
    logger.info(f"Output saved to: {OUTPUT_BASE_DIR}")

if __name__ == "__main__":
    main()