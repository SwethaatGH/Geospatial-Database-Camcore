# Brazil 2025 Data Update - Processing Scripts

This folder contains scripts to resample and process raw 2025 Brazil data before database upload.

## Processing Requirements

All rasters must be:
- **CRS**: EPSG:4326 (WGS84)
- **Resolution**: 0.02 degrees (bilinear for continuous, nearest neighbor for categorical)
- **NoData**: -9999.0 (except TerraClimate: -32768)
- **Tile Size**: 128x128 for raster2pgsql

## Processing Scripts

### 1. CHIRPS Processing
- **Script**: `resample_chirps_brazil_2025.bat`
- **Input**: Raw CHIRPS yearly multi-band TIFFs from GEE
- **Process**: Unpack yearly to daily, resample to 0.02°
- **Output**: Individual daily TIFFs ready for upload

### 2. SPEI Processing
- **Script**: `resample_spei_brazil_2025.bat`
- **Input**: Raw SPEI monthly TIFFs from GEE
- **Process**: Resample to 0.02° (bilinear)
- **Output**: Monthly TIFFs ready for upload

### 3. ET Processing
- **Script**: `resample_et_brazil_2025.bat`
- **Input**: Raw MODIS ET 8-day TIFFs from GEE
- **Process**: Unpack if needed, resample to 0.02°, apply scale factor 0.1
- **Output**: 8-day TIFFs ready for upload

### 4. ERA5 Processing
- **Script**: `resample_era5_brazil_2025.bat`
- **Input**: Raw ERA5-Land daily TIFFs from GEE
- **Process**: Resample to 0.02° (bilinear)
- **Output**: Daily TIFFs per variable ready for upload

### 5. TerraClimate Processing
- **Script**: `process_terraclim_brazil_2025.bat`
- **Input**: NetCDF files from TerraClimate download
- **Process**: Convert NetCDF to GeoTIFF, resample to 0.02°
- **Output**: Monthly TIFFs per variable ready for upload

## GDAL/OSGeo4W Shell

Run all batch files in OSGeo4W Shell (comes with QGIS):
```
C:\Program Files\QGIS 3.x\OSGeo4W.bat
```

## Directory Structure
```
Q:\My Drive\
├── Brazil_CHIRPS_Daily\          # Raw GEE exports
├── Brazil_CHIRPS_Resampled\      # Processed
├── Brazil_SPEI_Monthly\
├── Brazil_SPEI_Resampled\
├── Brazil_ET_8day\
├── Brazil_ET_Resampled\
├── Brazil_ERA5_Daily\
├── Brazil_ERA5_Resampled\
└── Brazil_TerraClimate\
    └── Brazil_TerraClimate_Resampled\
```
