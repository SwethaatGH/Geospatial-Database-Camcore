# main.py (fully integrated version with authentication)
import time
import math
import sys
import os, shutil, subprocess, uuid, json
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Depends, HTTPException, Query, File, UploadFile, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from .database import get_db
from datetime import datetime, timedelta, date
from enum import Enum
from shapely.geometry import box
from shapely import wkt as shapely_wkt

# --- Enums and configs ---
class Region(str, Enum):
    BRAZIL = "brazil"
    INDONESIA = "indonesia"

class DataSource(str, Enum):
    WORLDCLIM = "wc"
    SPEI = "spei"
    CHIRPS = "chirps"
    ET = "et"
    ELEVATION = "elev"
    SOILGRIDS = "soil"
    TERRACLIM = "tc"
    NASAPOWER = "np"
    ERA5 = "era5"
    KOPPEN = "koppen"  # New addition for Köppen-Geiger
    BIOCLIM = "bio"
    BRAZIL = "brazil"

class Cadence(str, Enum):
    DAILY = "daily"
    EIGHT_DAY = "8day"
    MONTHLY = "monthly"
    STATIC = "static"
    AGGREGATED = "aggregated"

DATA_SOURCE_CADENCE = {
    DataSource.WORLDCLIM: Cadence.MONTHLY,
    DataSource.SPEI: Cadence.MONTHLY,
    DataSource.CHIRPS: Cadence.DAILY,
    DataSource.ET: Cadence.EIGHT_DAY,
    DataSource.ELEVATION: Cadence.STATIC,
    DataSource.SOILGRIDS: Cadence.AGGREGATED,
    DataSource.TERRACLIM: Cadence.MONTHLY,
    DataSource.NASAPOWER: Cadence.MONTHLY,
    DataSource.ERA5: Cadence.DAILY,
    DataSource.KOPPEN: Cadence.STATIC,
    DataSource.BIOCLIM: Cadence.STATIC,
    DataSource.BRAZIL: Cadence.DAILY,
}

DATA_SOURCE_TABLES = {
    DataSource.WORLDCLIM: "wc_data",
    DataSource.SPEI: "spei_data",
    DataSource.CHIRPS: "chirps_data",
    DataSource.ET: "et_data",
    DataSource.ELEVATION: "elev_data",
    DataSource.TERRACLIM: "terraclim_data",
    DataSource.NASAPOWER: "np_data",
    DataSource.SOILGRIDS: "soil_data",
    DataSource.ERA5: "era5_data",
    DataSource.KOPPEN: "koppen_data",  # Add the table we created
    DataSource.BIOCLIM: "bio_data",
    DataSource.BRAZIL: "brazil_data",
}

AVAILABLE_VARIABLES = {
    DataSource.WORLDCLIM: ["prec", "tmax", "tmin"],
    DataSource.SPEI: ["spei"],
    DataSource.CHIRPS: ["chirps"],
    DataSource.ET: ["et"],
    DataSource.ELEVATION: ["aspect", "elev", "flowdir", "hillshade", "roughness", "tpi", "tri", "slope", "hand"], 
    DataSource.SOILGRIDS: ["bdod", "cec", "cfvo", "clay", "nitrogen", "ocd", "ocs", "phh2o", "sand", "silt", "soc", "wv0010", "wv0030", "wv1500"],
    DataSource.TERRACLIM: ["aet", "def", "pdsi", "pet", "ppt", "q", "soil", "srad", "tmin", "tmax", "vap", "vpd", "ws"],
    DataSource.NASAPOWER: ["airmass", "allsky_kt", "allsky_nkt", "allsky_sfc_lw_dwn", "allsky_sfc_lw_up", "allsky_sfc_par_diff", 
                         "allsky_sfc_par_dirh", "allsky_sfc_par_tot", "allsky_sfc_sw_diff", "allsky_sfc_sw_dirh", "allsky_sfc_sw_dni", 
                         "allsky_sfc_sw_dwn", "allsky_sfc_sw_up", "allsky_sfc_uv_index", "allsky_sfc_uva", "allsky_sfc_uvb", 
                         "allsky_srf_alb", "aod_55", "aod_55_adj", "aod_84", "cloud_amt", "cloud_amt_day", "cloud_amt_night", 
                         "cloud_od", "clrsky_days", "clrsky_kt", "clrsky_nkt", "clrsky_sfc_lw_dwn", "clrsky_sfc_lw_up", 
                         "clrsky_sfc_par_diff", "clrsky_sfc_par_dirh", "clrsky_sfc_par_tot", "clrsky_sfc_sw_diff", "clrsky_sfc_sw_dirh", 
                         "clrsky_sfc_sw_dni", "clrsky_sfc_sw_dwn", "clrsky_sfc_sw_up", "clrsky_srf_alb", "midday_insol", 
                         "original_allsky_sfc_sw_diff", "original_allsky_sfc_sw_dirh", "psh", "pw", "srf_alb_adj", "toa_sw_dni", 
                         "toa_sw_dwn", "ts_adj"],
    DataSource.ERA5: ["evaptrans", "latheat", "netsolrad", "press", "sktemp", "sotemp1", "sotemp2", "sotemp3", "temp", 
                     "totprec", "uwind", "vwind", "volsowat1", "volsowat12", "volsowat13"],
    DataSource.BIOCLIM: [
        "bio1", "bio2", "bio3", "bio4", "bio5",
        "bio6", "bio7", "bio8", "bio9", "bio10",
        "bio11", "bio12", "bio13", "bio14", "bio15",
        "bio16", "bio17", "bio18", "bio19"
    ],
    DataSource.KOPPEN: ["bsh", "dfb", "cfc", "cfa", "ef", "cwc", "af", "et", "cwb", "cwa",
    "csc", "bwk", "aw", "bsk", "dsb", "csa", "all", "dwb", "am", "dfc",
    "dwc", "cfb", "bwh", "csb", "dsc"],
    DataSource.BRAZIL: ["eto", "pr", "tmax", "tmin", "rh", "u2", "rs"],
}

DATASOURCES_WITH_VARIABLES = [
    DataSource.WORLDCLIM,
    DataSource.TERRACLIM,
    DataSource.NASAPOWER,
    DataSource.ERA5,
    DataSource.ELEVATION,
    DataSource.SOILGRIDS,
    DataSource.BIOCLIM,
    DataSource.KOPPEN,
    DataSource.BRAZIL,
]

STATIC_DATA_SOURCES = [
    DataSource.ELEVATION,
    DataSource.SOILGRIDS,
    DataSource.KOPPEN ,
    DataSource.BIOCLIM
]

from app.climate_data_service import get_climate_data_timeseries_logic, table_exists

# --- App init ---
app = FastAPI(title="Camcore Database API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Endpoints ---
@app.get("/")
async def root():
    return {"message": "Welcome to the Camcore Database API"}

@app.get("/climate-data-timeseries/")
async def get_climate_data_timeseries(
    lat: float = Query(...),
    lon: float = Query(...),
    region: Region = Query(Region.BRAZIL, description="Geographic region (brazil or indonesia)"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    variable: Optional[str] = Query(None),
    data_source: DataSource = Query(DataSource.WORLDCLIM),
    db: AsyncSession = Depends(get_db)
):
    return await get_climate_data_timeseries_logic(
        lat=lat, lon=lon,
        region=region,
        start_date=start_date, end_date=end_date,
        data_source=data_source, variable=variable,
        db=db
    )
## Most used functions above, new endpoints below ##

# CSV Processor Endpoint
@app.post("/api/process-csv")
async def process_csv(
    file: UploadFile = File(...),
    option: str = Form(...),
    variables: Optional[str] = Form(None),
):
    job_id = str(uuid.uuid4())
    upload_dir = Path(f"../Csv-Creator/uploads/{job_id}")
    processed_dir = Path(f"../Csv-Creator/processed/{job_id}")
    os.makedirs(upload_dir, exist_ok=True)
    os.makedirs(processed_dir, exist_ok=True)

    file_path = upload_dir / file.filename
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving file: {e}")

    raw_data_batches_zip = processed_dir / f"raw_data_{file.filename.replace('.csv', '_batches.zip')}"
    covariates_path = processed_dir / f"covariates_{file.filename}"

    try:
        if option == "full":
            # Run script.py (which does batching and covariates)
            subprocess.run([
                sys.executable, "../Csv-Creator/script.py",
                "--input", str(file_path),
                "--output", str(covariates_path),
                "--default-start-date", "2000-01-01",
                "--default-end-date", "2000-12-31",
                "--cache-file", f"{processed_dir}/cache.json",
                "--vars", variables 
            ], check=True)
        else:
            # Run script_raw.py (which does batching and merging, but not covariates)
            subprocess.run([
                sys.executable, "../Csv-Creator/script_raw.py",
                "--input", str(file_path),
                "--output", str(raw_data_batches_zip),
                "--default-start-date", "2000-01-01",
                "--default-end-date", "2000-12-31",
                "--cache-file", f"{processed_dir}/cache.json",
                "--vars", variables 
            ], check=True)

        # Prepare response:
        resp = {
            "message": "Processing complete.",
            "jobId": job_id,
            "rawDataFile": f"/download/{job_id}/{raw_data_batches_zip.name}",
            "covariatesFile": f"/download/{job_id}/covariates_{file.filename}" if option == "full" else None
        }
        return resp

    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Processing error: {e}")


@app.get("/download/{job_id}/{filename}")
async def download_file(job_id: str, filename: str):
    file_path = Path(f"../Csv-Creator/processed/{job_id}/{filename}")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=file_path, filename=filename, media_type="application/octet-stream")    
    

def sanitize_for_json(obj):
    """Recursively sanitize an object for JSON serialization, replacing NaN and Infinity with None."""
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(i) for i in obj]
    elif isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    else:
        return obj

  
@app.get("/climate-data-timeseries-bbox-sampled/")
async def get_climate_data_timeseries_bbox_sampled(
    min_lat: float = Query(..., description="Minimum latitude of BBOX"),
    min_lon: float = Query(..., description="Minimum longitude of BBOX"),
    max_lat: float = Query(..., description="Maximum latitude of BBOX"),
    max_lon: float = Query(..., description="Maximum longitude of BBOX"),
    date: Optional[str] = Query(None, description="Single date in YYYY-MM-DD format"),
    start_date: Optional[str] = Query(None, description="Start date in YYYY-MM-DD format (for time series)"),
    end_date: Optional[str] = Query(None, description="End date in YYYY-MM-DD format (for time series)"),
    data_source: DataSource = Query(DataSource.WORLDCLIM, description="Data source"),
    variable: Optional[str] = Query(None, description="Specific variable to query"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get climate data for a bounding box (BBOX) with random sampling.
    - For single date mode: Uses 'date' parameter and samples 100 random points
    - For time series mode: Uses 'start_date'/'end_date' parameters and samples 5 random points
    """
    # Determine if we're in time series mode
    is_time_series = start_date is not None and end_date is not None
    
    # Set appropriate sample size based on mode
    sample_size = 5 
    
    # Validate inputs based on mode
    if is_time_series:
        if not start_date or not end_date:
            raise HTTPException(status_code=400, detail="Both start_date and end_date are required for time series mode")
    
    # Convert dates
    try:
        date_obj = datetime.strptime(date, "%Y-%m-%d").date() if date else None
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Validate data source
    table_name = DATA_SOURCE_TABLES.get(data_source)
    if not table_name:
        raise HTTPException(status_code=400, detail=f"Unknown data source: {data_source}")
    
    if not await table_exists(db, table_name):
        raise HTTPException(status_code=404, detail=f"No data available for {data_source.value}")
    
    # Get default variable if not provided
    if not variable:
        available_vars = AVAILABLE_VARIABLES.get(data_source, [])
        if available_vars:
            variable = available_vars[0]
        else:
            raise HTTPException(status_code=400, detail=f"No variables available for {data_source.value}")
    elif variable not in AVAILABLE_VARIABLES.get(data_source, []):
        raise HTTPException(
            status_code=400, 
            detail=f"Variable '{variable}' not available for {data_source.value}. Available variables: {', '.join(AVAILABLE_VARIABLES.get(data_source, []))}"
        )
    
    try:
        # Generate random sample points within the bounding box using Python instead of SQL
        # This avoids the transaction rollback issues
        import random
        import math  # Import math for NaN checks
        random_points = []
        for _ in range(sample_size):  # Fixed syntax error
            lat = min_lat + random.random() * (max_lat - min_lat)
            lon = min_lon + random.random() * (max_lon - min_lon)
            random_points.append({"lat": lat, "lon": lon})
        
        # Initialize result structure
        result = {
            "bbox": [min_lat, min_lon, max_lat, max_lon],
            "data_source": data_source.value,
            "variable": variable,
            "sample_size": len(random_points),
            "points": []
        }
        
        # Add date information based on mode
        if is_time_series:
            result["start_date"] = start_date
            result["end_date"] = end_date
            result["cadence"] = DATA_SOURCE_CADENCE.get(data_source, Cadence.MONTHLY).value
        else:
            result["date"] = date
        
        # Process each sample point
        for point in random_points:
            lat = point["lat"]
            lon = point["lon"]
            point_wkt = f"ST_SetSRID(ST_MakePoint({lon}, {lat}), 4326)"
            
            point_data = {
                "lat": lat,
                "lon": lon,
                "values": {}
            }
            
            # Query based on time series or single date mode
            if is_time_series:
                # Time series mode - process multiple dates
                if data_source in DATASOURCES_WITH_VARIABLES:
                    query = text(f"""
                        SELECT 
                            date_id,
                            var_name,
                            ST_Value(rast, {point_wkt}) AS point_value
                        FROM 
                            {table_name}
                        WHERE 
                            date_id BETWEEN :start_date AND :end_date
                            AND var_name = :variable
                            AND ST_Value(rast, {point_wkt}) IS NOT NULL
                        ORDER BY date_id
                    """)
                    
                    result_data = await db.execute(query, {
                        "start_date": start_date_obj,
                        "end_date": end_date_obj,
                        "variable": variable
                    })
                else:
                    # For data sources without var_name column
                    query = text(f"""
                        SELECT 
                            date_id,
                            ST_Value(rast, {point_wkt}) AS point_value
                        FROM 
                            {table_name}
                        WHERE 
                            date_id BETWEEN :start_date AND :end_date
                            AND ST_Value(rast, {point_wkt}) IS NOT NULL
                        ORDER BY date_id
                    """)
                    
                    result_data = await db.execute(query, {
                        "start_date": start_date_obj,
                        "end_date": end_date_obj
                    })
                
                # Process time series results
                rows = result_data.mappings().all()
                time_values = []
                
                for row in rows:
                    if row["point_value"] is not None:
                        date_obj = row["date_id"]
                        
                        # Handle NaN values - Convert to None for JSON serialization
                        point_value = row["point_value"]
                        if isinstance(point_value, float) and (math.isnan(point_value) or math.isinf(point_value)):
                            point_value = None
                            
                        time_value = {
                            "date": date_obj.strftime("%Y-%m-%d"),
                            "year": date_obj.year,
                            "month": date_obj.month,
                            "values": {variable: point_value}  # Use the sanitized value
                        }
                        
                        # Add day for daily cadence
                        if DATA_SOURCE_CADENCE.get(data_source) == Cadence.DAILY:
                            time_value["day"] = date_obj.day
                            
                        time_values.append(time_value)
                
                # Only add point if it has data
                if time_values:
                    point_data["values"] = time_values
                    result["points"].append(point_data)
                
            else:
                # Single date mode or static data
                if data_source in STATIC_DATA_SOURCES:
                    variables = [variable] if variable else AVAILABLE_VARIABLES.get(data_source, [])
                    if not variables:
                        continue

                    query = text(f"""
                        SELECT var_name, ST_Value(rast, {point_wkt}) AS point_value
                        FROM {table_name}
                        WHERE var_name IN ({", ".join([f"'{v}'" for v in variables])})
                        AND ST_Value(rast, {point_wkt}) IS NOT NULL
                    """)
                    rows = (await db.execute(query)).mappings().all()

                    for row in rows:
                        val = row["point_value"]
                        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                            val = None
                        if val is not None:
                            point_data["values"][row["var_name"]] = val
               
                # Only add point if it has data
                if point_data["values"]:
                    result["points"].append(point_data)
        
        
        # Calculate statistics if we have points
        if result["points"]:
            # For single date mode, calculate overall statistics
            if not is_time_series:
                values = [p["values"].get(variable) for p in result["points"] if variable in p["values"]]
                if values:
                    # Filter out any remaining NaN values before statistics
                    values = [v for v in values if not (isinstance(v, float) and (math.isnan(v) or math.isinf(v)))]
                    if values:  # Make sure we still have values after filtering
                        result["stats"] = {
                            "min": min(values),
                            "max": max(values),
                            "avg": sum(values) / len(values),
                            "count": len(values)
                        }
        result = sanitize_for_json(result)
        return result
    
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}\n{error_traceback}")
            
# Mount the static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/ui/", response_class=HTMLResponse)
async def get_ui():
    with open("static/timeseriesv3.html", "r") as f:
        return f.read()

@app.get("/climate-data-grid-samples/")
async def get_climate_data_grid_samples(
    min_lat: float = Query(..., description="Minimum latitude of BBOX"),
    min_lon: float = Query(..., description="Minimum longitude of BBOX"),
    max_lat: float = Query(..., description="Maximum latitude of BBOX"),
    max_lon: float = Query(..., description="Maximum longitude of BBOX"),
    start_date: Optional[str] = Query(None, description="Start date in YYYY-MM-DD format"),
    end_date: Optional[str] = Query(None, description="End date in YYYY-MM-DD format"),
    data_source: DataSource = Query(DataSource.CHIRPS, description="Data source"),
    variable: Optional[str] = Query(None, description="Specific variable to query"),
    grid_size: int = Query(5, description="Number of points in each direction (total points = grid_size^2)"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get climate data for a bounding box (BBOX) using a regular grid of points.
    Returns time series data for each point in the grid.
    """
    # Validate dates
    if not start_date or not end_date:
        raise HTTPException(status_code=400, detail="Both start_date and end_date are required")
    
    try:
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Validate data source
    table_name = DATA_SOURCE_TABLES.get(data_source)
    if not table_name:
        raise HTTPException(status_code=400, detail=f"Unknown data source: {data_source}")
    
    if not await table_exists(db, table_name):
        raise HTTPException(status_code=404, detail=f"No data available for {data_source.value}")
    
    # Special handling for CHIRPS - use the correct variable
    if data_source == DataSource.CHIRPS:
        # CHIRPS uses 'chirps' as variable name in the config but we'll use 'prec' for output consistency
        output_variable = "prec"
    else:
        # Get default variable if not provided
        if not variable:
            available_vars = AVAILABLE_VARIABLES.get(data_source, [])
            if available_vars:
                output_variable = available_vars[0]
            else:
                raise HTTPException(status_code=400, detail=f"No variables available for {data_source.value}")
        elif variable not in AVAILABLE_VARIABLES.get(data_source, []):
            raise HTTPException(
                status_code=400, 
                detail=f"Variable '{variable}' not available for {data_source.value}. Available variables: {', '.join(AVAILABLE_VARIABLES.get(data_source, []))}"
            )
        else:
            output_variable = variable
    
    try:
        # Generate grid points
        grid_points = []
        lat_step = (max_lat - min_lat) / (grid_size - 1) if grid_size > 1 else 0
        lon_step = (max_lon - min_lon) / (grid_size - 1) if grid_size > 1 else 0
        
        for i in range(grid_size):
            for j in range(grid_size):
                lat = min_lat + i * lat_step
                lon = min_lon + j * lon_step
                grid_points.append({"lat": lat, "lon": lon})
        
        # Initialize result structure
        result = {
            "bbox": [min_lat, min_lon, max_lat, max_lon],
            "data_source": data_source.value,
            "variable": output_variable,
            "grid_size": grid_size,
            "total_points": len(grid_points),
            "start_date": start_date,
            "end_date": end_date,
            "cadence": DATA_SOURCE_CADENCE.get(data_source, Cadence.MONTHLY).value,
            "points": []
        }
        
        # Process each grid point
        for point in grid_points:
            lat = point["lat"]
            lon = point["lon"]
            point_wkt = f"ST_SetSRID(ST_MakePoint({lon}, {lat}), 4326)"
            
            point_data = {
                "lat": lat,
                "lon": lon,
                "values": []
            }
            
            # Query database based on data source type
            if data_source in DATASOURCES_WITH_VARIABLES:
                # For sources with var_name column
                query = text(f"""
                    SELECT 
                        date_id,
                        var_name,
                        ST_Value(rast, {point_wkt}) AS point_value
                    FROM 
                        {table_name}
                    WHERE 
                        date_id BETWEEN :start_date AND :end_date
                        AND var_name = :variable
                        AND ST_Intersects(rast, {point_wkt})
                    ORDER BY date_id
                """)
                
                result_data = await db.execute(query, {
                    "start_date": start_date_obj,
                    "end_date": end_date_obj,
                    "variable": variable
                })
            else:
                # For sources without var_name column (like CHIRPS)
                query = text(f"""
                    SELECT 
                        date_id,
                        ST_Value(rast, {point_wkt}) AS point_value
                    FROM 
                        {table_name}
                    WHERE 
                        date_id BETWEEN :start_date AND :end_date
                        AND ST_Intersects(rast, {point_wkt})
                    ORDER BY date_id
                """)
                
                result_data = await db.execute(query, {
                    "start_date": start_date_obj,
                    "end_date": end_date_obj
                })
            
            # Process results
            rows = result_data.mappings().all()
            time_values = []
            
            for row in rows:
                # Skip null values
                if row["point_value"] is None:
                    continue
                    
                date_obj = row["date_id"]
                
                # Handle NaN values
                point_value = row["point_value"]
                if isinstance(point_value, float) and (math.isnan(point_value) or math.isinf(point_value)):
                    continue
                
                time_value = {
                    "date": date_obj.strftime("%Y-%m-%d"),
                    "year": date_obj.year,
                    "month": date_obj.month,
                    "values": {output_variable: point_value}
                }
                
                # Add day for daily cadence
                if DATA_SOURCE_CADENCE.get(data_source) == Cadence.DAILY:
                    time_value["day"] = date_obj.day
                
                time_values.append(time_value)
            
            # Only add point if it has data
            if time_values:
                point_data["values"] = time_values
                result["points"].append(point_data)
        
        # Calculate average time series across all points
        date_values = {}
        for point in result["points"]:
            for time_value in point["values"]:
                date = time_value["date"]
                if date not in date_values:
                    date_values[date] = {"sum": 0, "count": 0}
                
                if output_variable in time_value["values"] and time_value["values"][output_variable] is not None:
                    date_values[date]["sum"] += time_value["values"][output_variable]
                    date_values[date]["count"] += 1
        
        # Create average time series
        average_series = []
        for date, data in sorted(date_values.items()):
            if data["count"] > 0:
                date_obj = datetime.strptime(date, "%Y-%m-%d")
                avg_value = data["sum"] / data["count"]
                
                average_point = {
                    "date": date,
                    "year": date_obj.year,
                    "month": date_obj.month,
                    "values": {output_variable: avg_value}
                }
                
                # Add day for daily cadence
                if DATA_SOURCE_CADENCE.get(data_source) == Cadence.DAILY:
                    average_point["day"] = date_obj.day
                
                average_series.append(average_point)
        
        # Add average series to result
        result["average_series"] = average_series
        
        # Calculate monthly averages
        monthly_averages = {}
        for point in average_series:
            month_key = f"{point['year']}-{point['month']:02d}"
            if month_key not in monthly_averages:
                monthly_averages[month_key] = {"sum": 0, "count": 0}
            
            if output_variable in point["values"] and point["values"][output_variable] is not None:
                monthly_averages[month_key]["sum"] += point["values"][output_variable]
                monthly_averages[month_key]["count"] += 1
        
        # Create monthly average series
        monthly_series = []
        for month_key, data in sorted(monthly_averages.items()):
            if data["count"] > 0:
                year, month = map(int, month_key.split('-'))
                avg_value = data["sum"] / data["count"]
                
                monthly_series.append({
                    "year": year,
                    "month": month,
                    "value": avg_value
                })
        
        # Add monthly series to result
        result["monthly_averages"] = monthly_series
        
        # If we have no points, return a meaningful message
        if len(result["points"]) == 0:
            return {"message": "No data found for the specified parameters", "bbox": result["bbox"], "data_source": result["data_source"]}
        
        return sanitize_for_json(result)
    
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}\n{error_traceback}")
    
    
@app.get("/climate-data-grid-heatmap/")
async def get_climate_data_grid_heatmap(
    min_lat: float = Query(...),
    min_lon: float = Query(...),
    max_lat: float = Query(...),
    max_lon: float = Query(...),
    start_date: str = Query(...),
    end_date: str = Query(...),
    data_source: DataSource = Query(DataSource.CHIRPS),
    variable: str = Query("prec"),
    db: AsyncSession = Depends(get_db)
):
    try:
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")

    year = start_date_obj.year
    table_name = f"{data_source.value}_data_{year}"  # Assume partitions are named like chirps_data_2023

    query = text(f"""
        SELECT
            date,
            ST_Y(ST_Centroid(ST_Transform(grid.geom, 4326))) AS lat,
            ST_X(ST_Centroid(ST_Transform(grid.geom, 4326))) AS lon,
            AVG(grid.val) AS value
        FROM (
            SELECT
                date_id::date AS date,
                ST_SnapToGrid(ST_Transform((p).geom, 4326), 0.5, 0.5) AS geom,
                (p).val AS val
            FROM (
                SELECT
                    date_id,
                    ST_PixelAsPolygons(ST_Clip(rast, ST_MakeEnvelope(:min_lon, :min_lat, :max_lon, :max_lat, 4326), true)) AS p
                FROM {table_name}
                WHERE date_id BETWEEN :start_date AND :end_date
            ) AS sub
        ) AS grid
        WHERE grid.val IS NOT NULL
        GROUP BY date, grid.geom
        ORDER BY date;
    """)

    rows = (await db.execute(query, {
        "min_lat": min_lat,
        "min_lon": min_lon,
        "max_lat": max_lat,
        "max_lon": max_lon,
        "start_date": start_date_obj,
        "end_date": end_date_obj
    })).mappings().all()

    frames = {}
    max_precip = 0

    for row in rows:
        date = row['date'].strftime('%Y-%m-%d')
        if date not in frames:
            frames[date] = []
        frames[date].append({
            "lat": row["lat"],
            "lon": row["lon"],
            "value": row["value"]
        })
        if row["value"] > max_precip:
            max_precip = row["value"]

    heatmap_frames = [
        {"date": date, "points": points}
        for date, points in sorted(frames.items())
    ]

    return {
        "heatmap_frames": heatmap_frames,
        "max_precip": max_precip
    }
    
@app.get("/CSVGenerator", response_class=HTMLResponse)
async def get_csv_generator():
    with open("static/csv_generator.html", "r", encoding="utf-8") as f:
        return f.read()