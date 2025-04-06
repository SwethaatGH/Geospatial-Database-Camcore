
@echo off
setlocal enabledelayedexpansion
rem Define input and output directories
set "INPUT_DIR=ReplaceWithYourPath\CHIRPS_BBOX"
set "OUTPUT_DIR=ReplaceWithYourPath\CHIRPS_BBOX_resampled"
rem Create output directory if it doesn't exist
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"
rem Iterate through all .tif files in the input directory
for %%f in ("%INPUT_DIR%\*.tif") do (
    rem Extract the filename (e.g., Precip_2013-07-26.tif)
    set "FILENAME=%%~nxf"
    
    rem Extract the date part from the filename (e.g., 2013-07-26)
    for /f "tokens=2 delims=_." %%a in ("!FILENAME!") do (
        set "DATE=%%a"
    )
    
    rem Format the date to the desired format (2013-07-26 to 2013_07_26)
    set "YEAR=!DATE:~0,4!"
    set "MONTH=!DATE:~5,2!"
    set "DAY=!DATE:~8,2!"
    
    rem Construct the new filename in the format chirps_2013_07_26.tif
    set "NEW_FILENAME=chirps_!YEAR!_!MONTH!_!DAY!.tif"
    
    rem Check if output file already exists
    if exist "%OUTPUT_DIR%\!NEW_FILENAME!" (
        echo Skipping: !NEW_FILENAME! - File already exists
    ) else (
        rem Print the old and new filenames
        echo Processing: !FILENAME! -^> !NEW_FILENAME!
        
        rem Run gdalwarp to resample the raster to 0.02 degrees and save in the output directory
        gdalwarp -tr 0.02 0.02 -r bilinear -co "COMPRESS=LZW" -co "TILED=YES" -ot Float32 -dstnodata -9999.0 "%%f" "%OUTPUT_DIR%\!NEW_FILENAME!"
        
        rem Print the completion message for this file
        echo Resampling of "!NEW_FILENAME!" complete.
    )
)
echo All processing complete.
pause