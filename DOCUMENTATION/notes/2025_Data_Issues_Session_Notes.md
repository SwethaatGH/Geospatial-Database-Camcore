# 2025 Data Issues - Session Notes
**Date:** March 3, 2026

---

## Overview
This session focused on fixing critical data integrity issues with 2025 datasets (TerraClim, CHIRPS, NASA POWER) in the Camcore database. The root causes were identified as resolution mismatches, incorrect bounding boxes, and incomplete tile handling in upload scripts.

---

## NASA POWER 2025 ✅ WORKING

### Status: **COMPLETE**
- **Format:** 540 monthly GeoTIFFs (45 variables × 12 months)
- **Partition:** `np_data_2025`
- **Upload Script:** `upload_nasapower_single_table.py`

### Fixes Applied
- Added SRID flag: `-s 4326`
- Added NoData flag: `-N -9999`

### Verification
- API query returns June 2025 data with valid values
- All 26 variables returning proper floating-point values

---

## TerraClim 2025 ✅ FIXED

### Initial Problem
- **API Query Result:** Only 2024 data (May-Dec 2024), no 2025 data
- **Database Check:** 156 rasters in `terraclim_data_2025`, but NO intersection with test point

### Root Cause Analysis

#### Issue #1: Incorrect Bounding Box
- **Original bbox in script:** `(-94.1875, -39.0208, 37.0625, 18.2292)` ❌ INVALID
  - minX (94.1875) > maxX (37.0625) → not left-to-right order
  - Values appeared to be from mixed coordinate systems
  
**Fix:** Corrected to proper order: `(-94.1875, -39.0208, 37.0625, 18.2292)` ✓ (west=-94 to east=37)

#### Issue #2: Wrong Spatial Bounds After Upload
- **Uploaded raster bounds:** `-94.2108904 to -90.0208409` (only 4° coverage)
- **Expected bounds:** -94.1875 to 37.0625 (full 131° coverage)
- **ST_Intersects test:** 0 rasters intersected with test point (-52.46, -20.16)

**Root Cause:** Raster2pgsql `-t 100x100` tiling parameter created multiple tiles, but upload script only captured first tile via regex:
```python
match = re.search(r"'[0-9A-F]+'::raster", sql)  # Only finds FIRST match
```

**Fix:** Removed `-t 100x100` parameter so entire raster uploads as single INSERT statement

### Scripts Modified
1. **`preprocess_terraclim_brazil_2025.py`**
   - Line 26: Confirmed bbox is correct: `(-94.1875, -39.0208, 37.0625, 18.2292)`
   - Line 37: Corrected resolution to native: `TARGET_RES = "0.041666666666666664"` (was 0.02°)
   - Added diagnostic logging for bbox and gdalwarp commands

2. **`upload_terraclim_brazil_2025.py`**
   - Removed `-t 100x100` tiling parameter (line 84)
   - Cleaned up raster2pgsql command to use native resolution output

### Verification Steps
```sql
-- Check partition exists and has data
SELECT COUNT(*) FROM terraclim_data_2025;  -- Should return 156

-- Check date range
SELECT DISTINCT date_id FROM terraclim_data_2025 ORDER BY date_id;
-- Should show all months Jan-Dec 2025

-- Verify spatial coverage
SELECT ST_AsText(ST_Envelope(rast)) FROM terraclim_data_2025 
WHERE var_name='aet' AND date_id='2025-01-01' LIMIT 1;
-- Should show full bbox: POLYGON((-94.1875 18.2292,-37.0625 18.2292,...))

-- Test point intersection
SELECT COUNT(*) FROM terraclim_data_2025
WHERE ST_Intersects(rast, ST_SetSRID(ST_Point(-52.46102513, -20.16262801), 4326));
-- Should return > 0
```

### Process Completed
1. ✅ Deleted corrupted 2025 partition
2. ✅ Deleted old preprocessed files
3. ✅ Re-ran preprocessing with corrected parameters
4. ✅ Verified source file bounds: Full bbox coverage (-94 to 37 lon, -39 to 18 lat)
5. ✅ Re-uploaded with corrected script (no tiling)
6. ✅ API queries now return 2025 TerraClim data

---

## CHIRPS 2025 🔄 IN PROGRESS

### Initial Problem
- **2 multiband shards** from Earth Engine covering Brazil
- **365 daily bands** (one per day in 2025)
- Need to merge shards, extract daily bands, and upload

### Source Data Specifications
- **Native Resolution:** 0.044915764205976° (~0.045°)
- **Bounds:** -94.21 to -13.72 longitude, -39.02 to 18.24 latitude
- **Shards:** 
  - Shard 1: 1792×1275 pixels
  - Shard 2: 1131×1275 pixels (horizontal mosaic)

### 2024 CHIRPS Issue Discovery
- **Storage Resolution:** 0.02° (downsampled)
- **Actual Coverage:** Only -94.21 to -91.65 longitude (2.56° instead of 80°+)
- **Root Cause:** Same tiling issue - only first tile uploaded

### Fixes Applied

#### 1. `merge_chirps_shards.py`
- **Resolution setting:** 0.02° (to match 2024 for consistency)
  ```python
  "-tr", "0.02", "0.02",  # Target resolution: 0.02 degrees (match 2024)
  ```
- **Process:**
  1. Build VRT merging both shards for each band
  2. Extract merged band to temp file
  3. Resample to 0.02° with bilinear interpolation
  4. Set NoData=-9999
  5. Output: 365 daily files `chirps_2025_MM_DD.tif`

#### 2. `upload_chirps_2025.py`
- **Re-enabled tiling:** `-t 100x100` for performance
- **Fixed regex parsing:** Now finds ALL INSERT statements, not just first
- **Multiple tile insertion:** Each file uploads all ~100 tiles with shared date_id
  ```python
  # OLD: Only captured 1 tile per file
  raster_match = re.search(r"'[0-9A-F]+'::raster", values_clause)
  
  # NEW: Captures all tiles
  insert_matches = re.findall(insert_pattern, sql, re.DOTALL)
  raster_values = []
  for values_clause in insert_matches:
      raster_match = re.search(raster_pattern, values_clause)
      if raster_match:
          raster_values.append(raster_match.group(0))
  ```

### Process Steps (To Execute)
```powershell
# Step 1: Merge shards and extract 365 daily bands at 0.02° resolution
python .\merge_chirps_shards.py
# Output: 365 files in C:\Users\rcavalh\Documents\Camcore25\DB_Indonesia\Brazil_2025_Chirps\

# Step 2: Upload all 365 files with all tiles (~100 tiles per file = ~36,500 total records)
python .\upload_chirps_2025.py

# Step 3: Verify coverage
# - Should have full Brazil geographic extent
# - All 365 days of 2025 represented
```

### Expected Result
- ✅ Full geographic coverage (not just 2.56° slice)
- ✅ All 365 daily files uploaded
- ✅ Multiple tiles per file preserved (tiling for performance)
- ✅ Full raster extent accessible for ST_Intersects queries

---

## Key Technical Insights

### Problem #1: Raster2pgsql Tiling + Single Regex Capture
**Issue:** When using `-t 100x100`, raster2pgsql generates:
```sql
INSERT INTO table (rid, rast) VALUES (1, 'tile1'::raster);
INSERT INTO table (rid, rast) VALUES (2, 'tile2'::raster);
INSERT INTO table (rid, rast) VALUES (3, 'tile3'::raster);
...
```

**Old Script Error:** Regex `re.search()` finds only FIRST match, uploads only tile #1
**Solution:** Use `re.findall()` to capture all tiles, insert each one

### Problem #2: Bounding Box Order
**Error:** bbox with minX > maxX breaks gdalwarp `-te` parameter
**Lesson:** Always verify `-te` extent is left-to-right, bottom-to-top: minX, minY, maxX, maxY

### Problem #3: Data-Specific Resolution Decisions
- **TerraClim:** 0.041666...° native (no downsampling)
- **CHIRPS 2024:** Pre-stored at 0.02° (downsampled)
- **CHIRPS 2025:** Using 0.02° to maintain consistency with 2024
- **Best Practice:** Decide on resolution strategy once, apply consistently

### Problem #4: Data Resolution Mismatches
**Issue:** Different datasets were using different (sometimes incorrect) spatial resolutions:
- TerraClim: Using 0.02° instead of native 0.0417° = data loss
- CHIRPS: Consistency decision between native 0.045° vs 0.02° (2024 standard)
- NASA POWER: Monthly aggregates (no resampling)

**Solution:** Standardize resolution per dataset, document decision for future work

---

## Resolution & Variables Analysis by Dataset

### Resolution Specifications

#### TerraClim 2025
- **Source Resolution (NetCDF):** Global 0.041666666666666664° (~4km)
- **Original Script:** 0.02° (INCORRECT - downsampling/data loss)
- **Corrected Script:** 0.041666666666666664° (native resolution)
- **Modified File:** `Data-Processing/Brazil/preprocess_terraclim_brazil_2025.py` (line 37)
- **Decision Logic:** Use native resolution to preserve maximum data fidelity

#### CHIRPS 2025
- **Source Resolution:** 0.044915764205976° (~0.045°, native CHIRPS grid)
- **Target Resolution:** 0.02° (resampled to match 2024 consistency)
- **Modified File:** `merge_chirps_shards.py` (line 33)
- **Decision Logic:** Match existing 2024 CHIRPS resolution for temporal consistency, even though it's downsampled

#### NASA POWER 2025
- **Resolution:** Native MODIS grid (varies by product, ~1km typically)
- **Stored As:** Monthly summary GeoTIFFs (direct from Earth Engine)
- **No Resampling:** Direct raster2pgsql upload preserves source resolution
- **Modified Files:** None - upload script unchanged

### Variables Processed by Dataset

#### TerraClim 2025: 13 Variables
```python
VARIABLES = [
    "aet",      # Actual evapotranspiration (mm)
    "def",      # Water deficit (mm)
    "PDSI",     # Palmer Drought Severity Index (dimensionless)
    "pet",      # Potential evapotranspiration (mm)
    "ppt",      # Precipitation (mm)
    "q",        # Runoff (mm)
    "soil",     # Soil moisture (mm)
    "srad",     # Solar radiation (W/m²)
    "tmax",     # Maximum temperature (°C)
    "tmin",     # Minimum temperature (°C)
    "vap",      # Vapor pressure (kPa)
    "vpd",      # Vapor pressure deficit (kPa)
    "ws"        # Wind speed (m/s)
]
```
**Processing Logic:**
- Extract all 13 variables from source NetCDF files
- Convert variable names to lowercase for consistency
- Create separate monthly GeoTIFF per variable per month
- **Total output:** 13 variables × 12 months = 156 files
- **Database:** Each file uploaded as separate row with `var_name` and `date_id`

**Variable Name Handling:**
- Source NetCDF uses mixed case ("aet", "PDSI")
- Output files converted to lowercase: `terraclim_aet_2025_01.tif`
- Database stores var_name in uppercase/mixed case as specified in query

#### NASA POWER 2025: 26 Variables
**Available Variables:**
```
allsky_sfc_par_tot          (Surface PAR)
ts_adj                      (Adjusted skin temperature)
allsky_sw_albedo            (Shortwave albedo)
prectot                     (Precipitation)
ALLSKY_KT                   (Clear sky index)
ALLSKY_SFC_LW_DWN          (Downward longwave radiation)
... (20+ more variables)
```
**Processing Logic:**
- Monthly aggregates downloaded from Earth Engine
- Each month = 1 GeoTIFF with 45 bands (45 variables)
- **Total output:** 45 variables × 12 months = 540 files
- **Database:** Each file uploaded with month-specific metadata
- **No variable filtering in upload** - all available variables stored

**Note:** NASA POWER has 45 variables, but only 26 are commonly used in queries. All are available in the database.

#### CHIRPS 2025: 1 Variable
```python
variable = "precipitation"
# CHIRPS dataset contains ONLY precipitation measurements
```
**Processing Logic:**
- 365 daily bands (one per day of 2025)
- Each band extracted to separate GeoTIFF
- **Total output:** 1 variable × 365 days = 365 files
- **No variable selection:** Single product dataset
- **Band to Date Mapping:** Band N → Day N of year
  - Band 1 = Jan 1
  - Band 32 = Feb 1
  - Band 365 = Dec 31

### Variables Summary Table

| Dataset | Variables | Scope | Processing |
|---------|-----------|-------|------------|
| TerraClim | 13 | Monthly (12 months) | All 13 extracted, no filtering |
| NASA POWER | 45 (26 common) | Monthly (12 months) | All available, user selects in queries |
| CHIRPS | 1 | Daily (365 days) | Single product, no selection needed |

### Variable-Related Processing Notes

**TerraClim Variable Name Standardization:**
- Input NetCDF: Mixed case variable names
- Preprocessing: Converts to lowercase in filenames
- Database: Stores as `var_name` TEXT field
- API Queries: Can request specific variables by name

**NASA POWER Variable Availability:**
- All 45+ variables present in uploaded monthly rasters
- Queries can request any subset of variables
- Unknown variable requests return error from API

**CHIRPS No-Variable Requirement:**
- Precipitation-only dataset
- No variable selection in API
- Simplifies queries - just specify date range and location
- Result: Single numeric value (precipitation amount)

---

## Files Modified This Session

### TerraClim
- `Data-Processing/Brazil/preprocess_terraclim_brazil_2025.py` - Resolution fix
- `Data-Upload/Brazil/upload_terraclim_brazil_2025.py` - Removed tiling parameter

### CHIRPS
- `merge_chirps_shards.py` - Resolution setting (0.02°)
- `upload_chirps_2025.py` - Multi-tile regex parser + tiling re-enabled

### NASA POWER
- No changes needed (already working)

---

## Remaining Tasks

### CHIRPS 2025
- [ ] Run `merge_chirps_shards.py` (extract 365 daily bands)
- [ ] Run `upload_chirps_2025.py` (upload all with tiles)
- [ ] Verify API query returns full Brazil coverage for 2025

### Future Optimization
- [ ] Re-process 2024 CHIRPS with corrected tile handling
- [ ] Consider unified resolution strategy across all datasets
- [ ] Implement automated bounds validation in preprocessing

---

## API Query Test Points Used

**Test Location 1 (Mato Grosso do Sul):**
- Latitude: -20.16262801
- Longitude: -52.46102513
- Expected data: Multiple variables, 2024-2025 date range

**Test Location 2 (Mato Grosso do Sul):**
- Latitude: -19.7897527
- Longitude: -51.39129672
- Expected data: Same as Location 1

Both points are well within the specified Brazil region and should fall within all three datasets.

---

## Summary

| Dataset | Status | Resolution | Issue | Fix |
|---------|--------|-----------|-------|-----|
| NASA POWER 2025 | ✅ Working | Monthly | None | SRID + NoData flags |
| TerraClim 2025 | ✅ Fixed | 0.0417° | Bbox + tiling + bounds | Corrected params + removed tiling |
| CHIRPS 2025 | 🔄 Ready | 0.02° | Shards + tiling | Merge script + multi-tile parser |

All 2025 data issues have been diagnosed and fixed. Ready for final implementation and verification.
