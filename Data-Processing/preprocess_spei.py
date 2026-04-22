import os
from pathlib import Path
import subprocess
from multiprocessing import Pool, cpu_count


"""
SPEI USA Monthly Resampling Script
- Resamples all spei_usa_YYYY_MM.tif files in ENVIROMICS/spei_usa_monthly
- Output: ENVIROMICS/spei_usa_monthly_resampled/spei_usa_YYYY_MM.tif
- Target resolution: 0.02 degrees
- NoData: -9999, Float32, LZW compression, tiled
- Parallelized for speed
"""


# Set PROJ_LIB to QGIS PROJ directory to avoid PROJ database warnings
os.environ["PROJ_LIB"] = r"C:\Program Files\QGIS 3.40.4\share\proj"

INPUT_DIR = Path(r"Z:\ENVIROMICS\spei_usa_monthly")
OUTPUT_DIR = Path(r"Z:\ENVIROMICS\spei_usa_monthly_resampled")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TARGET_RES = 0.02
NODATA = -9999.0
NUM_WORKERS = min(cpu_count(), 12)
# Path to gdalwarp executable (update as needed)
GDALWARP = r"C:\Program Files\QGIS 3.40.4\bin\gdalwarp.exe"

def resample_one(file_path):
    out_path = OUTPUT_DIR / file_path.name
    cmd = [
        GDALWARP,
        "-tr", str(TARGET_RES), str(TARGET_RES),
        "-r", "bilinear",
        "-co", "COMPRESS=LZW",
        "-co", "TILED=YES",
        "-ot", "Float32",
        "-dstnodata", str(NODATA),
        str(file_path),
        str(out_path)
    ]
    try:
        subprocess.run(cmd, check=True)
        print(f"Resampled: {file_path.name}")
    except Exception as e:
        print(f"Failed: {file_path.name} ({e})")

def main():
    tif_files = sorted(INPUT_DIR.glob("spei_usa_*.tif"))
    if not tif_files:
        print(f"No files found in {INPUT_DIR}")
        return
    print(f"Resampling {len(tif_files)} files to {OUTPUT_DIR}...")
    with Pool(processes=NUM_WORKERS) as pool:
        pool.map(resample_one, tif_files)
    print("Done.")

if __name__ == "__main__":
    main()
