@echo off
setlocal enabledelayedexpansion

rem Define input and output directories
set "INPUT_DIR=ReplaceWitYourPath\WorldClim\2.5mins"
set "OUTPUT_DIR=ReplaceWitYourPath\WorldClimResamp0.02"

rem Create output directory if it doesn't exist
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

rem Iterate through all .tif files in the directory and subdirectories
for /R "%INPUT_DIR%" %%f in (*.tif) do (
    rem Extract the filename
    set "FILENAME=%%~nxf"
    
    echo Full filename: !FILENAME!
    
    rem Extract parts directly from the filename
    if "!FILENAME:~0,15!"=="wc2.1_2.5m_prec" (
        set "VAR_TYPE=prec"
        set "YEAR=!FILENAME:~16,4!"
        set "MONTH=!FILENAME:~21,2!"
    ) else if "!FILENAME:~0,15!"=="wc2.1_2.5m_tmax" (
        set "VAR_TYPE=tmax"
        set "YEAR=!FILENAME:~16,4!"
        set "MONTH=!FILENAME:~21,2!"
    ) else if "!FILENAME:~0,15!"=="wc2.1_2.5m_tmin" (
        set "VAR_TYPE=tmin"
        set "YEAR=!FILENAME:~16,4!"
        set "MONTH=!FILENAME:~21,2!"
    ) else (
        rem For other variable types, extract by position
        for /f "tokens=3 delims=_" %%v in ("!FILENAME!") do (
            set "VAR_TYPE=%%v"
        )
        
        rem Find the year-month pattern in the filename (YYYY-MM)
        for /f "tokens=1 delims= " %%a in ('echo !FILENAME! ^| findstr /r "[0-9][0-9][0-9][0-9]-[0-9][0-9]"') do (
            set "DATE_PART=%%a"
            set "YEAR=!DATE_PART:~0,4!"
            set "MONTH=!DATE_PART:~5,2!"
        )
    )
    
    rem Construct the new filename in the format wc_VARTYPE_YYYY_MM.tif
    set "NEW_FILENAME=wc_!VAR_TYPE!_!YEAR!_!MONTH!.tif"
    
    rem Print the input and output files
    echo Processing: !FILENAME! -^> !NEW_FILENAME!
    
    rem Run gdalwarp to resample the raster
    gdalwarp -tr 0.02 0.02 -r bilinear -cutline "ReplaceWitYourPath\camcorecoordspolyfile\cacmcorecoordspolyfile.shp" -crop_to_cutline -co "COMPRESS=LZW" -co "TILED=YES" -ot Float32 -dstnodata -9999.0 "%%f" "%OUTPUT_DIR%\!NEW_FILENAME!"
    
    rem Print the completion message for this file
    echo Resampling of "!NEW_FILENAME!" complete.
)

echo All processing complete.
pause