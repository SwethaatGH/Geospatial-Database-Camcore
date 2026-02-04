#!/usr/bin/env python
"""
NASA Power NetCDF to Monthly Rasters
------------------------------------
Aggregates daily NASA Power NetCDF data to monthly means,
then exports as GeoTIFF rasters.

Requirements:
- netCDF4
- xarray
- rasterio
- numpy
"""

import os
import glob
import logging
import xarray as xr
import numpy as np
from pathlib import Path
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Set input and output directories
DATA_DIR = r"Q:\My Drive\Indonesia_NASA_POWER_Daily"
OUTPUT_BASE_DIR = r"Q:\My Drive\Indonesia_NASA_POWER_Monthly"

# Target resolution in degrees (None = keep native 1 degree resolution)
TARGET_RES = None

def process_netcdf_to_monthly(nc_file):
    """
    Process a single NetCDF file:
    1. Open with xarray
    2. Resample daily data to monthly means
    3. Export each month as a GeoTIFF
    """
    logger.info(f"Processing NetCDF file: {os.path.basename(nc_file)}")
    
    try:
        # Open NetCDF file
        ds = xr.open_dataset(nc_file)
        
        # Get the variable name (should be only one data variable)
        data_vars = [v for v in ds.data_vars if 'time' in ds[v].dims]
        
        if not data_vars:
            logger.warning(f"No time-series variables found in {os.path.basename(nc_file)}")
            return
        
        var_name = data_vars[0]
        var_name_lower = var_name.lower()
        
        logger.info(f"Processing variable: {var_name}")
        
        # Create output directory for this variable
        output_dir = os.path.join(OUTPUT_BASE_DIR, var_name_lower)
        os.makedirs(output_dir, exist_ok=True)
        
        # Get the data array
        data = ds[var_name]
        
        # Check if data has time dimension
        if 'time' not in data.dims:
            logger.warning(f"Variable {var_name} has no time dimension")
            return
        
        # Get initial info
        total_days = len(data.time)
        logger.info(f"Total daily time steps: {total_days}")
        
        # Resample to monthly means
        logger.info("Resampling to monthly means...")
        monthly_data = data.resample(time='1MS').mean(dim='time')
        
        total_months = len(monthly_data.time)
        logger.info(f"Total monthly time steps: {total_months}")
        
        # Process each month
        for i, time_val in enumerate(monthly_data.time.values):
            try:
                # Convert to datetime
                dt = np.datetime64(time_val).astype('datetime64[M]').astype(datetime)
                year = dt.year
                month = dt.month
                month_str = f"{month:02d}"
                
                # Create output filename
                output_file = os.path.join(output_dir, f"{var_name_lower}_{year}_{month_str}.tif")
                
                # Skip if already exists
                if os.path.exists(output_file):
                    logger.info(f"Skipping {i+1}/{total_months}: {year}-{month_str} (already exists)")
                    continue
                
                logger.info(f"Processing {i+1}/{total_months}: {year}-{month_str}")
                
                # Get the monthly data
                month_array = monthly_data.isel(time=i)
                
                # Export to GeoTIFF using rasterio
                import rasterio
                from rasterio.transform import from_bounds
                
                # Get spatial extent
                if 'lat' in ds.coords and 'lon' in ds.coords:
                    lats = ds.lat.values
                    lons = ds.lon.values
                    lat_name = 'lat'
                    lon_name = 'lon'
                elif 'latitude' in ds.coords and 'longitude' in ds.coords:
                    lats = ds.latitude.values
                    lons = ds.longitude.values
                    lat_name = 'latitude'
                    lon_name = 'longitude'
                else:
                    logger.error("Cannot find lat/lon coordinates")
                    continue
                
                # Calculate bounds
                min_lon, max_lon = float(lons.min()), float(lons.max())
                min_lat, max_lat = float(lats.min()), float(lats.max())
                
                # Resample to target resolution (0.02 degrees)
                if TARGET_RES:
                    # Create new coordinate arrays at target resolution
                    new_lons = np.arange(min_lon, max_lon + TARGET_RES, TARGET_RES)
                    new_lats = np.arange(min_lat, max_lat + TARGET_RES, TARGET_RES)
                    
                    # Interpolate to new grid
                    month_array = month_array.interp({lat_name: new_lats, lon_name: new_lons}, method='linear')
                    
                    # Update coordinate arrays
                    lats = month_array[lat_name].values
                    lons = month_array[lon_name].values
                
                # Get array values
                array = month_array.values
                
                # Handle dimension order (should be lat, lon)
                if array.ndim != 2:
                    logger.error(f"Unexpected array dimensions: {array.shape}")
                    continue
                
                # Ensure correct orientation (top-down)
                if lats[0] < lats[-1]:  # If lats are ascending, flip
                    array = np.flipud(array)
                    min_lat, max_lat = max_lat, min_lat
                
                # Calculate transform
                height, width = array.shape
                transform = from_bounds(min_lon, min_lat, max_lon, max_lat, width, height)
                
                # Write to GeoTIFF
                with rasterio.open(
                    output_file,
                    'w',
                    driver='GTiff',
                    height=height,
                    width=width,
                    count=1,
                    dtype=array.dtype,
                    crs='EPSG:4326',
                    transform=transform,
                    compress='lzw',
                    tiled=True,
                    nodata=-9999.0
                ) as dst:
                    # Replace NaN with nodata
                    array_out = np.where(np.isnan(array), -9999.0, array)
                    dst.write(array_out.astype('float32'), 1)
                
                logger.info(f"Created: {os.path.basename(output_file)}")
                
            except Exception as e:
                logger.error(f"Error processing month {i+1}: {str(e)}")
                continue
        
        ds.close()
        logger.info(f"Completed processing {var_name}")
        
    except Exception as e:
        logger.error(f"Error processing file {nc_file}: {str(e)}")
        import traceback
        traceback.print_exc()

def main():
    """Main processing function."""
    logger.info("Starting NASA Power Daily to Monthly Conversion")
    
    # Create output base directory
    os.makedirs(OUTPUT_BASE_DIR, exist_ok=True)
    
    # Find all NetCDF files
    nc_files = glob.glob(os.path.join(DATA_DIR, "*.nc"))
    
    if not nc_files:
        logger.error(f"No NetCDF files found in {DATA_DIR}")
        return
    
    logger.info(f"Found {len(nc_files)} NetCDF files")
    
    # Process each file
    for idx, nc_file in enumerate(nc_files, 1):
        logger.info(f"\n{'='*60}")
        logger.info(f"File {idx}/{len(nc_files)}: {os.path.basename(nc_file)}")
        logger.info(f"{'='*60}")
        process_netcdf_to_monthly(nc_file)
    
    logger.info("\n" + "="*60)
    logger.info("All files processed!")
    logger.info(f"Output saved to: {OUTPUT_BASE_DIR}")
    logger.info("="*60)

if __name__ == "__main__":
    main()
