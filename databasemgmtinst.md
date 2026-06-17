# Database Management Instructions — covariablesv1 (Brazil)

This document is the single reference for adding a new year of data to the **covariablesv1** PostGIS database, which backs the CSV generator and API for the Brazil region.

---

## What Needs to Be Updated Each Year

The database has two categories of datasets:

### Static — No Update Needed
These are one-time uploads that never change. Do NOT re-run these for 2026:

| Dataset | Table | Reason |
|---------|-------|--------|
| WorldClim | `wc_data` | Historical baseline 1960–2021, not updated |
| Elevation (SRTM) | `elev_data` | Topography does not change |
| SoilGrids | `soil_data` | Soil survey data, not time-series |
| Köppen-Geiger | `koppen_data` | Climate classification, static |
| BioCLIM | `bio_data` | Derived from WorldClim, static |

### Time-Series — Must Update for 2026
Run all 4 steps (Download → Unpack → Process → Upload) for each of these:

| Dataset | Table | Cadence | Variables |
|---------|-------|---------|-----------|
| CHIRPS | `chirps_data` | Daily | precipitation |
| TerraClim | `terraclim_data` | Monthly | aet, def, PDSI, pet, ppt, q, soil, srad, tmax, tmin, vap, vpd, ws |
| NASA Power | `np_data` | Monthly | 47 variables (see API) |
| SPEI | `spei_data` | Monthly | spei |
| ET (MODIS) | `et_data` | 8-day | et |
| ERA5-Land | `era5_data` | Daily | 15 variables (temp, precip, soil moisture, etc.) |

---

## Critical Rules Before You Start

> **ALWAYS use append mode** when uploading. Use the `-a` flag with `raster2pgsql`. **NEVER use `-c` or `-d`** (create/drop) — this would destroy all historical data.

> **Always check the latest date already in the table** before uploading, to avoid duplicate records:
> ```sql
> SELECT MAX(date_id), COUNT(*) FROM chirps_data;
> SELECT MAX(date_id), COUNT(*) FROM terraclim_data;
> SELECT MAX(date_id), COUNT(*) FROM np_data;
> SELECT MAX(date_id), COUNT(*) FROM spei_data;
> SELECT MAX(date_id), COUNT(*) FROM et_data;
> SELECT MAX(date_id), COUNT(*) FROM era5_data;
> ```

> **Brazil bounding box** (used in all scripts):
> `minX=-94.1875, minY=-39.0208, maxX=37.0625, maxY=18.2292` (EPSG:4326)

> **Many scripts in this repo are for Indonesia (`covariables_indonesia`).** The correct scripts for Brazil (`covariablesv1`) are identified per dataset below. Do not mix them up.

---

## Dataset 1: CHIRPS (Daily Precipitation)

**Table:** `chirps_data` | **Cadence:** Daily | **Output:** `chirps_YYYY_MM_DD.tif`

### Step 1 — Download
**Script:** `Data-Download/Brazil/DownloadCHIRPS_GEE.ipynb`

- Runs on Google Earth Engine (GEE) / Google Colab
- Authenticate with `ee-camcoredatabase` project
- Change `years = list(range(2026, 2027))` for 2026 data
- Exports to Google Drive folder `Brazil_CHIRPS_Daily/` as yearly multi-band GeoTIFFs (one per year, 365/366 bands)
- GEE may export as 2 shards (e.g., `CHIRPS_Daily_2026-0000000000-0000000000.tif` and `...-0000000001.tif`) — that is normal, handled in Unpack

> ❌ Do NOT use: `Data-Download/DownloadCHIRPS_GEE.ipynb` (old location, not Brazil-specific)

### Step 2 — Unpack
**Script:** `Data-Unpacking/unpack_chirps_yearly_to_daily.py`

- Splits yearly multi-band GeoTIFF (365 bands) into individual daily files
- If GEE exported 2 shards, merge them first — see the chirps_merge note below
- Update `INPUT_DIR` and `OUTPUT_DIR` to your local paths
- Output files named: `chirps_2026_MM_DD.tif`
- Uses parallel workers (`NUM_WORKERS = 8`) — adjust for your machine

> **If GEE exported shards (2 files for 1 year):** Use `Data-Processing/Brazil-2025/chirps_merge.py` first to merge shards into a single yearly file, then run the unpack script. See the poorna notes (`DOCUMENTATION/poorna_notes/2025_Data_Issues_Session_Notes.md`) for the shard merge process.

> ❌ Do NOT use: `Data-Unpacking/unpack_et_indonesia.py`, `unpack_spei_yearly_to_monthly.py`, `unpack_yearly_stacks.py` for CHIRPS

### Step 3 — Process (Resample)
**Script:** `Data-Processing/resample_chirps.py`

- Resamples from native CHIRPS resolution (~0.045°) to 0.02° using bilinear interpolation
- Update `INPUT_DIR` and `OUTPUT_DIR` to your local paths
- Resolution: `0.02°`, NoData: `-9999.0`, CRS: EPSG:4326, Format: Float32

> ❌ Do NOT use: `Data-Processing/preprocess_chirps.py` — that script uses **Indonesia paths** and was written for a different pipeline

### Step 4 — Upload
**Script:** `Data-Upload/upload_chirps_python.py`

- **Database:** `covariablesv1` ✅ (already configured correctly — confirmed in script)
- **Table:** `chirps_data`
- Update `INPUT_DIR` to your resampled files directory
- Uses parallel workers (`NUM_WORKERS = 16`)
- Uses `raster2pgsql` with append mode and all tiles
- Automatically creates yearly partitions (`chirps_data_2026`)

> ❌ Do NOT use: `Data-Upload/upload_chirps.py` — targets `covariables_indonesia`
> ❌ Do NOT use: `Data-Upload/uploadchirps.bat` — targets `covariables_indonesia`

---

## Dataset 2: TerraClim (Monthly, 13 Variables)

**Table:** `terraclim_data` | **Cadence:** Monthly | **Output:** `terraclim_<var>_2026_MM.tif`

### Step 1 — Download
**Script:** `Data-Download/download_terraclimate.py`

- Downloads NetCDF files directly from `climate.northwestknowledge.net`
- Update `OUTPUT_FOLDER` to your local path
- Update `START_YEAR = 2026` and `END_YEAR = 2026`
- Downloads 13 variables × 1 year = 13 `.nc` files
- Each file is a global NetCDF with 12 monthly bands

> Note: The `OUTPUT_FOLDER` in the script currently points to an Indonesia path — just change it to your local Brazil download folder.

### Step 2 — Unpack
**Not needed.** TerraClim NetCDFs come as yearly files with 12 monthly bands. The preprocessing script (Step 3) handles extraction of each month directly from the NetCDF.

### Step 3 — Process (Clip + Resample)
**Script:** `Data-Processing/preprocess_terraclim.py`

- Converts TerraClim NetCDF → monthly GeoTIFFs, clips to bbox, resamples
- **⚠️ MUST change the following before running:**
  - Change `BBOX` to the Brazil bbox: `(-94.1875, -39.0208, 37.0625, 18.2292)`
  - Change `OUTPUT_DIR` to your local Brazil output folder
  - Change `INPUT_ROOT` to where you downloaded the 2026 NetCDFs
  - Change `TARGET_RES` to `"0.041666666666666664"` (TerraClim native — do NOT use 0.02°, causes data loss per poorna notes)
- Output naming: `terraclim_<var>_2026_MM.tif`

> ❌ Do NOT use: `Data-Upload/preprocess_terraclim.py` — identical script but placed in wrong folder, both are Indonesia-configured out of the box. The one in `Data-Processing/` is preferred.

> ⚠️ **Resolution warning from poorna notes:** Do NOT resample TerraClim to 0.02°. Use its native resolution `0.041666666666666664°`. Downsampling to 0.02° causes data loss and spatial coverage errors.

> ⚠️ **Bbox warning from poorna notes:** Ensure bbox order is `(minX, minY, maxX, maxY)` = `(-94.1875, -39.0208, 37.0625, 18.2292)`. A reversed minX/maxX caused the entire 2025 upload to fail — all rasters fell outside the query region.

### Step 4 — Upload
**Script:** `Data-Upload/upload_terraclim.py`

- **⚠️ MUST change before running:**
  - Change `DB_NAME` from `covariables_indonesia` to `covariablesv1`
  - Change `INPUT_DIR` to your Brazil-processed TerraClim folder
- Uses parallel workers, appends to existing `terraclim_data` table
- Automatically creates yearly partition `terraclim_data_2026`

> ❌ Do NOT use: `Data-Upload/uploadchirps.bat` — wrong dataset and wrong database

---

## Dataset 3: NASA Power (Monthly, 47 Variables)

**Table:** `np_data` | **Cadence:** Monthly | **Output:** `<var>_YYYY_MM.tif`

### Step 1 — Download
**Script:** `Data-Download/download_nasapower.py`

- ✅ Already Brazil-specific (correct Brazil bbox in script)
- Downloads from NASA S3 ZARR store — no authentication needed
- Update `TIME_START = "2026-01-01"` and `TIME_END = "2026-12-31"` for 2026
- Update `OUTPUT_DIR` to your local path
- Downloads all 47 variables as individual NetCDF files

> Alternative: `Data-Download/Brazil/DownloadNASAPOWER.ipynb` — notebook version of the same download, also works

### Step 2 — Unpack
**Script:** `Data-Unpacking/unpack_nasapower_monthly.py`

- Converts per-variable NetCDF (daily data) → monthly aggregated GeoTIFFs
- Update `DATA_DIR` to your downloaded NetCDF folder
- Update `OUTPUT_BASE_DIR` to your output path
- Output pattern: `<var_name>/<var_name>_2026_MM.tif`

> Note: NASA Power data from GEE is already monthly. If you used the GEE notebook to download, you may not need this step — check if your files are already monthly GeoTIFFs or daily NetCDFs.

### Step 3 — Process (Resample)
**Script:** `Data-Processing/preprocess_nasapower.py`

- ✅ Labeled "Brazil 2025" — uses Brazil bbox coords
- Converts NetCDF → GeoTIFF using `gdal_translate`, then resamples via `gdalwarp`
- Update `INPUT_DIR` and `OUTPUT_DIR` to your 2026 paths
- Native NASA Power resolution is 1° — kept as-is (no downsampling to 0.02°)
- Uses 16 parallel workers

> Note: If you used `unpack_nasapower_monthly.py` in Step 2 and already have monthly GeoTIFFs, this step may be redundant. Check your files — if they are already GeoTIFF at 1° resolution and clipped to Brazil, skip this step.

### Step 4 — Upload
**Script:** `Data-Upload/upload_nasapower.py`

- **⚠️ MUST change before running:**
  - Change `DB_CONFIG['database']` from `covariables_indonesia` to `covariablesv1`
  - Change `INPUT_DIR` to your Brazil NASA Power GeoTIFF folder
  - Change `TABLE_NAME` to `np_data_2026` (or `np_data` if using append without partitioning)
- Uses parallel workers for upload

> ⚠️ From poorna notes: The working Brazil 2025 upload used flags `-s 4326` (SRID) and `-N -9999` (NoData). Verify these are set in the upload script.

> ❌ Do NOT use: `Data-Upload/uploadnasapower.bat` — targets `covariables_indonesia`

---

## Dataset 4: SPEI (Monthly Drought Index)

**Table:** `spei_data` | **Cadence:** Monthly | **Output:** `spei_2026_MM.tif`

### Step 1 — Download
**Script:** `Data-Download/Brazil/DownloadSPEIbase_GEE.ipynb`

- ✅ Brazil bbox configured in notebook
- Runs on Google Earth Engine
- GEE dataset: `CSIC/SPEI/2_10`, variable: `SPEI_01_month`
- Exports yearly stacks to Google Drive
- Update year range in the notebook for 2026

> ❌ Do NOT use: `Data-Download/download_spei.py` — Indonesia only

### Step 2 — Unpack
**Script:** `Data-Unpacking/unpack_yearly_stacks.py`

- Generic unpacker that handles SPEI yearly multi-band files → individual monthly files
- Call with `dataset_type='SPEI'` 
- Update `input_file` and `output_dir` arguments in the script
- Output naming: `spei_2026_MM.tif`

> Alternative: `Data-Unpacking/unpack_spei_yearly_to_monthly.py` — also unpacks SPEI yearly → monthly, but paths in the script are hardcoded to USA/non-Brazil locations. Update the `INPUT_DIR` and `OUTPUT_DIR` before using.

### Step 3 — Process (Resample)
**Script:** `Data-Processing/preprocess_spei.py`

- Resamples SPEI monthly files to 0.02°, sets NoData to -9999, CRS to EPSG:4326
- **⚠️ MUST change before running:**
  - Update `INPUT_DIR` to your Brazil SPEI unpacked folder
  - Update `OUTPUT_DIR` to your Brazil SPEI resampled folder
  - Script currently has USA paths — logic is identical, only paths differ

### Step 4 — Upload
**Script:** `Data-Upload/upload_spei.py`

- **⚠️ MUST change before running:**
  - Change `DB_CONFIG['database']` from `covariables_indonesia` to `covariablesv1`
  - Update `INPUT_DIR` to your Brazil resampled SPEI folder
- Table: `spei_data`, appends monthly records

> ❌ Do NOT use: `Data-Upload/uploadspei.bat` — targets `covariables_indonesia`

---

## Dataset 5: ET — Evapotranspiration (MODIS, 8-day)

**Table:** `et_data` | **Cadence:** 8-day | **Output:** `modis_et_YYYY_MM_DD.tif`

### Step 1 — Download
**Script:** `Data-Download/Brazil/DownloadMODIS_GEE.ipynb`

- ✅ Brazil bbox configured in notebook
- GEE dataset: `MODIS/061/MOD16A2GF`, band: `ET`
- Exports one GeoTIFF per 8-day period to Google Drive folder `GEE_ET_BBOX/`
- Update `start_date` and `end_date` for 2026
- Exports ~46 images for a full year (8-day composites)

### Step 2 — Unpack
**Not needed.** The GEE notebook exports individual 8-day files directly — no yearly stack to unpack.

> If you chose to export as yearly stacks: use `Data-Unpacking/unpack_et_indonesia.py` (logic is generic — update `INPUT_DIR`, `OUTPUT_DIR`, `START_YEAR`, `END_YEAR` to Brazil paths and 2026)

### Step 3 — Process (Resample)
**No dedicated Python script for Brazil.** Use `gdalwarp` directly or the batch file logic:

```bash
gdalwarp -tr 0.02 0.02 -r bilinear -co COMPRESS=LZW -co TILED=YES \
  -ot Float32 -srcnodata -9999.0 -dstnodata -9999.0 \
  -t_srs EPSG:4326 input.tif output.tif
```

- Target resolution: `0.02°`
- NoData: `-9999.0`
- Resampling: bilinear
- CRS: EPSG:4326
- Original CRS from GEE export: EPSG:6842 — gdalwarp will reproject automatically

> `Data-Processing/resamplinget.bat` exists but is configured for Indonesia paths. You can use it as a template — update the paths and run in an OSGeo4W/QGIS shell.

### Step 4 — Upload
**Script:** `Data-Upload/upload_modis.py`

- **⚠️ MUST change before running:**
  - Change `DB_NAME` from `covariables_indonesia` to `covariablesv1`
  - Update `OUTPUT_DIR` to your Brazil resampled ET folder
- Table: `et_data`, appends 8-day records with `date_id`
- Creates yearly partitions automatically

> ❌ Do NOT use: `Data-Upload/uploadet.bat` — targets `covariables_indonesia`

---

## Dataset 6: ERA5-Land (Daily, 15 Variables)

**Table:** `era5_data` | **Cadence:** Daily | **Output:** `ERA5_BBOX_YYYY-MM-DD.tif`

### Step 1 — Download
**Script:** `Data-Download/Brazil/DownloadERA5Land_GEE.ipynb`

- ✅ Brazil bbox configured in notebook
- GEE dataset: `ECMWF/ERA5_LAND/DAILY_AGGR`, 15 variables
- Exports one multi-band GeoTIFF per day to Google Drive folder `GEE_Exports_BBOX/`
- Update `start_date` and `end_date` to cover 2026
- ⚠️ This produces 365 files — expect a lot of GEE tasks

### Step 2 — Unpack
**Not needed.** GEE exports individual daily files with all 15 bands. No yearly stack.

### Step 3 — Process (Resample)
**No dedicated Python script for Brazil.** Use `gdalwarp` on each daily file:

```bash
gdalwarp -tr 0.02 0.02 -r bilinear -co COMPRESS=LZW -co TILED=YES \
  -ot Float32 -srcnodata -9999.0 -dstnodata -9999.0 \
  -t_srs EPSG:4326 ERA5_BBOX_2026-01-01.tif ERA5_BBOX_2026-01-01_resampled.tif
```

> `Data-Processing/resamplingera5.bat` exists but uses Indonesia paths. Use as a template — update paths and run in OSGeo4W shell.

### Step 4 — Upload
**Script:** `Data-Upload/upload_era5.py`

- **⚠️ MUST change before running:**
  - Change `DB_CONFIG['database']` from `covariables_indonesia` to `covariablesv1`
  - Update `ERA5_FOLDER` to your Brazil resampled ERA5 folder
- Handles multi-band files (15 bands per day = 15 separate rows in the table)
- Uses 16 parallel workers

> ❌ Do NOT use: `Data-Upload/uploadera5.bat` — targets `covariables_indonesia`

---

## Script Quick Reference

| Dataset | Download | Unpack | Process | Upload |
|---------|----------|--------|---------|--------|
| CHIRPS | `Data-Download/Brazil/DownloadCHIRPS_GEE.ipynb` | `Data-Unpacking/unpack_chirps_yearly_to_daily.py` | `Data-Processing/resample_chirps.py` | `Data-Upload/upload_chirps_python.py` ✅ |
| TerraClim | `Data-Download/download_terraclimate.py` | N/A | `Data-Processing/preprocess_terraclim.py` ⚠️ change BBOX | `Data-Upload/upload_terraclim.py` ⚠️ change DB |
| NASA Power | `Data-Download/download_nasapower.py` ✅ | `Data-Unpacking/unpack_nasapower_monthly.py` | `Data-Processing/preprocess_nasapower.py` ✅ | `Data-Upload/upload_nasapower.py` ⚠️ change DB |
| SPEI | `Data-Download/Brazil/DownloadSPEIbase_GEE.ipynb` | `Data-Unpacking/unpack_yearly_stacks.py` | `Data-Processing/preprocess_spei.py` ⚠️ change paths | `Data-Upload/upload_spei.py` ⚠️ change DB |
| ET (MODIS) | `Data-Download/Brazil/DownloadMODIS_GEE.ipynb` | N/A | `gdalwarp` manually | `Data-Upload/upload_modis.py` ⚠️ change DB |
| ERA5-Land | `Data-Download/Brazil/DownloadERA5Land_GEE.ipynb` | N/A | `gdalwarp` manually | `Data-Upload/upload_era5.py` ⚠️ change DB |

**Legend:**
- ✅ = already configured for Brazil / covariablesv1, no changes needed
- ⚠️ = requires config changes before running (see dataset section above)
- N/A = step not needed for this dataset

---

## Scripts That Are Indonesia-Only — Do Not Use for Brazil

These exist in the repo but are **not** for the covariablesv1 Brazil database:

| Script | Reason to avoid |
|--------|----------------|
| `Data-Download/download_spei.py` | Indonesia bbox |
| `Data-Processing/preprocess_chirps.py` | Indonesia paths |
| `Data-Processing/preprocess_terraclim.py` (in Data-Upload folder) | Indonesia BBOX |
| `Data-Unpacking/unpack_et_indonesia.py` | Indonesia paths (can adapt, but update paths) |
| `Data-Unpacking/unpack_spei_yearly_to_monthly.py` | USA paths |
| `Data-Upload/upload_chirps.py` | `covariables_indonesia` DB |
| `Data-Upload/upload_era5.py` | `covariables_indonesia` DB (change DB name before use) |
| `Data-Upload/upload_modis.py` | `covariables_indonesia` DB (change DB name before use) |
| `Data-Upload/upload_nasapower.py` | `covariables_indonesia` DB (change DB name before use) |
| `Data-Upload/upload_spei.py` | `covariables_indonesia` DB (change DB name before use) |
| `Data-Upload/upload_terraclim.py` | `covariables_indonesia` DB (change DB name before use) |
| `Data-Upload/upload_worldclim.py` | `covariables_indonesia` DB |
| `Data-Upload/upload_soilgrids.py` | `covariables_indonesia` DB |
| All `*.bat` files in Data-Upload | `covariables_indonesia` DB |

---

## Common Config Changes Needed (All Upload Scripts Except CHIRPS)

When adapting any Indonesia upload script for Brazil, change these three things:

```python
# Change this:
'database': 'covariables_indonesia'
# To this:
'database': 'covariablesv1'

# Change INPUT_DIR to your local Brazil data path

# Always verify raster2pgsql uses append mode (-a), NOT create (-c) or drop (-d)
```

---

## Key Technical Notes from Previous Work

- **TerraClim resolution:** Use native `0.041666666666666664°`. Do not resample to 0.02° — causes bbox mismatch where rasters don't intersect query points.
- **CHIRPS shards:** GEE may export 2 files per year. Merge with `Data-Processing/Brazil-2025/chirps_merge.py` before unpacking.
- **Tiling in raster2pgsql:** When using `-t 100x100`, make sure the upload script captures ALL tile INSERT statements (use `re.findall()` not `re.search()`). Old scripts only captured tile #1 — see poorna notes for the fix.
- **raster2pgsql always needs:** `-s 4326` (set SRID) and `-N -9999` (set NoData) for all Brazil uploads.
- **Bbox format:** Always `(minX, minY, maxX, maxY)` = `(-94.1875, -39.0208, 37.0625, 18.2292)`. Do not swap min/max.
- **Verification after upload:**
  ```sql
  SELECT COUNT(*) FROM chirps_data WHERE date_id >= '2026-01-01';
  SELECT COUNT(*) FROM terraclim_data WHERE date_id >= '2026-01-01';
  -- Test a point query (Mato Grosso do Sul):
  SELECT COUNT(*) FROM chirps_data
  WHERE ST_Intersects(rast, ST_SetSRID(ST_Point(-52.46, -20.16), 4326))
  AND date_id >= '2026-01-01';
  ```

---

## Reference Docs

- `Data-Download/DownloadScriptsRD.md` — dataset specs (resolution, format, cadence)
- `Data-Processing/DataProcessingRD.md` — processing standards (0.02° target, nodata, CRS)
- `Data-Upload/DataUploadRD.md` — upload process and database notes
- `DOCUMENTATION/poorna_notes/2025_Data_Issues_Session_Notes.md` — detailed record of 2025 bugs and fixes; read before running TerraClim or CHIRPS
- `Data-Download/Brazil/README.md` — per-notebook download instructions for all Brazil datasets
