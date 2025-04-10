# main.py
import time
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, Query, File, UploadFile, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db
from datetime import datetime, timedelta
from enum import Enum
import os, shutil, subprocess, uuid, json
from pathlib import Path
import asyncio

# Ensure necessary directories exist
os.makedirs("../Csv-Creator/uploads", exist_ok=True)
os.makedirs("../Csv-Creator/processed", exist_ok=True)

# Define your Enums (unchanged)
class DataSource(str, Enum):
    WORLDCLIM = "wc"
    SPEI = "spei"
    CHIRPS = "chirps"
    ET = "et"
    ELEVATION = "elev"
    SOILGRIDS = "sg"
    TERRACLIM = "tc" 
    NASAPOWER = "np"

class Variable(str, Enum):
    # Add your variables (truncated for brevity)
    PRECIPITATION = "prec"
    TMAX = "tmax"
    TMIN = "tmin"
    SPEI = "spei"
    ET = "et"
    CHIRPS = "chirps"

    # SoilGrids variables
    ELEVATION = "elev"  # Elevation
    BDOD = "bdod"       # Bulk density
    CEC = "cec"         # Cation exchange capacity
    CFVO = "cfvo"       # Coarse fragments volumetric
    CLAY = "clay"       # Clay content
    NITROGEN = "nitrogen" # Nitrogen
    OCD = "ocd"         # Organic carbon density
    OCS = "ocs"         # Organic carbon stock
    PHH2O = "phh2o"     # pH in H2O
    SAND = "sand"       # Sand content
    SILT = "silt"       # Silt content
    SOC = "soc"         # Soil organic carbon
    WV0010 = "wv0010"   # Water vapor content at 10cm depth
    WV0030 = "wv0030"   # Water vapor content at 30cm depth
    WV1500 = "wv1500"   # Water vapor content at 1500cm depth
    
    # TerraClim variables
    AET = "aet"         # Actual Evapotranspiration
    DEF = "def"         # Water Deficit
    PDSI = "pdsi"       # Palmer Drought Severity Index
    PET = "pet"         # Potential Evapotranspiration
    PPT = "ppt"         # Precipitation
    Q = "q"             # Runoff
    SOIL = "soil"       # Soil Moisture
    SRAD = "srad"       # Solar Radiation
    VAP = "vap"         # Vapor Pressure
    VPD = "vpd"         # Vapor Pressure Deficit
    WS = "ws"           # Wind Speed
    
    # NASA POWER variables
    AIRMASS = "airmass"
    ALLSKY_KT = "allsky_kt"
    ALLSKY_NKT = "allsky_nkt"
    ALLSKY_SFC_LW_DWN = "allsky_sfc_lw_dwn"
    ALLSKY_SFC_LW_UP = "allsky_sfc_lw_up"
    ALLSKY_SFC_PAR_DIFF = "allsky_sfc_par_diff"
    ALLSKY_SFC_PAR_DIRH = "allsky_sfc_par_dirh"
    ALLSKY_SFC_PAR_TOT = "allsky_sfc_par_tot"
    ALLSKY_SFC_SW_DIFF = "allsky_sfc_sw_diff"
    ALLSKY_SFC_SW_DIRH = "allsky_sfc_sw_dirh"
    ALLSKY_SFC_SW_DNI = "allsky_sfc_sw_dni"
    ALLSKY_SFC_SW_DWN = "allsky_sfc_sw_dwn"
    ALLSKY_SFC_SW_UP = "allsky_sfc_sw_up"
    ALLSKY_SFC_UV_INDEX = "allsky_sfc_uv_index"
    ALLSKY_SFC_UVA = "allsky_sfc_uva"
    ALLSKY_SFC_UVB = "allsky_sfc_uvb"
    ALLSKY_SRF_ALB = "allsky_srf_alb"
    AOD_55 = "aod_55"
    AOD_55_ADJ = "aod_55_adj"
    AOD_84 = "aod_84"
    CLOUD_AMT = "cloud_amt"
    CLOUD_AMT_DAY = "cloud_amt_day"
    CLOUD_AMT_NIGHT = "cloud_amt_night"
    CLOUD_OD = "cloud_od"
    CLRSKY_DAYS = "clrsky_days"
    CLRSKY_KT = "clrsky_kt"
    CLRSKY_NKT = "clrsky_nkt"
    CLRSKY_SFC_LW_DWN = "clrsky_sfc_lw_dwn"
    CLRSKY_SFC_LW_UP = "clrsky_sfc_lw_up"
    CLRSKY_SFC_PAR_DIFF = "clrsky_sfc_par_diff"
    CLRSKY_SFC_PAR_DIRH = "clrsky_sfc_par_dirh"
    CLRSKY_SFC_PAR_TOT = "clrsky_sfc_par_tot"
    CLRSKY_SFC_SW_DIFF = "clrsky_sfc_sw_diff"
    CLRSKY_SFC_SW_DIRH = "clrsky_sfc_sw_dirh"
    CLRSKY_SFC_SW_DNI = "clrsky_sfc_sw_dni"
    CLRSKY_SFC_SW_DWN = "clrsky_sfc_sw_dwn"
    CLRSKY_SFC_SW_UP = "clrsky_sfc_sw_up"
    CLRSKY_SRF_ALB = "clrsky_srf_alb"
    MIDDAY_INSOL = "midday_insol"
    ORIGINAL_ALLSKY_SFC_SW_DIFF = "original_allsky_sfc_sw_diff"
    ORIGINAL_ALLSKY_SFC_SW_DIRH = "original_allsky_sfc_sw_dirh"
    PSH = "psh"
    PW = "pw"
    SRF_ALB_ADJ = "srf_alb_adj"
    TOA_SW_DNI = "toa_sw_dni"
    TOA_SW_DWN = "toa_sw_dwn"
    TS_ADJ = "ts_adj"
    
class Cadence(str, Enum):
    DAILY = "daily"
    EIGHT_DAY = "8day"
    MONTHLY = "monthly"
    STATIC = "static"
    AGGREGATED = "aggregated"

# Helper functions used also by the shared module.
def get_table_name(data_source: DataSource, variable: Variable, year: int = None, month: int = None, day: int = None):
    if data_source == DataSource.WORLDCLIM:
        return f"{data_source.value}_{variable.value}_{year}_{month:02d}"
    elif data_source == DataSource.SPEI:
        return f"{data_source.value}_{year}_{month:02d}"
    elif data_source == DataSource.CHIRPS:
        if day is None:
            raise ValueError("Day is required for CHIRPS data source")
        return f"{data_source.value}_{year}_{month:02d}_{day:02d}"
    elif data_source == DataSource.ET:
        if day is None:
            raise ValueError("Day is required for ET data source")
        return f"{data_source.value}_{year}_{month:02d}_{day:02d}"
    elif data_source == DataSource.ELEVATION:
        return "elev"
    elif data_source == DataSource.SOILGRIDS:
        return f"sg_{variable.value}"
    elif data_source == DataSource.TERRACLIM:
        return f"terraclim_{variable.value}_{year}_{month:02d}"
    elif data_source == DataSource.NASAPOWER:
        return f"np_{variable.value}_{year}_{month:02d}"
    else:
        raise ValueError(f"Unknown data source: {data_source}")

def get_cadence_for_data_source(data_source: DataSource):
    if data_source in [DataSource.WORLDCLIM, DataSource.SPEI, DataSource.TERRACLIM, DataSource.NASAPOWER]:
        return Cadence.MONTHLY
    elif data_source == DataSource.CHIRPS:
        return Cadence.DAILY
    elif data_source == DataSource.ET:
        return Cadence.EIGHT_DAY
    elif data_source == DataSource.ELEVATION:
        return Cadence.STATIC
    elif data_source == DataSource.SOILGRIDS:
        return Cadence.AGGREGATED
    else:
        raise ValueError(f"Unknown data source: {data_source}")

# Import the shared logic:
from .climate_data_service import get_climate_data_timeseries_logic

app = FastAPI(title="Camcore Database API")

@app.get("/")
async def root():
    return {
        "message": "Welcome to the Camcore Database API",
        "available_data_sources": {
            "wc": "WorldClim (monthly: precipitation, tmax, tmin)",
            "spei": "SPEI (monthly)",
            "chirps": "CHIRPS (daily precipitation)",
            "et": "Evapotranspiration (8-day cadence)",
            "elev": "Elevation (static)",
            "sg": "SoilGrids (static soil properties)",
            "tc": "TerraClim (monthly climate data)",
            "np": "NASA POWER (monthly climate and solar data)"
        }
    }

@app.get("/climate-data-timeseries/")
async def get_climate_data_timeseries(
    lat: float = Query(..., description="Latitude coordinate"),
    lon: float = Query(..., description="Longitude coordinate"),
    start_date: Optional[str] = Query(None, description="Start date in YYYY-MM-DD format"),
    end_date: Optional[str] = Query(None, description="End date in YYYY-MM-DD format"),
    data_source: DataSource = Query(DataSource.WORLDCLIM, description="Data source (wc, spei, chirps, et, elev, sg)"),
    variable: Optional[Variable] = Query(None, description="Climate variable"),
    db: AsyncSession = Depends(get_db)
):
    # For time series data sources, require dates.
    if data_source not in [DataSource.ELEVATION, DataSource.SOILGRIDS]:
        if start_date is None or end_date is None:
            raise HTTPException(status_code=400, detail="start_date and end_date are required for time series data")
    
    result = await get_climate_data_timeseries_logic(lat, lon, start_date, end_date, data_source, variable, db)
    return result

# (Other endpoints and CSV generator endpoint remain largely the same.)
# For brevity, the rest of your endpoints (static file serving, CSV generator post, etc.) remain unchanged.

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/ui/", response_class=HTMLResponse)
async def get_ui():
    with open("static/timeseries.html", "r") as f:
        return f.read()

@app.get("/CSVGenerator", response_class=HTMLResponse)
async def get_csv_generator():
    with open("static/csv_generator.html", "r") as f:
        return f.read()

def wait_for_file(path, timeout=60):
    waited = 0
    while not path.exists() and waited < timeout:
        time.sleep(1)
        waited += 1
    return path.exists()

@app.post("/api/process-csv")
async def process_csv(
    file: UploadFile = File(...),
    option: str = Form(...)
):
    print("Current Working Directory:", os.getcwd())
    # (set up directories and save file, as you already do)
    job_id = str(uuid.uuid4())
    upload_dir = Path(f"../Csv-Creator/uploads/{job_id}")
    processed_dir = Path(f"../Csv-Creator/processed/{job_id}")
    os.makedirs(upload_dir, exist_ok=True)
    os.makedirs(processed_dir, exist_ok=True)
    file_path = upload_dir / file.filename
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        print("File saved successfully.")
    except Exception as e:
        print("Error saving file:", e)
        raise HTTPException(status_code=500, detail=f"Error saving file: {e}")

    raw_data_path = processed_dir / f"raw_data_{file.filename}"
    covariates_path = processed_dir / f"covariates_{file.filename}"
    
    try:
        raw_data_script = "../Csv-Creator/script.py"
        subprocess.run([
            "python", raw_data_script,
            "--input", str(file_path),
            "--output", str(raw_data_path),
            "--default-start-date", "2000-01-01",
            "--default-end-date", "2000-12-31",
            "--all-variables",
            "--cache-file", f"{processed_dir}/cache.json"
        ], check=True)
        
        if option == "full":
            covariates_script = "../Csv-Creator/covariablesv3.py"
            subprocess.run([
                "python", covariates_script,
                "--input", str(raw_data_path),
                "--output", str(covariates_path)
            ], check=True)
        
        # Poll until the raw data file exists (timeout after, say, 60 seconds)
        if not wait_for_file(raw_data_path):
            raise HTTPException(status_code=500, detail="Raw data file was not created in time.")
        if option == "full" and not wait_for_file(covariates_path):
            raise HTTPException(status_code=500, detail="Covariates file was not created in time.")

        if option == "full":
            return {
                "message": "Processing complete.",
                "jobId": job_id,
                "rawDataFile": f"/download/{job_id}/raw_data_{file.filename}",
                "covariatesFile": f"/download/{job_id}/covariates_{file.filename}"
            }
        else:
            return {
                "message": "Processing complete.",
                "jobId": job_id,
                "rawDataFile": f"/download/{job_id}/raw_data_{file.filename}"
            }
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@app.get("/download/{job_id}/{filename}")
async def download_file(job_id: str, filename: str):
    file_path = Path(f"../Csv-Creator/processed/{job_id}/{filename}")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=file_path, filename=filename, media_type="application/octet-stream")

# @app.post("/test-upload/")
# async def test_upload(file: UploadFile = File(...)):
#     print("Test upload file:", file.filename)
#     path = Path("../Csv-Creator/uploads/test_" + file.filename)
#     try:
#         with open(path, "wb") as f:
#             content = await file.read()
#             f.write(content)
#         return {"message": "File saved", "path": str(path.resolve())}
#     except Exception as e:
#         return {"message": "Error saving file", "error": str(e)}