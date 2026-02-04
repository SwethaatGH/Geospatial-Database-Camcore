@echo off
setlocal enabledelayedexpansion

rem Resample SPEI monthly files to 0.02 degrees
rem Input: Indonesia_SPEI_Monthly (already named spei_YYYY_MM.tif)
rem Output: Indonesia_SPEI_Resampled (same naming)

set "INPUT_DIR=Q:\My Drive\Indonesia_SPEI_Monthly"
set "OUTPUT_DIR=Q:\My Drive\Indonesia_SPEI_Resampled"

rem Create output directory if it doesn't exist
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

echo ============================================================
echo Resampling SPEI files to 0.02 degrees
echo Input:  %INPUT_DIR%
echo Output: %OUTPUT_DIR%
echo ============================================================
echo.

rem Count total files
set COUNT=0
for %%f in ("%INPUT_DIR%\*.tif") do set /a COUNT+=1
echo Found %COUNT% files to resample
echo.

rem Iterate through all .tif files
set PROCESSED=0
for %%f in ("%INPUT_DIR%\*.tif") do (
    set /a PROCESSED+=1
    set "FILENAME=%%~nxf"
    
    echo [!PROCESSED!/%COUNT%] Processing: !FILENAME!
    
    rem Run gdalwarp to resample
    gdalwarp -tr 0.02 0.02 -r bilinear -co "COMPRESS=LZW" -co "TILED=YES" -ot Float32 -dstnodata -9999.0 "%%f" "%OUTPUT_DIR%\!FILENAME!"
    
    if errorlevel 1 (
        echo   ERROR: Failed to resample !FILENAME!
    ) else (
        echo   OK: Resampled successfully
    )
    echo.
)

echo ============================================================
echo All processing complete!
echo Processed: %PROCESSED% files
echo Output: %OUTPUT_DIR%
echo ============================================================
pause
