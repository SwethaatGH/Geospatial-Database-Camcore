@echo off
setlocal enabledelayedexpansion

rem Define input and output directories
set "INPUT_DIR=ReplaceWitYourPath\SoilGrid"
set "OUTPUT_DIR=ReplaceWitYourPath\SoilGridResamp\"

rem Change to the input directory
cd /d "%INPUT_DIR%"

rem Iterate through all .tif files in the directory  
for %%f in (*.tif) do (
    rem Construct the output path by replacing the input directory structure
    set "REL_PATH=%%f"
    set "REL_PATH=!REL_PATH:%INPUT_DIR%=!"   rem Remove INPUT_DIR from the path
    set "OUT_PATH=%OUTPUT_DIR%!REL_PATH!"   rem Append to the OUTPUT_DIR

    rem Print the input and output paths
    echo Input Path: %%f
    echo Output Path: !OUT_PATH!

    rem Create the output folder if it doesn't exist
    for %%A in ("!OUT_PATH!") do (
        if not exist "%%~dpA" mkdir "%%~dpA"
    )

    rem Run gdalwarp to resample the raster
    gdalwarp -cutline  "ReplaceWithYourPath\camcorecoordspolyfile\cacmcorecoordspolyfile.shp" -crop_to_cutline -co "COMPRESS=LZW" -co "TILED=YES" -ot Float32 -dstnodata -9999 "%%f" "!OUT_PATH!"

    rem Print the completion message for this file
    echo Resampling of "%%f" complete.
)

pause
