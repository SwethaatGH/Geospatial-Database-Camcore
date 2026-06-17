"""
NASA POWER NetCDF to Monthly GeoTIFF Unpacking

Purpose:
- Treat NASA POWER conversion as an unpacking step.
- Read downloaded per-variable NetCDF files.
- Aggregate daily data to monthly means.
- Write monthly GeoTIFFs per variable.

Output pattern:
- <output_base>/<var_name>/<var_name>_YYYY_MM.tif
"""

import glob
import logging
import os
from datetime import datetime
from pathlib import Path

import numpy as np
import xarray as xr

# Set before rasterio import to avoid PROJ conflicts in mixed environments.
os.environ["PROJ_LIB"] = r"C:\Program Files\QGIS 3.40.4\share\proj"

import rasterio
from rasterio.transform import from_bounds


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# Update these paths for your environment.
DATA_DIR = r"C:\Users\rcavalh\Documents\Camcore25\DB_Indonesia\Brazil_NASA_POWER_2025"
OUTPUT_BASE_DIR = r"C:\Users\rcavalh\Documents\Camcore25\DB_Indonesia\Brazil_NASA_POWER_2025_Monthly"

# None keeps native grid. Set e.g. 0.02 to interpolate to 0.02 degree.
TARGET_RES = None


def is_base_variable_file(filename: str) -> bool:
    """Keep base variables; exclude hourly and stat suffix files."""
    stem = Path(filename).stem

    if stem.endswith(tuple(f"_{i:02d}" for i in range(24))):
        return False
    if stem.endswith(("_MAX", "_MIN", "_SD")):
        return False

    return True


def process_netcdf_to_monthly(nc_file: str) -> None:
    logger.info("Processing NetCDF file: %s", os.path.basename(nc_file))

    try:
        try:
            ds = xr.open_dataset(nc_file)
        except Exception as exc:
            logger.error("Cannot open NetCDF file: %s", exc)
            logger.warning("Skipping potentially corrupted file: %s", os.path.basename(nc_file))
            return

        data_vars = [v for v in ds.data_vars if "time" in ds[v].dims]
        if not data_vars:
            logger.warning("No time-series variable found in %s", os.path.basename(nc_file))
            ds.close()
            return

        var_name = data_vars[0]
        var_name_lower = var_name.lower()
        logger.info("Variable: %s -> %s", var_name, var_name_lower)

        output_dir = os.path.join(OUTPUT_BASE_DIR, var_name_lower)
        os.makedirs(output_dir, exist_ok=True)

        data = ds[var_name]
        if "time" not in data.dims:
            logger.warning("Variable %s has no time dimension", var_name)
            ds.close()
            return

        monthly_data = data.resample(time="1MS").mean(dim="time")
        total_months = len(monthly_data.time)
        logger.info("Monthly slices: %d", total_months)

        for i, time_val in enumerate(monthly_data.time.values):
            try:
                dt = np.datetime64(time_val).astype("datetime64[M]").astype(datetime)
                year = dt.year
                month = dt.month
                month_str = f"{month:02d}"

                output_file = os.path.join(output_dir, f"{var_name_lower}_{year}_{month_str}.tif")
                if os.path.exists(output_file):
                    logger.info("Skipping %d/%d: %s-%s exists", i + 1, total_months, year, month_str)
                    continue

                month_array = monthly_data.isel(time=i)

                if "lat" in ds.coords and "lon" in ds.coords:
                    lats = ds.lat.values
                    lons = ds.lon.values
                    lat_name, lon_name = "lat", "lon"
                elif "latitude" in ds.coords and "longitude" in ds.coords:
                    lats = ds.latitude.values
                    lons = ds.longitude.values
                    lat_name, lon_name = "latitude", "longitude"
                else:
                    logger.error("No lat/lon coordinates in %s", os.path.basename(nc_file))
                    continue

                west, east = float(lons.min()), float(lons.max())
                south, north = float(lats.min()), float(lats.max())

                if TARGET_RES:
                    new_lons = np.arange(west, east + TARGET_RES, TARGET_RES)
                    new_lats = np.arange(south, north + TARGET_RES, TARGET_RES)
                    month_array = month_array.interp({lat_name: new_lats, lon_name: new_lons}, method="linear")
                    lats = month_array[lat_name].values

                array = month_array.to_numpy()
                if np.ma.isMaskedArray(array):
                    array = array.filled(np.nan)
                array = np.asarray(array, dtype="float32")
                array[np.isinf(array)] = np.nan

                if array.ndim != 2:
                    logger.error("Unexpected array shape for %s: %s", output_file, array.shape)
                    continue

                if lats[0] < lats[-1]:
                    array = np.flipud(array)

                height, width = array.shape
                transform = from_bounds(west, south, east, north, width, height)
                array_out = np.where(np.isnan(array), -9999.0, array).astype("float32")

                with rasterio.open(
                    output_file,
                    "w",
                    driver="GTiff",
                    height=height,
                    width=width,
                    count=1,
                    dtype="float32",
                    crs="EPSG:4326",
                    transform=transform,
                    compress="lzw",
                    tiled=True,
                    nodata=-9999.0,
                ) as dst:
                    dst.write(array_out, 1)

                logger.info("Created: %s", os.path.basename(output_file))

            except Exception as exc:
                logger.error("Error writing month %d for %s: %s", i + 1, os.path.basename(nc_file), exc)
                continue

        ds.close()

    except Exception as exc:
        logger.error("Unexpected failure processing %s: %s", nc_file, exc)


def main() -> None:
    logger.info("Starting NASA POWER monthly unpacking")
    logger.info("Input: %s", DATA_DIR)
    logger.info("Output: %s", OUTPUT_BASE_DIR)

    os.makedirs(OUTPUT_BASE_DIR, exist_ok=True)

    all_nc_files = glob.glob(os.path.join(DATA_DIR, "*.nc"))
    if not all_nc_files:
        logger.error("No NetCDF files found in %s", DATA_DIR)
        return

    nc_files = [f for f in all_nc_files if is_base_variable_file(f)]
    logger.info("Found %d total .nc files", len(all_nc_files))
    logger.info("Processing %d base-variable files", len(nc_files))

    for idx, nc_file in enumerate(sorted(nc_files), 1):
        logger.info("[%d/%d] %s", idx, len(nc_files), os.path.basename(nc_file))
        process_netcdf_to_monthly(nc_file)

    logger.info("Unpacking complete")


if __name__ == "__main__":
    main()
