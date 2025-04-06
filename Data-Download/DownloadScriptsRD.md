# Download Scripts/ Processes for databases

## 1. Download Notebooks 

### 1.1. WorldclimCovariables: 

---
- Downloaded all Worldclim global rasters (both 30 sec and 2.5 min resolution) and created covariables for desired location and date range.
- Execute all cells after replacing file path to root dir with desired download folder path. 
- **Do not rerun any download cells** as it takes a long time and would just rewrite your downloaded folders.

### 1.2. DownloadNasaPower: 

---
- Downloaded NASA power data as NETCDF files 
- To download monthly url used: [https://nasa-power.s3.us-west-2.amazonaws.com/syn1deg/temporal/power_syn1deg_monthly_temporal_lst.zarr](https://nasa-power.s3.us-west-2.amazonaws.com/syn1deg/temporal/power_syn1deg_monthly_temporal_lst.zarr)
- To download daily url used: [https://nasa-power.s3.us-west-2.amazonaws.com/syn1deg/temporal/power_syn1deg_daily_temporal_lst.zarr](https://nasa-power.s3.us-west-2.amazonaws.com/syn1deg/temporal/power_syn1deg_daily_temporal_lst.zarr)
- To download different region rasters for a different time frame modified:
`
ds_region = ds[var].sel(
                    lat=slice(minlat, maxlat),
                    lon=slice(minlon, maxlon),
                    time=slice("year-month-day", "year-month-day")
                )
`
### 1.3. WorldclimSoilGridsCovariables:
---
- Downloaded SoilGrids and make covariables for wordlcim and soil grids together 

### 1.4. DownloadMODIS_GEE:
---
- MOD16A2 downloaded from Google Earth Engine on Google Colab.
- GEE link: https://developers.google.com/earth-engine/datasets/catalog/MODIS_NTSG_MOD16A2_105

### 1.5. DownloadCHIRPS_GEE:
---
- CHIRPSDaily downloaded from Google Earth Engine on Google Colab.
- GEE link: https://developers.google.com/earth-engine/datasets/catalog/UCSB-CHG_CHIRPS_DAILY#bands

### 1.6. DownloadERA5Land_GEE:
---
- ERA5Land downloaded from Google Earth Engine on Google Colab.
- GEE link: https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_DAILY_AGGR

### 1.7. DownloadSPEIbase_GEE:
---
- SPEIbase downloaded from Google Earth Engine on Google Colab.
- GEE link: https://developers.google.com/earth-engine/datasets/catalog/CSIC_SPEI_2_10


## 2. Download Process 

### 2.1. Terraclim: 

---
- Downloaded all Terraclim NetCDFs from [https://climate.northwestknowledge.net/TERRACLIMATE/index_directDownloads.php](https://climate.northwestknowledge.net/TERRACLIMATE/index_directDownloads.php)


### 2.2. SoilGrids: 

---
- Downloaded all soilgrids global rasters from [https://www.isric.org/instruction-wms](https://www.isric.org/instruction-wms)


