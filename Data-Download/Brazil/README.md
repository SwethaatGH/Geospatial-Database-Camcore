# Brazil Dataset Downloads

All notebooks in this folder download geospatial datasets clipped to the **Brazil bounding box** used across the Camcore pipeline.

**Bounding Box:** West = -94.1875, South = -39.0208, East = 37.0625, North = 18.2292 (EPSG:4326)

---

## Datasets

### 1. `DownloadCHIRPS_GEE.ipynb` — CHIRPS Daily Precipitation

- **Source:** Google Earth Engine — `UCSB-CHG/CHIRPS/DAILY`
- **Output:** One multi-band GeoTIFF per year (365/366 bands = 1 band per day), exported to Google Drive folder `Brazil_CHIRPS_Daily`
- **Temporal coverage:** Configurable — edit the `years` list in the notebook
- **Variable:** `precipitation` (mm/day)
- **Resolution:** ~5 km (scale=5000m in GEE export)

**Instructions:**
1. Authenticate GEE: run the `ee.Authenticate()` and `ee.Initialize(project='ee-camcoredatabase')` cells
2. Set the `years` list to the year(s) you want, e.g. `years = list(range(2025, 2026))` for 2025
3. Run all cells — GEE export tasks will be submitted
4. Monitor task progress in the [GEE Task Manager](https://code.earthengine.google.com/tasks)
5. Download the exported files from Google Drive → `Brazil_CHIRPS_Daily/`
6. To unpack yearly multi-band files into daily GeoTIFFs, use `Unpacking/unpack_chirps_yearly_to_daily.py`

> **Note:** After downloading, raw files are yearly stacks. The Unpacking scripts (at the repo root level) must be run before uploading to the database.

---

### 2. `DownloadERA5Land_GEE.ipynb` — ERA5-Land Daily Aggregates

- **Source:** Google Earth Engine — `ECMWF/ERA5_LAND/DAILY_AGGR`
- **Output:** One GeoTIFF per day, exported to Google Drive folder `GEE_Exports_BBOX`
- **Temporal coverage:** 1990-01-01 to 2024-12-31 (edit `start_date` / `end_date` to change)
- **Variables (15):**
  - `temperature_2m`, `skin_temperature`
  - `soil_temperature_level_1/2/3`
  - `volumetric_soil_water_layer_1/2/3`
  - `u_component_of_wind_10m`, `v_component_of_wind_10m`
  - `surface_pressure`, `total_precipitation_sum`
  - `surface_latent_heat_flux_sum`, `surface_net_solar_radiation_sum`
  - `evaporation_from_vegetation_transpiration_sum`
- **Resolution:** ~10 km (scale=10000m)

**Instructions:**
1. Authenticate GEE
2. Adjust `start_date` and `end_date` if downloading a specific range
3. Run all cells — one GEE export task is submitted per day × variable
4. Monitor task progress in the GEE Task Manager (expect a large number of tasks)
5. Download results from Google Drive → `GEE_Exports_BBOX/`

---

### 3. `DownloadMODIS_GEE.ipynb` — MODIS Evapotranspiration (ET)

- **Source:** Google Earth Engine — `MODIS/061/MOD16A2GF`
- **Output:** One GeoTIFF per 8-day composite, exported to Google Drive folder `GEE_ET_BBOX`
- **Temporal coverage:** 2000-01-01 to 2024-12-31
- **Variable:** `ET` (Evapotranspiration, kg/m²/8day)
- **Resolution:** 500 m (MODIS native)

**Instructions:**
1. Authenticate GEE
2. Adjust `start_date` / `end_date` if needed
3. Run all cells — one GEE export task per 8-day image
4. Download results from Google Drive → `GEE_ET_BBOX/`
5. Use `Unpacking/unpack_et_indonesia.py` if additional band extraction is needed

---

### 4. `DownloadNASAPOWER.ipynb` — NASA POWER (Daily & Monthly)

- **Source:** NASA POWER S3 ZARR stores (direct HTTP, no authentication needed)
  - Monthly: `https://nasa-power.s3.us-west-2.amazonaws.com/syn1deg/temporal/power_syn1deg_monthly_temporal_lst.zarr`
  - Daily: `https://nasa-power.s3.us-west-2.amazonaws.com/syn1deg/temporal/power_syn1deg_daily_temporal_lst.zarr`
- **Output:** Per-variable NetCDF files saved to the working directory
- **Temporal coverage:** Configurable — edit the `time=slice(...)` parameters
- **Variables (47+):** Includes radiation, temperature, precipitation, aerosols, cloud cover, and more. See the `Subset of Variables` section in the notebook for the full list.
- **Region subset (Brazil bbox):**
  ```python
  lat=slice(-38.6, 17.81),
  lon=slice(-93.75, 36.65)
  ```

**Instructions:**
1. Install dependencies: run the `%pip install` cells
2. To download a specific subset of variables, use the `get_power_data(url, var)` loop in the *Subset of Variables* section
3. To download all variables at once, use the `get_power_data(url)` function in the *All variables* section
4. To change the date range, modify the `time=slice("YYYY-MM-DD", "YYYY-MM-DD")` parameter
5. Output NetCDF files are saved as `<VAR_NAME>.nc` in the current directory
6. Use `Unpacking/unpack_nasapower_monthly.py` to convert NetCDF files to monthly GeoTIFFs

> **Note:** The notebook has two approaches for opening the ZARR store (direct and fsspec fallback) — if one fails, the other runs automatically.

---

### 5. `DownloadSPEIbase_GEE.ipynb` — SPEI (Standardized Precipitation-Evapotranspiration Index)

- **Source:** Google Earth Engine — `CSIC/SPEI/2_10`
- **Output:** GeoTIFFs exported to Google Drive
- **Variable:** SPEI (drought index, dimensionless)

**Instructions:**
1. Authenticate GEE
2. Run all cells to submit export tasks
3. Download results from Google Drive

---

### 6. `WorldclimCovariables.ipynb` — WorldClim Climate Covariables

- **Source:** WorldClim v2.1 (direct HTTP download from UC Davis)
  - 30-second resolution: `https://geodata.ucdavis.edu/climate/worldclim/2_1/base/wc2.1_30s_<type>.zip`
  - 2.5-minute historical: `https://geodata.ucdavis.edu/climate/worldclim/2_1/hist/cts4.06/2.5m/`
- **Variables downloaded:** `bio` (19 bioclimatic variables), `prec`, `tmin`, `tmax`
- **Output:** Covariable CSV per location/date range with seasonal statistics and bioclimatic indices

**Instructions:**
1. Run `%pip install` cells to install dependencies
2. **Section 3 (30s resolution):** Replace `ReplaceWithYourPath` in `root_dir` with your actual download directory path
3. Run the download cells to fetch global WorldClim ZIP files — **do not rerun download cells** once downloaded as files are large
4. Run `unzip_and_cleanup()` to extract downloaded ZIPs
5. Set your bounding box (`lat_min`, `lat_max`, `lon_min`, `lon_max`) to your area of interest
6. **Section 4 (2.5m historical):** Update `root_dir` and run `download_data()` for historical monthly data
7. Run the covariable computation cells to produce seasonal precipitation, temperature, and bioclimatic index outputs
8. Final output is saved as a CSV

> **Do NOT rerun download cells** — the WorldClim global files are large and take a long time. Only run download cells once.

---

### 7. `WorldclimSoilGridsCovariables.ipynb` — WorldClim + SoilGrids Combined Covariables

- **Source:** WorldClim 2.5m + SoilGrids WCS API (`https://maps.isric.org`)
- **Output:** `required_view_soil_worldclim.csv` — one row per location/date range with WorldClim and soil covariables
- **SoilGrids variables (15):** `ocd`, `ocs`, `bdod`, `clay`, `cfvo`, `sand`, `silt`, `wv0010`, `wv0033`, `wv1500`, `cec`, `nitrogen`, `soc`, `phh2o`, `wrb`
- **Requires:** Pre-downloaded WorldClim 2.5m files (see `WorldclimCovariables.ipynb`) and a `Camcore_Pine_dataset.csv` input file

**Instructions:**
1. Ensure WorldClim 2.5m files are already downloaded (see notebook 6 above)
2. Place `Camcore_Pine_dataset.csv` in the working directory
3. Update `root_dir` to point to your WorldClim 2.5m folder
4. Run all cells — the notebook loops over all unique lat/lon locations in the dataset, downloads SoilGrids tiles on the fly, and computes covariables
5. Output: `required_view_soil_worldclim.csv`

---

## Key Notes

- All datasets use the same Brazil bounding box: `(-94.1875, -39.0208, 37.0625, 18.2292)`
- GEE notebooks require authentication with `ee-camcoredatabase` GEE project
- After downloading raw files, run the appropriate **Unpacking** scripts (located at the repo root `Unpacking/` folder) before uploading to the PostGIS database
- **Do not rerun WorldClim download cells** — those downloads are large and slow
- NASA POWER notebooks require no authentication — data is publicly available on S3

## Post-Download Pipeline

```
Download (this folder)
        ↓
Unpack / Preprocess (Unpacking/ at repo root, or Data-Processing/Brazil/)
        ↓
Upload to PostGIS (Data-Upload/Brazil/)
```
