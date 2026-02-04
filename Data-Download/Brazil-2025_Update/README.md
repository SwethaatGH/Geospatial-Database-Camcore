# Brazil 2025 Data Update - Download Scripts

This folder contains Google Earth Engine (GEE) scripts for downloading 2025 data for Brazil.

## Database Target
- **Database**: `covariables2` (Brazil)
- **Port**: 5433
- **Region**: Brazil
- **Bounding Box**: (-94.1875, -39.0208, 37.0625, 18.2292)

## Data Sources for 2025 Update

### 1. CHIRPS (Precipitation)
- **File**: `DownloadCHIRPS_Brazil_2025.ipynb`
- **Dataset**: UCSB-CHG/CHIRPS/DAILY
- **Cadence**: Daily
- **Export Folder**: Brazil_CHIRPS_Daily
- **Status**: Ready to run for 2025

### 2. SPEI (Drought Index)
- **File**: `DownloadSPEI_Brazil_2025.ipynb`
- **Dataset**: CSIC/SPEI/2_10
- **Cadence**: Monthly (12-month scale)
- **Export Folder**: Brazil_SPEI_Monthly
- **Status**: Ready to run for 2025

### 3. MODIS ET (Evapotranspiration)
- **File**: `DownloadMODIS_Brazil_2025.ipynb`
- **Dataset**: MODIS/061/MOD16A2GF
- **Cadence**: 8-day
- **Export Folder**: Brazil_ET_8day
- **Status**: Ready to run for 2025

### 4. ERA5-Land (Climate Variables)
- **File**: `DownloadERA5Land_Brazil_2025.ipynb`
- **Dataset**: ECMWF/ERA5_LAND/DAILY_AGGR
- **Cadence**: Daily
- **Export Folder**: Brazil_ERA5_Daily
- **Status**: Ready to run for 2025

### 5. TerraClimate (Climate Variables)
- **Source**: Manual download from https://climate.northwestknowledge.net/TERRACLIMATE/
- **Cadence**: Monthly
- **Status**: Check if 2025 data available

## Workflow

1. **Run GEE Scripts**: Execute notebooks in Google Colab to export data to Google Drive
2. **Download to Local**: Sync Google Drive folders to local machine
3. **Process**: Use scripts in `Data-Processing/Brazil-2025/` to resample and format
4. **Upload**: Use scripts in `Data-Upload/Brazil-2025/` to append to covariables2 database

## Notes
- All scripts use Brazil bounding box
- Export folders are labeled with "Brazil" prefix for easy identification
- Year range is set to 2025 only - update as needed for future years
- Verify GEE project authentication before running
