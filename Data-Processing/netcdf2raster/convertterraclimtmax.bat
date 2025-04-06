@echo off
setlocal enabledelayedexpansion

REM Set paths
set "GDAL_TRANSLATE=C:\Program Files\QGIS 3.40.4\bin\gdal_translate.exe"
set "GDAL_WARP=C:\Program Files\QGIS 3.40.4\bin\gdalwarp.exe"
set "tmax_DIR=ReplaceWithYourPath\tmax"
set "TARGET_RES=0.02"
set "CUTLINE_PATH=ReplaceWithYourPath\camcorecoordspolyfile\cacmcorecoordspolyfile.shp"
set "OUTPUT_DIR=%tmax_DIR%\rasters"

REM Create output directory if it doesn't exist
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

REM Display all .nc files in directory for diagnosis
echo List of all NetCDF files found:
dir /b "%tmax_DIR%\*.nc"
echo.

REM Count total files
set count=0
for %%f in ("%tmax_DIR%\*.nc") do set /a count+=1
echo Total NetCDF files found: %count%
echo.

REM Process each .nc file directly with explicit command
pushd "%tmax_DIR%"
for %%f in (*.nc) do (
    echo ==========================================
    echo PROCESSING FILE: %%f
    echo ==========================================
    
    REM Extract year part from filename
    set "filename=%%~nf"
    for /f "tokens=3 delims=_" %%y in ("!filename!") do (
        set "year=%%y"
        echo Year detected: !year!
    )
    
    REM Process each month (1-12)
    for /L %%m in (1,1,12) do (
        REM Format month with leading zero
        set "month=0%%m"
        set "month=!month:~-2!"
        
        echo Working on !year! Month !month!...
        
        REM Define output filenames
        set "tempfile=%OUTPUT_DIR%\terraclim_tmax_!year!_!month!_temp.tif"
        set "finalfile=%OUTPUT_DIR%\terraclim_tmax_!year!_!month!.tif"
        
        REM Skip if final file already exists
        if exist "!finalfile!" (
            echo File already exists: !finalfile! - Skipping...
        ) else (
            echo Extracting band %%m from %%f...
            
            REM Try with 'tmax' variable first
            echo Command: "%GDAL_TRANSLATE%" -of GTiff -b %%m -a_srs EPSG:4326 -co COMPRESS=LZW -co TILED=YES "NETCDF:%%f:tmax" "!tempfile!"
            "%GDAL_TRANSLATE%" -of GTiff -b %%m -a_srs EPSG:4326 -co COMPRESS=LZW -co TILED=YES "NETCDF:%%f:tmax" "!tempfile!"
            
            if exist "!tempfile!" (
                echo Applying cutline with gdalwarp...
                "%GDAL_WARP%" -tr %TARGET_RES% %TARGET_RES% -r bilinear -cutline "%CUTLINE_PATH%" -crop_to_cutline -co COMPRESS=LZW -co TILED=YES -ot Float32 -dstnodata -9999.0 "!tempfile!" "!finalfile!"
                del "!tempfile!"
                echo Created: !finalfile!
            ) else (
                echo Failed with 'tmax', trying 'tmax_mm'...
                "%GDAL_TRANSLATE%" -of GTiff -b %%m -a_srs EPSG:4326 -co COMPRESS=LZW -co TILED=YES "NETCDF:%%f:tmax_mm" "!tempfile!"
                
                if exist "!tempfile!" (
                    echo Applying cutline with gdalwarp...
                    "%GDAL_WARP%" -tr %TARGET_RES% %TARGET_RES% -r bilinear -cutline "%CUTLINE_PATH%" -crop_to_cutline -co COMPRESS=LZW -co TILED=YES -ot Float32 -dstnodata -9999.0 "!tempfile!" "!finalfile!"
                    del "!tempfile!"
                    echo Created: !finalfile!
                ) else (
                    echo ERROR: Failed to extract data for !year! Month !month!
                )
            )
        )
    )
    echo Completed processing file: %%f
    echo.
)
popd

echo ==========================================
echo PROCESSING COMPLETE
echo ==========================================
pause