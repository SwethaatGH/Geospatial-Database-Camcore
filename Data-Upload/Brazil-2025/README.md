# Brazil 2025 Data Update - Upload Scripts

This folder contains scripts to upload processed 2025 Brazil data to the covariables2 database.

## Database Configuration
- **Database**: covariables2
- **Host**: localhost
- **Port**: 5433
- **User**: postgres
- **Tables**: Use APPEND mode (-a flag) - never drop existing tables!

## Upload Scripts

### 1. CHIRPS Upload
- **Script**: `upload_chirps_brazil_2025.py`
- **Target Table**: `chirps_data`
- **Mode**: Append (-a)
- **Structure**: (rid, date_id, var_name='precipitation', rast)

### 2. SPEI Upload
- **Script**: `upload_spei_brazil_2025.py`
- **Target Table**: `spei_data`
- **Mode**: Append (-a)
- **Structure**: (rid, date_id, var_name='spei', rast)

### 3. ET Upload
- **Script**: `upload_et_brazil_2025.py`
- **Target Table**: `et_data`
- **Mode**: Append (-a)
- **Structure**: (rid, date_id, var_name='et', rast)

### 4. ERA5 Upload
- **Script**: `upload_era5_brazil_2025.bat`
- **Target Tables**: Multiple (temperature_2m_data, precipitation_data, etc.)
- **Mode**: Append (-a)
- **Structure**: (rid, date_id, var_name, rast)

### 5. TerraClimate Upload
- **Script**: `upload_terraclim_brazil_2025.bat`
- **Target Table**: `terraclim_data`
- **Mode**: Append (-a)
- **Structure**: (rid, date_id, var_name, rast)

## Usage

### Python Scripts
```powershell
python upload_chirps_brazil_2025.py
```

### Batch Scripts
```powershell
.\upload_era5_brazil_2025.bat
```

## Critical Notes

⚠️ **ALWAYS USE APPEND MODE (-a)**
- Never use -c or -d flags (create/drop table)
- Existing 2024 and earlier data must not be affected
- Only add 2025 records

⚠️ **Verify Before Upload**
- Check latest date_id in tables before upload
- Ensure no duplicate dates
- Confirm 2025 data is processed correctly

⚠️ **raster2pgsql Location**
```
C:\Program Files\PostgreSQL\13\bin\raster2pgsql.exe
```

## Verification Queries

After upload, run these checks:
```sql
-- Check date ranges
SELECT MIN(date_id), MAX(date_id), COUNT(*) FROM chirps_data;
SELECT MIN(date_id), MAX(date_id), COUNT(*) FROM spei_data;
SELECT MIN(date_id), MAX(date_id), COUNT(*) FROM et_data;

-- Check for duplicates
SELECT date_id, COUNT(*) FROM chirps_data GROUP BY date_id HAVING COUNT(*) > 1;

-- Count 2025 records
SELECT COUNT(*) FROM chirps_data WHERE date_id >= '2025-01-01';
```
