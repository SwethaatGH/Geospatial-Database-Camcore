"""
SPEI USA Yearly-to-Monthly Unpacking Script
- Mosaics two yearly shards for each year
- Extracts each month's band (1-12) and writes one GeoTIFF per month
- Output: spei_usa_<year>_<month>.tif in ENVIROMICS/spei_usa_monthly
"""

import os
import re
from pathlib import Path
import rasterio
from rasterio.merge import merge
from rasterio.io import MemoryFile
from multiprocessing import Pool, cpu_count

# ----------------- CONFIG -----------------
INPUT_DIR = Path(r"Q:\My Drive\USA_SPEI_Years")
OUTPUT_DIR = Path(r"Z:\ENVIROMICS\spei_usa_monthly")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
NODATA_VALUE = -9999

# ----------------- HELPERS -----------------
def get_year_from_filename(filename):
    match = re.search(r"SPEI_USA_(\d{4})-", filename)
    return int(match.group(1)) if match else None

def group_files_by_year(files):
    years = {}
    for f in files:
        year = get_year_from_filename(f.name)
        if year:
            years.setdefault(year, []).append(f)
    return years

def process_month(args):
    year, files, month = args
    files = sorted(files)
    memfiles = []
    datasets = []
    try:
        for f in files:
            with rasterio.open(str(f)) as src:
                if month > src.count:
                    continue
                band = src.read(month)
                meta = src.meta.copy()
                meta.update({
                    'count': 1,
                    'dtype': band.dtype,
                    'nodata': NODATA_VALUE
                })
                memfile = MemoryFile()
                with memfile.open(**meta) as tmp:
                    tmp.write(band, 1)
                memfiles.append(memfile)
                datasets.append(memfile.open())
        if not datasets:
            return None
        mosaic, out_trans = merge(datasets, nodata=NODATA_VALUE)
        mosaic = mosaic[0]
        out_name = f"spei_usa_{year}_{month:02d}.tif"
        out_path = OUTPUT_DIR / out_name
        with rasterio.open(
            out_path,
            'w',
            driver='GTiff',
            height=mosaic.shape[0],
            width=mosaic.shape[1],
            count=1,
            dtype=mosaic.dtype,
            crs=datasets[0].crs,
            transform=out_trans,
            nodata=NODATA_VALUE,
            compress='LZW',
            tiled=True,
            BIGTIFF='YES',
        ) as dst:
            dst.write(mosaic, 1)
        print(f"[{year}] Month {month}: {out_name}")
    finally:
        for ds in datasets:
            ds.close()
        for mf in memfiles:
            mf.close()

# ----------------- MAIN -----------------
def main():
    tif_files = sorted(INPUT_DIR.glob("*.tif"))
    if not tif_files:
        print(f"No .tif files found in {INPUT_DIR}")
        return
    years = group_files_by_year(tif_files)
    print(f"Found years: {sorted(years.keys())}")
    for year, files in years.items():
        if len(files) != 2:
            print(f"Warning: {year} has {len(files)} files (expected 2)")
            continue
        print(f"Processing year {year} (12 months) in parallel...")
        args_list = [(year, files, month) for month in range(1, 13)]
        with Pool(processes=min(cpu_count(), 12)) as pool:
            pool.map(process_month, args_list)

if __name__ == "__main__":
    main()
