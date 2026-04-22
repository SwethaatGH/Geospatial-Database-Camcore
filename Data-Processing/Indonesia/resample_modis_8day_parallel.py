"""
MODIS 8-day Indonesia Resampling Script
Resamples all .tif files in INPUT_DIR to 0.02° resolution, EPSG:4326, sets NoData to -9999, outputs Float32, and writes to OUTPUT_DIR.
Parallel processing for speed.
Output naming: modis_et_YYYY_MM_DD.tif
"""

import os
from pathlib import Path
from multiprocessing import Pool, cpu_count
import subprocess
import re

# GDAL / PROJ
GDAL_BIN = r"C:\\Program Files\\QGIS 3.40.4\\bin"
GDALWARP = os.path.join(GDAL_BIN, "gdalwarp.exe")
PROJ_LIB = r"C:\\Program Files\\QGIS 3.40.4\\share\\proj"
INPUT_DIR = Path(r"Q:\My Drive\Indonesia_MODIS_ET_8day")
OUTPUT_DIR = Path(r"Z:\ENVIROMICS\Indonesia_modis_resampled")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_RES = "0.02"
NODATA = "-9999.0"
NUM_WORKERS = min(16, cpu_count())


def extract_date(filename):
    # Example: ET_Indonesia_2000-01-01.tif
    m = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
    return m.group(1) if m else None


def build_tasks():
    tasks = []
    for tif_path in INPUT_DIR.glob("*.tif"):
        date = extract_date(tif_path.name)
        if not date:
            print(f"⚠️  Skipping (no date): {tif_path.name}")
            continue
        year, month, day = date.split("-")
        out_name = f"modis_et_{year}_{month}_{day}.tif"
        out_path = OUTPUT_DIR / out_name
        if out_path.exists():
            continue
        tasks.append((tif_path, out_path))
    return tasks


def process_task(task):
    tif_path, out_path = task
    cmd = [
        GDALWARP,
        "-t_srs", "EPSG:4326",
        "-tr", TARGET_RES, TARGET_RES,
        "-r", "bilinear",
        "-co", "COMPRESS=LZW",
        "-co", "TILED=YES",
        "-ot", "Float32",
        "-dstnodata", NODATA,
        str(tif_path),
        str(out_path)
    ]
    env = os.environ.copy()
    env["PROJ_LIB"] = PROJ_LIB
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if result.returncode != 0:
            return "error", out_path.name, result.stderr.strip()[:400]
        return "success", out_path.name, None
    except Exception as e:
        return "error", out_path.name, str(e)


if __name__ == "__main__":
    tasks = build_tasks()
    total = len(tasks)
    print(f"Total tasks: {total}")
    if total == 0:
        print("Nothing to process.")
        exit(0)

    success = 0
    failed = 0
    with Pool(processes=NUM_WORKERS) as pool:
        for i, (status, name, msg) in enumerate(pool.imap_unordered(process_task, tasks), 1):
            if status == "success":
                success += 1
                print(f"[{i}/{total}] ✓ {name}")
            else:
                failed += 1
                print(f"[{i}/{total}] ✗ {name} - {msg}")

    print(f"Completed: {success} success, {failed} failed")
