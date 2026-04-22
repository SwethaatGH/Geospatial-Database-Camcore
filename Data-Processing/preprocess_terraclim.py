"""
TerraClimate Preprocessing Script
Converts TerraClimate NetCDF (yearly, 12 monthly bands) to monthly GeoTIFFs.
Reads from flat dataset folder (TerraClimate_<var>_<year>.nc naming).
Clips to configured bounding box, resamples to configured resolution, EPSG:4326.

Output naming: terraclim_<var>_<year>_<month>.tif
"""

import os
import re
from multiprocessing import Pool, cpu_count
from pathlib import Path
from datetime import datetime

# Must be set before rasterio is imported to avoid PostgreSQL PROJ conflict
os.environ["PROJ_DATA"] = r"C:\Program Files\QGIS 3.40.4\share\proj"
os.environ["PROJ_LIB"] = r"C:\Program Files\QGIS 3.40.4\share\proj"

import numpy as np
import netCDF4 as nc
import rasterio
import rasterio.warp
from rasterio.transform import from_bounds
from rasterio.enums import Resampling
from rasterio.crs import CRS

# ----------------- CONFIG -----------------
INPUT_ROOT = Path(r"Z:\ENVIROMICS\terraclimate\2025_dataset")
OUTPUT_DIR = Path(r"Z:\ENVIROMICS\terraclimate\Indonesia_TerraClimate_Resampled_2025")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

BBOX = (95.293026, -10.359987, 141.033852, 5.479821)  # minX, minY, maxX, maxY

TARGET_RES = "0.02"
NUM_WORKERS = min(16, cpu_count())
VARIABLES = [
    "aet", "def", "PDSI", "pet", "ppt", "q", "soil",
    "srad", "tmax", "tmin", "vap", "vpd", "ws"
]


# ----------------- HELPERS -----------------

def _find_var(ds, var_name):
    for candidate in [var_name, f"{var_name}_mm"]:
        if candidate in ds.variables:
            return ds.variables[candidate], candidate
    raise KeyError(f"Variable '{var_name}' not found. Available: {list(ds.variables.keys())}")


def _apply_scale(var_obj, raw):
    fill = getattr(var_obj, "_FillValue", None)
    mask = (raw == fill) if fill is not None else np.zeros(raw.shape, dtype=bool)
    data = raw.astype(np.float32)
    scale = float(getattr(var_obj, "scale_factor", 1.0))
    offset = float(getattr(var_obj, "add_offset", 0.0))
    data = data * scale + offset
    data[mask] = np.nan
    return data


def _clip_resample(data, src_lon, src_lat, bbox, target_res):
    minx, miny, maxx, maxy = bbox
    res = float(target_res)

    src_res_lon = float(src_lon[1] - src_lon[0])
    src_res_lat = float(src_lat[1] - src_lat[0])
    lon_arr = np.array(src_lon)
    lat_arr = np.array(src_lat)

    col_min = max(0, int(np.searchsorted(lon_arr, minx) - 1))
    col_max = min(len(lon_arr), int(np.searchsorted(lon_arr, maxx) + 2))

    if lat_arr[0] > lat_arr[-1]:
        row_min = max(0, int(np.searchsorted(-lat_arr, -maxy) - 1))
        row_max = min(len(lat_arr), int(np.searchsorted(-lat_arr, -miny) + 2))
    else:
        row_min = max(0, int(np.searchsorted(lat_arr, miny) - 1))
        row_max = min(len(lat_arr), int(np.searchsorted(lat_arr, maxy) + 2))

    clipped = data[row_min:row_max, col_min:col_max]
    clip_lons = lon_arr[col_min:col_max]
    clip_lats = lat_arr[row_min:row_max]
    half_lon = abs(src_res_lon) / 2.0
    half_lat = abs(src_res_lat) / 2.0

    if lat_arr[0] > lat_arr[-1]:
        src_transform = from_bounds(
            clip_lons[0] - half_lon, clip_lats[-1] - half_lat,
            clip_lons[-1] + half_lon, clip_lats[0] + half_lat,
            clipped.shape[1], clipped.shape[0])
    else:
        src_transform = from_bounds(
            clip_lons[0] - half_lon, clip_lats[0] - half_lat,
            clip_lons[-1] + half_lon, clip_lats[-1] + half_lat,
            clipped.shape[1], clipped.shape[0])

    width_out = max(1, round((maxx - minx) / res))
    height_out = max(1, round((maxy - miny) / res))
    dst_transform = from_bounds(minx, miny, maxx, maxy, width_out, height_out)

    nodata = np.float32(-9999.0)
    clipped_filled = np.where(np.isnan(clipped), nodata, clipped).astype(np.float32)

    src_profile = {
        "driver": "GTiff", "dtype": "float32",
        "width": clipped.shape[1], "height": clipped.shape[0],
        "count": 1, "crs": CRS.from_epsg(4326),
        "transform": src_transform, "nodata": nodata,
    }
    dst_array = np.full((height_out, width_out), nodata, dtype=np.float32)
    with rasterio.MemoryFile() as memfile:
        with memfile.open(**src_profile) as src_ds:
            src_ds.write(clipped_filled[np.newaxis, :, :])
            rasterio.warp.reproject(
                source=rasterio.band(src_ds, 1),
                destination=dst_array,
                src_transform=src_transform, src_crs=CRS.from_epsg(4326),
                dst_transform=dst_transform, dst_crs=CRS.from_epsg(4326),
                resampling=Resampling.bilinear,
                src_nodata=nodata, dst_nodata=nodata,
            )
    return dst_array, dst_transform, nodata


# ----------------- MAIN -----------------

def build_tasks():
    tasks = []
    # Flat folder: TerraClimate_<var>_<year>.nc
    for nc_path in sorted(INPUT_ROOT.glob("TerraClimate_*.nc")):
        match = re.match(r"TerraClimate_(.+)_(\d{4})\.nc", nc_path.name)
        if not match:
            print(f"WARNING: Skipping (bad filename): {nc_path.name}")
            continue
        var_name = match.group(1)
        year = int(match.group(2))
        if var_name not in VARIABLES:
            continue
        for month in range(1, 13):
            out_file = OUTPUT_DIR / f"terraclim_{var_name.lower()}_{year}_{month:02d}.tif"
            if out_file.exists():
                continue
            tasks.append((var_name, nc_path, year, month))
    return tasks


def process_task(task):
    var_name, nc_path, year, month = task
    out_file = OUTPUT_DIR / f"terraclim_{var_name.lower()}_{year}_{month:02d}.tif"

    try:
        with nc.Dataset(str(nc_path), "r") as ds:
            ds.set_auto_maskandscale(False)
            var_obj, _ = _find_var(ds, var_name)

            raw = np.array(var_obj[month - 1, :, :], dtype=np.float32)
            data = _apply_scale(var_obj, raw)

            lon_var = ds.variables.get("lon") or ds.variables.get("longitude")
            lat_var = ds.variables.get("lat") or ds.variables.get("latitude")
            if lon_var is None or lat_var is None:
                raise KeyError("Cannot find lat/lon coordinate variables")
            lons = np.array(lon_var[:])
            lats = np.array(lat_var[:])

        dst_array, dst_transform, nodata = _clip_resample(
            data, lons, lats, BBOX, TARGET_RES)

        height_out, width_out = dst_array.shape
        profile = {
            "driver": "GTiff", "dtype": "float32",
            "width": width_out, "height": height_out,
            "count": 1, "crs": CRS.from_epsg(4326),
            "transform": dst_transform, "nodata": nodata,
            "compress": "lzw", "tiled": True, "bigtiff": "YES",
        }
        with rasterio.open(str(out_file), "w", **profile) as dst:
            dst.write(dst_array[np.newaxis, :, :])

        return "success", out_file.name, None

    except Exception as e:
        if out_file.exists():
            out_file.unlink()
        return "error", out_file.name, str(e)[:400]


if __name__ == "__main__":
    start = datetime.now()
    print("TerraClimate preprocessing")
    print(f"Input:  {INPUT_ROOT}")
    print(f"Output: {OUTPUT_DIR}")
    tasks = build_tasks()
    total = len(tasks)
    print(f"Total tasks: {total}")
    if total == 0:
        print("Nothing to process.")
        raise SystemExit(0)

    success = 0
    failed = 0
    with Pool(processes=NUM_WORKERS) as pool:
        for i, (status, name, msg) in enumerate(pool.imap_unordered(process_task, tasks), 1):
            if status == "success":
                success += 1
                print(f"[{i}/{total}] OK {name}")
            else:
                failed += 1
                print(f"[{i}/{total}] FAIL {name} - {msg}")

    print(f"Completed: {success} success, {failed} failed")
    print(f"Done in {(datetime.now()-start).total_seconds()/60:.1f} min")
