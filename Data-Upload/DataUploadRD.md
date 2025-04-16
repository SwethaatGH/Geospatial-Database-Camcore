# Upload Scripts/ Processes for databases

#### Make sure path is added for postgres bin to environment variable Path after downloading Postgres. Add POSTGIS in stack builder. Download process is [here](https://postgis.net/documentation/getting_started/install_windows/).

- Postgis version: 
- Postgres version:
- QGIS version:
---
## Ensure all scripts are in same directory as resampled databases

**Elevation Uploaded using command:** `raster2pgsql -s 4326 -I -C -M -t 128x128 "%%f" public.table_name | psql -U username -d dbname -h host_name! -p !port_number`

--- 
Run all batch files in command line 

**Database with Worldclim, ET, CHIRPS, SPEI, Elevation, Terraclim, Nasa Power is 1.17 TB**

**CSV Uploaded using command:** `raster2pgsql -s 4326 -I -C -M -t 128x128 "%%f" public.table_name | psql -U username -d dbname -h host_name! -p !port_number`