@echo off
setlocal enabledelayedexpansion

rem Define input and output directories
set "INPUT_DIR=ReplaceWithYourPath\ET_BBOX\GEE_ET_BBOX"
set "OUTPUT_DIR=ReplaceWithYourPath\ET_BBOX\GEE_ET_BBOX_resampled"

rem Create output directory if it doesn't exist
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

rem Iterate through all .tif files in the input directory
for %%f in ("%INPUT_DIR%\*.tif") do (
    rem Extract the filename without extension (e.g., ET_2000-12-10)
    set "FILENAME=%%~nf"

    rem Extract the date part from the filename (e.g., 2000-12-10)
    for /f "tokens=2 delims=_" %%a in ("!FILENAME!") do (
        set "DATE=%%a"
    )

    rem Extract year, month, and day from the date (YYYY-MM-DD)
    set "YEAR=!DATE:~0,4!"
    set "MONTH=!DATE:~5,2!"
    set "DAY=!DATE:~8,2!"

    rem Construct the new filename in the format et_YYYY_MM_DD.tif
    set "NEW_FILENAME=et_!YEAR!_!MONTH!_!DAY!.tif"

    rem Print the old and new filenames
    echo Processing: %%f to !NEW_FILENAME!

    rem Run gdalwarp to resample and reproject the raster to EPSG:4326
    gdalwarp -t_srs EPSG:4326 -tr 0.02 0.02 -r bilinear -co "COMPRESS=LZW" -co "TILED=YES" -ot Float32 -dstnodata -9999.0 "%%f" "%OUTPUT_DIR%\!NEW_FILENAME!"

    rem Check if gdalwarp was successful
    if %errorlevel% neq 0 (
        echo Error processing: %%f
    ) else (
        echo Processing of "!NEW_FILENAME!" complete.
    )
)

echo All processing complete.
pause
