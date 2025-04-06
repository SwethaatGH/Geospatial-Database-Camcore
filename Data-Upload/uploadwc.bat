@echo off

REM Set environment variables
set DB_USER=XXXX
set DB_PASS=XXXX
set DB_HOST=localhost
set DB_PORT=5432
set DB_NAME=covariablesv1

REM Set the password for PostgreSQL using PGPASSWORD
set PGPASSWORD=%DB_PASS%

for %%f in (*.tif) do (
    set "name=%%~nf"
    setlocal enabledelayedexpansion
     
    REM Upload the raster file
    raster2pgsql -s 4326 -I -C -M -t 128x128 "%%f" public.!name! | psql -U !DB_USER! -d !DB_NAME! -h !DB_HOST! -p !DB_PORT!

   
    endlocal
)

echo Done!