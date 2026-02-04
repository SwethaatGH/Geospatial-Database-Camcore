@echo off
setlocal enabledelayedexpansion

rem ========================================================================
rem ERA5-Land Daily Data Resampling Script
rem ========================================================================
rem Processes daily ERA5-Land multi-variable files (15 bands per file)
rem Input format: era5land_YYYY-MM-DD.tif (from unpacking script)
rem Output format: era5land_YYYY_MM_DD.tif (resampled to 0.02 degrees)
rem ========================================================================

rem Define input and output directories
set "INPUT_DIR=Q:\My Drive\Indonesia_ERA5_Daily"
set "OUTPUT_DIR=C:\Users\rcavalh\Documents\Camcore25\DB_Indonesia\Indonesia_ERA5_Daily_resampled"

rem Create output directory if it doesn't exist
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

echo ========================================================================
echo ERA5-Land Daily Resampling
echo ========================================================================
echo Input:  %INPUT_DIR%
echo Output: %OUTPUT_DIR%
echo Target Resolution: 0.02 degrees (EPSG:4326)
echo ========================================================================
echo.

rem Counter for progress tracking
set /a "TOTAL=0"
set /a "PROCESSED=0"
set /a "SKIPPED=0"
set /a "ERRORS=0"

rem Count total files
for %%f in ("%INPUT_DIR%\era5land_*.tif") do (
    set /a "TOTAL+=1"
)

echo Total files to process: !TOTAL!
echo.

rem Iterate through all era5land_*.tif files in the input directory
for %%f in ("%INPUT_DIR%\era5land_*.tif") do (
    rem Extract the filename without extension (e.g., era5land_2020-01-15)
    set "FILENAME=%%~nf"

    rem Extract the date part from the filename (e.g., 2020-01-15)
    rem The filename format is: era5land_YYYY-MM-DD
    set "FULLNAME=!FILENAME!"
    set "DATE=!FULLNAME:~9!"

    rem Extract year, month, and day from the date (YYYY-MM-DD)
    set "YEAR=!DATE:~0,4!"
    set "MONTH=!DATE:~5,2!"
    set "DAY=!DATE:~8,2!"

    rem Construct the new filename in the format era5land_YYYY_MM_DD.tif
    set "NEW_FILENAME=era5land_!YEAR!_!MONTH!_!DAY!.tif"

    rem Check if output file already exists
    if exist "%OUTPUT_DIR%\!NEW_FILENAME!" (
        set /a "SKIPPED+=1"
        echo [!SKIPPED!/!TOTAL!] Skipping: !NEW_FILENAME! ^(already exists^)
    ) else (
        rem Print progress
        set /a "PROCESSED+=1"
        echo [!PROCESSED!/!TOTAL!] Processing: !DATE! ^-^> !NEW_FILENAME!

        rem Run gdalwarp to resample and reproject the raster to EPSG:4326
        rem Note: All 15 bands are preserved during resampling
        gdalwarp -t_srs EPSG:4326 -tr 0.02 0.02 -r bilinear -co "COMPRESS=LZW" -co "TILED=YES" -co "BLOCKXSIZE=256" -co "BLOCKYSIZE=256" -ot Float32 -dstnodata -9999.0 "%%f" "%OUTPUT_DIR%\!NEW_FILENAME!" >nul 2>&1

        rem Check if gdalwarp was successful
        if !errorlevel! neq 0 (
            echo    ERROR: Failed to process !DATE!
            set /a "ERRORS+=1"
        ) else (
            echo    SUCCESS: !NEW_FILENAME!
        )
    )
)

echo.
echo ========================================================================
echo Processing Complete
echo ========================================================================
echo Total files:     !TOTAL!
echo Processed:       !PROCESSED!
echo Skipped:         !SKIPPED!
echo Errors:          !ERRORS!
echo Output location: %OUTPUT_DIR%
echo ========================================================================
echo.
echo Note: Each file contains 15 bands (ERA5-Land variables)
echo Band order: evap_transp, pot_evap, runoff, skin_temp, snow_cover,
echo             snow_depth, snowfall, snowmelt, soil_temp, pressure,
echo             solar_rad, temp_max, temp_mean, temp_min, precip
echo ========================================================================

pause
