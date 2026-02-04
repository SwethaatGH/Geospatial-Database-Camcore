@echo off
setlocal enabledelayedexpansion

rem ========================================================================
rem ERA5-Land Daily Data Upload Script
rem ========================================================================
rem Uploads daily ERA5-Land multi-variable files to PostgreSQL/PostGIS
rem Input format: era5land_YYYY_MM_DD.tif (15 bands per file)
rem Table naming: era5land_YYYY_MM_DD (one table per daily file)
rem ========================================================================

rem Set PostgreSQL connection parameters
set DB_USER=XXXX
set DB_PASS=XXXX
set DB_HOST=localhost
set DB_PORT=5432
set DB_NAME=covariablesv1

rem Set the password for PostgreSQL
set PGPASSWORD=%DB_PASS%

echo ========================================================================
echo ERA5-Land Daily Data Upload to PostgreSQL
echo ========================================================================
echo Database: %DB_NAME%
echo Host:     %DB_HOST%:%DB_PORT%
echo User:     %DB_USER%
echo ========================================================================
echo.

rem Counter for progress tracking
set /a "TOTAL=0"
set /a "UPLOADED=0"
set /a "ERRORS=0"

rem Count total files
for %%f in (era5land_*.tif) do (
    set /a "TOTAL+=1"
)

echo Total files to upload: !TOTAL!
echo.
echo Starting upload process...
echo Note: Each file contains 15 bands (ERA5-Land variables)
echo This may take considerable time for ~12,000+ daily files.
echo.

rem Iterate through all era5land_*.tif files
for %%f in (era5land_*.tif) do (
    set "name=%%~nf"
    set /a "UPLOADED+=1"
    
    echo [!UPLOADED!/!TOTAL!] Uploading: !name!
    
    rem Upload the raster file with all 15 bands
    rem -s 4326: EPSG:4326 (WGS84)
    rem -I: Create spatial index
    rem -C: Apply constraints
    rem -M: Use VACUUM ANALYZE after upload
    rem -t 128x128: Tile size for efficient storage
    raster2pgsql -s 4326 -I -C -M -t 128x128 "%%f" public.!name! | psql -U %DB_USER% -d %DB_NAME% -h %DB_HOST% -p %DB_PORT% >nul 2>&1
    
    if !errorlevel! neq 0 (
        echo    ERROR: Failed to upload !name!
        set /a "ERRORS+=1"
    ) else (
        echo    SUCCESS: !name! uploaded
    )
)

echo.
echo ========================================================================
echo Upload Complete
echo ========================================================================
echo Total files:  !TOTAL!
echo Uploaded:     !UPLOADED!
echo Errors:       !ERRORS!
echo Database:     %DB_NAME%
echo Schema:       public
echo ========================================================================
echo.
echo ERA5-Land Variable Band Order in Each Table:
echo   Band 1:  evaporation_from_vegetation_transpiration_sum
echo   Band 2:  potential_evaporation_sum
echo   Band 3:  runoff_sum
echo   Band 4:  skin_temperature_mean
echo   Band 5:  snow_cover_mean
echo   Band 6:  snow_depth_mean
echo   Band 7:  snowfall_sum
echo   Band 8:  snowmelt_sum
echo   Band 9:  soil_temperature_level_1_mean
echo   Band 10: surface_pressure_mean
echo   Band 11: surface_solar_radiation_downwards_sum
echo   Band 12: temperature_2m_max
echo   Band 13: temperature_2m_mean
echo   Band 14: temperature_2m_min
echo   Band 15: total_precipitation_sum
echo ========================================================================

pause
