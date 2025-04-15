from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import get_db
from typing import Optional, List, Literal, Callable
from datetime import datetime, timedelta
from enum import Enum
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import os


# Update DataSource and Variable Enums
class DataSource(str, Enum):
    WORLDCLIM = "wc"
    SPEI = "spei"
    CHIRPS = "chirps"
    ET = "et"
    ELEVATION = "elev"
    SOILGRIDS = "sg"
    TERRACLIM = "tc"    # Added TerraClim
    NASAPOWER = "np"    # Added NASA POWER

class Variable(str, Enum):
    # Weather and Climate variables
    CHIRPS = "chirps"
    PRECIPITATION = "prec"
    TMAX = "tmax"
    TMIN = "tmin"
    SPEI = "spei"
    ET = "et"
    
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
    DAILY = "daily"         # For CHIRPS
    EIGHT_DAY = "8day"      # For ET
    MONTHLY = "monthly"     # For WorldClim, SPEI
    STATIC = "static"       # For Elevation
    AGGREGATED = "aggregated" # For SoilGrids

app = FastAPI(title="Camcore Database API")



def get_table_name(data_source: DataSource, variable: Variable, year: Optional[int] = None, 
                  month: Optional[int] = None, day: Optional[int] = None):
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
    if data_source == DataSource.WORLDCLIM or data_source == DataSource.SPEI or data_source == DataSource.TERRACLIM or data_source == DataSource.NASAPOWER:
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

def validate_date_params(data_source: DataSource, year: int, month: int, day: Optional[int] = None):
    cadence = get_cadence_for_data_source(data_source)
    
    if not (1 <= month <= 12):
        raise HTTPException(status_code=400, detail="Month must be between 1 and 12")
    
    if cadence == Cadence.DAILY:
        if day is None:
            raise HTTPException(status_code=400, detail="Day parameter is required for CHIRPS data source")
        days_in_month = [0, 31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]  
        if not (1 <= day <= days_in_month[month]):
            raise HTTPException(status_code=400, detail=f"Day must be between 1 and {days_in_month[month]} for month {month}")
    
    elif cadence == Cadence.EIGHT_DAY:
        if day is None:
            raise HTTPException(status_code=400, detail="Day parameter is required for ET data source")
        
        try:
            check_date = datetime(year, month, day)
            baseline = datetime(2000, 1, 1)
            
            if check_date < baseline:
                raise HTTPException(
                    status_code=400, 
                    detail=f"ET data is only available from 2000-01-01 onwards."
                )
            
            days_diff = (check_date - baseline).days
            if days_diff % 8 != 0:
                days_to_next = 8 - (days_diff % 8)
                next_valid_date = check_date + timedelta(days=days_to_next)
                
                days_to_prev = days_diff % 8
                prev_valid_date = check_date - timedelta(days=days_to_prev)
                
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invalid ET date. ET data is available every 8 days starting from 2000-01-01. " + 
                        f"The nearest valid dates are {prev_valid_date.strftime('%Y-%m-%d')} and {next_valid_date.strftime('%Y-%m-%d')}."
                )
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date")
        
def get_variable_param(
    data_source: DataSource = Query(DataSource.WORLDCLIM, description="Data source (wc, spei, chirps, et, elev, sg)")
) -> Optional[Variable]:
    """Dependency that only requests variable parameter if data_source is WorldClim"""
    if data_source == DataSource.WORLDCLIM:
        return Query(None, description="Climate variable (prec, tmax, tmin)")
    if data_source == DataSource.NASAPOWER:
        return Query(None, description="NASA POWER variable (airmass, allsky_kt, etc.)")
    if data_source == DataSource.TERRACLIM:
        return Query(None, description="TerraClim variable (aet, def, pdsi, etc.)")
    return None
       
def is_valid_et_date(date_obj: datetime) -> bool:
    """Check if a date is a valid ET date (follows the 8-day cadence from 2000-01-01)"""
    start_date = datetime(2000, 1, 1)
    
    if date_obj < start_date:
        return False
    
    days_diff = (date_obj - start_date).days
    
    return days_diff % 8 == 0

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

@app.get("/available-data/")
async def get_available_data():
    return {
        "data_sources": {
            "wc": {
                "description": "WorldClim - Monthly climate data",
                "variables": ["prec", "tmax", "tmin"],
                "cadence": "monthly",
                "unit": ["mm", "°C", "°C"]
            },
            "spei": {
                "description": "Standardized Precipitation Evapotranspiration Index",
                "variables": ["spei"],
                "cadence": "monthly",
                "unit": "no unit"
            },
            "chirps": {
                "description": "Climate Hazards Group InfraRed Precipitation with Station data",
                "variables": ["prec"],
                "cadence": "daily",
                "unit": "mm"
            },
            "et": {
                "description": "Evapotranspiration data",
                "variables": ["et"],
                "cadence": "8day",
                "unit": "mm"
            },
            "elev": {
                "description": "Elevation data",
                "variables": ["elev"],
                "cadence": "static",
                "unit": "m"
            },
            "sg": {
                "description": "SoilGrids - Soil properties",
                "variables": ["bdod", "cec", "cfvo", "clay", "nitrogen", "ocd", "ocs", "phh2o", "sand", "silt", "soc", "wv0010", "wv0030", "wv1500"],
                "cadence": "static",
                "unit": "various"
            },
            "tc": {
                "description": "TerraClim - Monthly climate data",
                "variables": ["aet", "def", "pdsi", "pet", "ppt", "q", "soil", "srad", "tmax", "tmin", "vap", "vpd", "ws"],
                "cadence": "monthly",
                "unit": ["mm", "mm", "mm", "mm", "mm", "mm", "W/m2", "mm", "C", "C", "kPa", "m/s", "kPa", "unitless"]
            },
            "np": {
                "description": "NASA POWER - Monthly climate and solar radiation data",
                "variables": ["airmass", "allsky_kt", "allsky_nkt", "allsky_sfc_lw_dwn", "allsky_sfc_lw_up", "allsky_sfc_par_diff", 
                             "allsky_sfc_par_dirh", "allsky_sfc_par_tot", "allsky_sfc_sw_diff", "allsky_sfc_sw_dirh", 
                             "allsky_sfc_sw_dni", "allsky_sfc_sw_dwn", "allsky_sfc_sw_up", "allsky_sfc_uv_index", 
                             "allsky_sfc_uva", "allsky_sfc_uvb", "allsky_srf_alb", "aod_55", "aod_55_adj", "aod_84", 
                             "cloud_amt", "cloud_amt_day", "cloud_amt_night", "cloud_od", "clrsky_days", "clrsky_kt", 
                             "clrsky_nkt", "clrsky_sfc_lw_dwn", "clrsky_sfc_lw_up", "clrsky_sfc_par_diff", "clrsky_sfc_par_dirh", 
                             "clrsky_sfc_par_tot", "clrsky_sfc_sw_diff", "clrsky_sfc_sw_dirh", "clrsky_sfc_sw_dni", 
                             "clrsky_sfc_sw_dwn", "clrsky_sfc_sw_up", "clrsky_srf_alb", "midday_insol", 
                             "original_allsky_sfc_sw_diff", "original_allsky_sfc_sw_dirh", "psh", "pw", "srf_alb_adj", 
                             "toa_sw_dni", "toa_sw_dwn", "ts_adj"],
                "cadence": "monthly",
                "unit": ["dimensionless", "dimensionless", "dimensionless", "W m-2", "W m-2", "W m-2", "W m-2", "W m-2", "W m-2", "W m-2", "W m-2", "W m-2", "W m-2", "W m-2", "W m-2", "W m-2 x 40", "dimensionless", "dimensionless", "dimensionless", "dimensionless", "%", "%", "%", "dimensionless", "Days", "dimensionless", "dimensionless", "W m-2", "W m-2", "W m-2", "W m-2", "W m-2", "W m-2", "W m-2", "W m-2", "W m-2", "W m-2", "dimensionless", "W m-2", "W m-2", "cm", "dimensionless", "W m-2", "W m-2", "C"]
            }
        }
    }
    
@app.get("/climate-data-timeseries/")
async def get_climate_data_timeseries(
    lat: float = Query(..., description="Latitude coordinate"),
    lon: float = Query(..., description="Longitude coordinate"),
    start_date: Optional[str] = Query(None, description="Start date in YYYY-MM-DD format (not required for Elevation or SoilGrids)"),
    end_date: Optional[str] = Query(None, description="End date in YYYY-MM-DD format (not required for Elevation or SoilGrids)"),
    data_source: DataSource = Query(DataSource.WORLDCLIM, description="Data source (wc, spei, chirps, et, elev, sg)"),
    variable: Optional[Variable] = Query(None, description="Climate variable (prec, tmax, tmin, spei, et, elev, bdod, cec, etc.)"),
    db: AsyncSession = Depends(get_db)
):
    # Validate inputs
    if not (-90 <= lat <= 90):
        raise HTTPException(status_code=400, detail="Latitude must be between -90 and 90")
    if not (-180 <= lon <= 180):
        raise HTTPException(status_code=400, detail="Longitude must be between -180 and 180")
    
    # For static data sources (Elevation and SoilGrids), handle differently
    if data_source in [DataSource.ELEVATION, DataSource.SOILGRIDS]:
        # Set default variable based on data source if not provided
        # if variable is None:
        #     if data_source == DataSource.ELEVATION:
        #         variable = Variable.ELEVATION
        #     elif data_source == DataSource.SOILGRIDS:
        #         variable = Variable.BDOD  # Default to bulk density for SoilGrids
        # Set default variable based on data source if not provided
        if variable is None:
            if data_source == DataSource.WORLDCLIM:
                variable = Variable.PRECIPITATION
            elif data_source == DataSource.SPEI:
                variable = Variable.SPEI
            elif data_source == DataSource.CHIRPS:
                variable = Variable.CHIRPS
            elif data_source == DataSource.ET:
                variable = Variable.ET
            elif data_source == DataSource.TERRACLIM:
                variable = Variable.PPT  # Default to precipitation for TerraClim
            elif data_source == DataSource.NASAPOWER:
                variable = Variable.ALLSKY_SFC_SW_DWN  # Default to all-sky surface SW down for NASA POWER
        
        # Validate variable-data source compatibility
        if data_source == DataSource.WORLDCLIM and variable not in [Variable.PRECIPITATION, Variable.TMAX, Variable.TMIN]:
            raise HTTPException(status_code=400, detail=f"WorldClim only supports these variables: prec, tmax, tmin")
        elif data_source == DataSource.SPEI and variable != Variable.SPEI:
            raise HTTPException(status_code=400, detail="SPEI data source only supports spei variable")
        elif data_source == DataSource.CHIRPS and variable != Variable.CHIRPS:
            raise HTTPException(status_code=400, detail="CHIRPS data source only supports chirps variable")
        elif data_source == DataSource.ET and variable != Variable.ET:
            raise HTTPException(status_code=400, detail="ET data source only supports et variable")
        elif data_source == DataSource.TERRACLIM and variable not in [
            Variable.AET, Variable.DEF, Variable.PDSI, Variable.PET, Variable.PPT,
            Variable.Q, Variable.SOIL, Variable.SRAD, Variable.TMAX, Variable.TMIN,
            Variable.VAP, Variable.VPD, Variable.WS
        ]:           
            raise HTTPException(status_code=400, detail="Invalid TerraClim variable")
        elif data_source == DataSource.NASAPOWER and not variable.value.startswith(("allsky_", "clrsky_", "airmass", "aod_", "cloud_", "midday_", "original_", "psh", "pw", "srf_", "toa_", "ts_")):
            raise HTTPException(status_code=400, detail="Invalid NASA POWER variable")
    
        
        # Validate variable-data source compatibility
        if data_source == DataSource.ELEVATION and variable != Variable.ELEVATION:
            raise HTTPException(status_code=400, detail="Elevation data source only supports elev variable")
        elif data_source == DataSource.SOILGRIDS and variable not in [
            Variable.BDOD, Variable.CEC, Variable.CFVO, Variable.CLAY, Variable.NITROGEN,
            Variable.OCD, Variable.OCS, Variable.PHH2O, Variable.SAND, Variable.SILT, Variable.SOC, Variable.WV0010, Variable.WV0030, Variable.WV1500
        ]:
            raise HTTPException(status_code=400, detail="Invalid SoilGrids variable")
        
        # Define the point for PostGIS query
        point = f'POINT({lon} {lat})'
        
        # Get cadence for the selected data source
        cadence = get_cadence_for_data_source(data_source)
        
        # Prepare the results structure
        results = {
            "lon": lon,
            "lat": lat,
            "wkt": f"POINT({lon} {lat})",
            "data_source": data_source.value,
            "variable": variable.value,
            "cadence": cadence.value,
            "values": []
        }
        
        try:
            table_name = get_table_name(data_source, variable)
            
            # Build the query to get the raster value for the point
            query = text(f"""
                SELECT 
                    {lon} AS lon, 
                    {lat} AS lat,
                    ST_Value(rast, ST_SetSRID(ST_GeomFromText('{point}'), 4326)) AS value
                FROM {table_name} 
                WHERE ST_Intersects(rast, ST_SetSRID(ST_GeomFromText('{point}'), 4326))
                LIMIT 1
            """)
            
            # Execute the query
            result = await db.execute(query)
            row = result.mappings().first()
            
            if not row or row['value'] is None:
                return {
                    "message": f"No data found at specified coordinates for {data_source.value}-{variable.value}",
                    "lon": lon,
                    "lat": lat,
                    "data_source": data_source.value,
                    "variable": variable.value,
                    "cadence": cadence.value,
                    "values": []
                }
            
            # For static data, we still use a time series structure but with a single value
            # This allows the frontend to handle it consistently
            value = row['value']
            
            results["values"].append({
                "value": value,
                # No date/time information for static data
            })
            
            return results
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    
    # For time series data sources, continue with regular processing
    # Require start_date and end_date for time series data
    if start_date is None or end_date is None:
        raise HTTPException(status_code=400, detail="start_date and end_date are required for time series data")
    
    # Set default variable based on data source if not provided
    if variable is None:
        if data_source == DataSource.WORLDCLIM:
            variable = Variable.PRECIPITATION
        elif data_source == DataSource.SPEI:
            variable = Variable.SPEI
        elif data_source == DataSource.CHIRPS:
            variable = Variable.CHIRPS
        elif data_source == DataSource.ET:
            variable = Variable.ET
    
    # Validate variable-data source compatibility
    if data_source == DataSource.WORLDCLIM and variable not in [Variable.PRECIPITATION, Variable.TMAX, Variable.TMIN]:
        raise HTTPException(status_code=400, detail=f"WorldClim only supports these variables: prec, tmax, tmin")
    elif data_source == DataSource.SPEI and variable != Variable.SPEI:
        raise HTTPException(status_code=400, detail="SPEI data source only supports spei variable")
    elif data_source == DataSource.CHIRPS and variable != Variable.CHIRPS:
        raise HTTPException(status_code=400, detail="CHIRPS data source only supports chirps variable")
    elif data_source == DataSource.ET and variable != Variable.ET:
        raise HTTPException(status_code=400, detail="ET data source only supports et variable")
    
    # Parse start and end dates for time series data sources
    try:
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    
    if end_date_obj < start_date_obj:
        raise HTTPException(status_code=400, detail="End date must be greater than or equal to start date.")
    
    # Define the point for PostGIS query
    point = f'POINT({lon} {lat})'
    
    # Get cadence for the selected data source
    cadence = get_cadence_for_data_source(data_source)
    
    results = {
        "lon": lon,
        "lat": lat,
        "wkt": f"POINT({lon} {lat})",
        "data_source": data_source.value,
        "variable": variable.value,
        "cadence": cadence.value,
        "values": []
    }
    
    # Function to check if a table exists in the database
    async def table_exists(table_name):
        check_query = text(f"""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = '{table_name}'
            );
        """)
        
        try:
            result = await db.execute(check_query)
            return result.scalar()
        except Exception:
            return False
    
    # Handle different cadences with appropriate methods
    if cadence == Cadence.MONTHLY:
        # For WorldClim and SPEI (monthly cadence)
        current_date = datetime(start_date_obj.year, start_date_obj.month, 1)
        end_month = datetime(end_date_obj.year, end_date_obj.month, 1)
        
        while current_date <= end_month:
            year = current_date.year
            month = current_date.month
            date_key = f"{year}-{month:02d}"
            
            try:
                table_name = get_table_name(data_source, variable, year, month)
                
                # Check if table exists before querying
                if await table_exists(table_name):
                    query = text(f"""
                        SELECT ST_Value(rast, ST_SetSRID(ST_GeomFromText('{point}'), 4326)) AS value 
                        FROM {table_name} 
                        WHERE ST_Intersects(rast, ST_SetSRID(ST_GeomFromText('{point}'), 4326))
                        LIMIT 1
                    """)
                    
                    try:
                        result = await db.execute(query)
                        row = result.mappings().first()
                        value = row['value'] if row and 'value' in row else None
                        
                        results["values"].append({
                            "date": date_key,
                            "year": year,
                            "month": month,
                            "value": value
                        })
                    except Exception as e:
                        results["values"].append({
                            "date": date_key,
                            "year": year,
                            "month": month,
                            "value": None,
                            "error": f"Query error: {str(e)}"
                        })
                else:
                    # Table doesn't exist
                    results["values"].append({
                        "date": date_key,
                        "year": year,
                        "month": month,
                        "value": None,
                        "error": "No data available for this date"
                    })
            except ValueError as e:
                # Handle errors in table name generation
                results["values"].append({
                    "date": date_key,
                    "year": year,
                    "month": month,
                    "value": None,
                    "error": str(e)
                })
            
            # Move to the next month
            if current_date.month == 12:
                current_date = datetime(current_date.year + 1, 1, 1)
            else:
                current_date = datetime(current_date.year, current_date.month + 1, 1)
                
    elif cadence == Cadence.DAILY:
        # For CHIRPS (daily cadence)
        current_date = start_date_obj
        
        while current_date <= end_date_obj:
            year = current_date.year
            month = current_date.month
            day = current_date.day
            date_key = f"{year}-{month:02d}-{day:02d}"
            
            try:
                table_name = get_table_name(data_source, variable, year, month, day)
                
                # Check if table exists before querying
                if await table_exists(table_name):
                    query = text(f"""
                        SELECT ST_Value(rast, ST_SetSRID(ST_GeomFromText('{point}'), 4326)) AS value 
                        FROM {table_name} 
                        WHERE ST_Intersects(rast, ST_SetSRID(ST_GeomFromText('{point}'), 4326))
                        LIMIT 1
                    """)
                    
                    try:
                        result = await db.execute(query)
                        row = result.mappings().first()
                        value = row['value'] if row and 'value' in row else None
                        
                        results["values"].append({
                            "date": date_key,
                            "year": year,
                            "month": month,
                            "day": day,
                            "value": value
                        })
                    except Exception as e:
                        results["values"].append({
                            "date": date_key,
                            "year": year,
                            "month": month,
                            "day": day,
                            "value": None,
                            "error": f"Query error: {str(e)}"
                        })
                else:
                    # Table doesn't exist
                    results["values"].append({
                        "date": date_key,
                        "year": year,
                        "month": month,
                        "day": day,
                        "value": None,
                        "error": "No data available for this date"
                    })
            except ValueError as e:
                # Handle errors in table name generation
                results["values"].append({
                    "date": date_key,
                    "year": year,
                    "month": month,
                    "day": day,
                    "value": None,
                    "error": str(e)
                })
            
            # Move to the next day
            current_date += timedelta(days=1)
            
    elif cadence == Cadence.EIGHT_DAY:
        # For ET (8-day cadence)
        # Get a list of all ET tables in the database that fall within the date range
        
        # Build a query to find all relevant ET tables in the database
        tables_query = text(f"""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_name LIKE 'et\_%' 
            AND table_schema = 'public'
            ORDER BY table_name
        """)
        
        try:
            tables_result = await db.execute(tables_query)
            et_tables = [row['table_name'] for row in tables_result.mappings().all()]
            
            # Filter tables to only include those in the requested date range
            filtered_tables = []
            for table in et_tables:
                # Parse the date from table name (et_YYYY_MM_DD format)
                try:
                    parts = table.split('_')
                    if len(parts) == 4:
                        year = int(parts[1])
                        month = int(parts[2])
                        day = int(parts[3])
                        
                        table_date = datetime(year, month, day)
                        if start_date_obj <= table_date <= end_date_obj:
                            filtered_tables.append({
                                "table": table,
                                "date": table_date,
                                "year": year,
                                "month": month,
                                "day": day
                            })
                except (ValueError, IndexError):
                    # Skip tables that don't match our expected format
                    continue
            
            # Sort the filtered tables by date
            filtered_tables.sort(key=lambda x: x["date"])
            
            # Now query each table in the filtered list
            for table_info in filtered_tables:
                table_name = table_info["table"]
                year = table_info["year"]
                month = table_info["month"]
                day = table_info["day"]
                date_key = f"{year}-{month:02d}-{day:02d}"
                
                # Define the query for this table
                query = text(f"""
                    SELECT ST_Value(rast, ST_SetSRID(ST_GeomFromText('{point}'), 4326)) AS value 
                    FROM {table_name} 
                    WHERE ST_Intersects(rast, ST_SetSRID(ST_GeomFromText('{point}'), 4326))
                    LIMIT 1
                """)
                
                try:
                    result = await db.execute(query)
                    row = result.mappings().first()
                    value = row['value'] if row and 'value' in row else None
                    
                    results["values"].append({
                        "date": date_key,
                        "year": year,
                        "month": month,
                        "day": day,
                        "value": value
                    })
                except Exception as e:
                    results["values"].append({
                        "date": date_key,
                        "year": year,
                        "month": month,
                        "day": day,
                        "value": None,
                        "error": f"Query error: {str(e)}"
                    })
        
        except Exception as e:
            # Handle any errors in the table lookup process
            results["error"] = f"Error retrieving ET tables: {str(e)}"
    
    return results

@app.get("/climate-data-bbox/")
async def get_climate_data_bbox(
    min_lon: float = Query(..., description="Minimum longitude coordinate"),
    min_lat: float = Query(..., description="Minimum latitude coordinate"),
    max_lon: float = Query(..., description="Maximum longitude coordinate"),
    max_lat: float = Query(..., description="Maximum latitude coordinate"),
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    data_source: DataSource = Query(DataSource.WORLDCLIM, description="Data source"),
    variable: Optional[Variable] = Query(None, description="Climate variable"),
    max_points: int = Query(100, description="Maximum number of points to return"),
    db: AsyncSession = Depends(get_db)
):
    # Validate inputs
    if not (-90 <= min_lat <= 90) or not (-90 <= max_lat <= 90):
        raise HTTPException(status_code=400, detail="Latitude must be between -90 and 90")
    if not (-180 <= min_lon <= 180) or not (-180 <= max_lon <= 180):
        raise HTTPException(status_code=400, detail="Longitude must be between -180 and 180")
    if min_lat > max_lat:
        raise HTTPException(status_code=400, detail="min_lat must be less than or equal to max_lat")
    if min_lon > max_lon:
        raise HTTPException(status_code=400, detail="min_lon must be less than or equal to max_lon")
    
    # Set default variable based on data source if not provided
    if variable is None:
        if data_source == DataSource.WORLDCLIM:
            variable = Variable.PRECIPITATION
        elif data_source == DataSource.SPEI:
            variable = Variable.SPEI
        elif data_source == DataSource.CHIRPS:
            variable = Variable.CHIRPS
        elif data_source == DataSource.ET:
            variable = Variable.ET
        elif data_source == DataSource.ELEVATION:
            variable = Variable.ELEVATION
        elif data_source == DataSource.SOILGRIDS:
            variable = Variable.BDOD
        elif data_source == DataSource.TERRACLIM:
            variable = Variable.PPT
        elif data_source == DataSource.NASAPOWER:
            variable = Variable.ALLSKY_SFC_SW_DWN
            
    # Create random points within the bounding box (up to max_points)
    import random
    random_points = []
    for _ in range(max_points):
        lat = min_lat + random.random() * (max_lat - min_lat)
        lon = min_lon + random.random() * (max_lon - min_lon)
        random_points.append({"lat": round(lat, 6), "lon": round(lon, 6)})
    
    # For time series data sources like WorldClim, SPEI, etc.
    try:
        date_obj = datetime.strptime(date, "%Y-%m-%d")
        year = date_obj.year
        month = date_obj.month
        day = date_obj.day
        
        # Get table name based on data source and date
        try:
            if data_source in [DataSource.WORLDCLIM, DataSource.SPEI, DataSource.TERRACLIM, DataSource.NASAPOWER]:
                # For monthly data
                table_name = get_table_name(data_source, variable, year, month)
            elif data_source == DataSource.CHIRPS:
                # For daily data
                table_name = get_table_name(data_source, variable, year, month, day)
            elif data_source == DataSource.ET:
                # For 8-day data
                table_name = get_table_name(data_source, variable, year, month, day)
            elif data_source in [DataSource.ELEVATION, DataSource.SOILGRIDS]:
                # For static data
                table_name = get_table_name(data_source, variable)
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported data source: {data_source}")
                
            # Check if table exists
            check_query = text(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = '{table_name}'
                );
            """)
            
            result = await db.execute(check_query)
            exists = result.scalar()
            
            if not exists:
                return {
                    "message": f"No data available for {data_source.value} {variable.value} at {date}",
                    "bbox": {
                        "min_lon": min_lon,
                        "min_lat": min_lat,
                        "max_lon": max_lon,
                        "max_lat": max_lat
                    },
                    "data_source": data_source.value,
                    "variable": variable.value,
                    "date": date,
                    "points": []
                }
            
            # Query values at each random point
            points_with_values = []
            
            for point in random_points:
                lat = point["lat"]
                lon = point["lon"]
                point_wkt = f"POINT({lon} {lat})"
                
                query = text(f"""
                    SELECT 
                        ST_Value(rast, ST_SetSRID(ST_GeomFromText('{point_wkt}'), 4326)) AS value
                    FROM {table_name} 
                    WHERE ST_Intersects(rast, ST_SetSRID(ST_GeomFromText('{point_wkt}'), 4326))
                    LIMIT 1
                """)
                
                result = await db.execute(query)
                row = result.mappings().first()
                
                if row and row['value'] is not None:
                    points_with_values.append({
                        "lat": lat,
                        "lon": lon,
                        "value": row['value']
                    })
            
            # Return the results
            return {
                "bbox": {
                    "min_lon": min_lon,
                    "min_lat": min_lat,
                    "max_lon": max_lon,
                    "max_lat": max_lat
                },
                "data_source": data_source.value,
                "variable": variable.value,
                "date": date,
                "points": points_with_values
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")
            
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

@app.get("/climate-data-bbox-timeseries/")
async def get_climate_data_bbox_timeseries(
    min_lon: float = Query(..., description="Minimum longitude coordinate"),
    min_lat: float = Query(..., description="Minimum latitude coordinate"),
    max_lon: float = Query(..., description="Maximum longitude coordinate"),
    max_lat: float = Query(..., description="Maximum latitude coordinate"),
    start_date: str = Query(..., description="Start date in YYYY-MM-DD format"),
    end_date: str = Query(..., description="End date in YYYY-MM-DD format"),
    data_source: DataSource = Query(DataSource.WORLDCLIM, description="Data source"),
    variable: Optional[Variable] = Query(None, description="Climate variable"),
    max_points: int = Query(5, description="Maximum number of random points to sample"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get time series climate data for multiple random points within a bounding box.
    Returns up to max_points random sample points with climate time series data.
    """
    # Validate inputs
    if not (-90 <= min_lat <= 90) or not (-90 <= max_lat <= 90):
        raise HTTPException(status_code=400, detail="Latitude must be between -90 and 90")
    if not (-180 <= min_lon <= 180) or not (-180 <= max_lon <= 180):
        raise HTTPException(status_code=400, detail="Longitude must be between -180 and 180")
    if min_lat > max_lat:
        raise HTTPException(status_code=400, detail="min_lat must be less than or equal to max_lat")
    if min_lon > max_lon:
        raise HTTPException(status_code=400, detail="min_lon must be less than or equal to max_lon")
    
    # Set default variable based on data source if not provided
    if variable is None:
        if data_source == DataSource.WORLDCLIM:
            variable = Variable.PRECIPITATION
        elif data_source == DataSource.SPEI:
            variable = Variable.SPEI
        elif data_source == DataSource.CHIRPS:
            variable = Variable.CHIRPS
        elif data_source == DataSource.ET:
            variable = Variable.ET
        elif data_source == DataSource.TERRACLIM:
            variable = Variable.PPT
        elif data_source == DataSource.NASAPOWER:
            variable = Variable.ALLSKY_SFC_SW_DWN
    
    # Check if data source is static
    if data_source in [DataSource.ELEVATION, DataSource.SOILGRIDS]:
        raise HTTPException(status_code=400, detail="Time series not available for static data sources")
    
    # Parse dates
    try:
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
    
    if end_date_obj < start_date_obj:
        raise HTTPException(status_code=400, detail="End date must be greater than or equal to start date.")
    
    # Create random points within the bounding box
    import random
    random_points = []
    for _ in range(max_points):
        lat = min_lat + random.random() * (max_lat - min_lat)
        lon = min_lon + random.random() * (max_lon - min_lon)
        random_points.append({"lat": round(lat, 6), "lon": round(lon, 6)})
    
    # Get cadence for the data source
    cadence = get_cadence_for_data_source(data_source)
    
    # Initialize result structure
    result = {
        "bbox": {
            "min_lon": min_lon,
            "min_lat": min_lat,
            "max_lon": max_lon,
            "max_lat": max_lat
        },
        "data_source": data_source.value,
        "variable": variable.value,
        "cadence": cadence.value,
        "start_date": start_date,
        "end_date": end_date,
        "points": []
    }
    
    # Process points based on cadence
    for point in random_points:
        lat = point["lat"]
        lon = point["lon"]
        point_wkt = f"POINT({lon} {lat})"
        point_values = []
        
        # Function to check if a table exists
        async def table_exists(table_name):
            check_query = text(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = '{table_name}'
                );
            """)
            
            try:
                result = await db.execute(check_query)
                return result.scalar()
            except Exception:
                return False
        
        if cadence == Cadence.MONTHLY:
            # For WorldClim, SPEI, TerraClim, NASA POWER (monthly cadence)
            current_date = datetime(start_date_obj.year, start_date_obj.month, 1)
            end_month = datetime(end_date_obj.year, end_date_obj.month, 1)
            
            while current_date <= end_month:
                year = current_date.year
                month = current_date.month
                date_key = f"{year}-{month:02d}"
                
                try:
                    table_name = get_table_name(data_source, variable, year, month)
                    
                    # Check if table exists before querying
                    if await table_exists(table_name):
                        query = text(f"""
                            SELECT ST_Value(rast, ST_SetSRID(ST_GeomFromText('{point_wkt}'), 4326)) AS value 
                            FROM {table_name} 
                            WHERE ST_Intersects(rast, ST_SetSRID(ST_GeomFromText('{point_wkt}'), 4326))
                            LIMIT 1
                        """)
                        
                        try:
                            query_result = await db.execute(query)
                            row = query_result.mappings().first()
                            value = row['value'] if row and 'value' in row else None
                            
                            if value is not None:
                                point_values.append({
                                    "date": date_key,
                                    "year": year,
                                    "month": month,
                                    "value": value
                                })
                        except Exception:
                            # Skip if error
                            pass
                    
                except Exception:
                    # Skip if error
                    pass
                
                # Move to next month
                if current_date.month == 12:
                    current_date = datetime(current_date.year + 1, 1, 1)
                else:
                    current_date = datetime(current_date.year, current_date.month + 1, 1)
        
        elif cadence == Cadence.DAILY:
            # For CHIRPS (daily cadence)
            current_date = start_date_obj
            
            while current_date <= end_date_obj:
                year = current_date.year
                month = current_date.month
                day = current_date.day
                date_key = f"{year}-{month:02d}-{day:02d}"
                
                try:
                    table_name = get_table_name(data_source, variable, year, month, day)
                    
                    # Check if table exists before querying
                    if await table_exists(table_name):
                        query = text(f"""
                            SELECT ST_Value(rast, ST_SetSRID(ST_GeomFromText('{point_wkt}'), 4326)) AS value 
                            FROM {table_name} 
                            WHERE ST_Intersects(rast, ST_SetSRID(ST_GeomFromText('{point_wkt}'), 4326))
                            LIMIT 1
                        """)
                        
                        try:
                            query_result = await db.execute(query)
                            row = query_result.mappings().first()
                            value = row['value'] if row and 'value' in row else None
                            
                            if value is not None:
                                point_values.append({
                                    "date": date_key,
                                    "year": year,
                                    "month": month,
                                    "day": day,
                                    "value": value
                                })
                        except Exception:
                            # Skip if error
                            pass
                except Exception:
                    # Skip if error
                    pass
                
                # Move to next day
                current_date += timedelta(days=1)
        
        elif cadence == Cadence.EIGHT_DAY:
            # For ET (8-day cadence)
            # Get a list of all ET tables in the database that fall within the date range
            tables_query = text(f"""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_name LIKE 'et\_%' 
                AND table_schema = 'public'
                ORDER BY table_name
            """)
            
            try:
                tables_result = await db.execute(tables_query)
                et_tables = [row['table_name'] for row in tables_result.mappings().all()]
                
                # Filter tables to only include those in the requested date range
                filtered_tables = []
                for table in et_tables:
                    # Parse the date from table name (et_YYYY_MM_DD format)
                    try:
                        parts = table.split('_')
                        if len(parts) == 4:
                            year = int(parts[1])
                            month = int(parts[2])
                            day = int(parts[3])
                            
                            table_date = datetime(year, month, day)
                            if start_date_obj <= table_date <= end_date_obj:
                                filtered_tables.append({
                                    "table": table,
                                    "date": table_date,
                                    "year": year,
                                    "month": month,
                                    "day": day
                                })
                    except (ValueError, IndexError):
                        # Skip tables that don't match our expected format
                        continue
                
                # Sort the filtered tables by date
                filtered_tables.sort(key=lambda x: x["date"])
                
                # Now query each table in the filtered list
                for table_info in filtered_tables:
                    table_name = table_info["table"]
                    year = table_info["year"]
                    month = table_info["month"]
                    day = table_info["day"]
                    date_key = f"{year}-{month:02d}-{day:02d}"
                    
                    # Define the query for this table
                    query = text(f"""
                        SELECT ST_Value(rast, ST_SetSRID(ST_GeomFromText('{point_wkt}'), 4326)) AS value 
                        FROM {table_name} 
                        WHERE ST_Intersects(rast, ST_SetSRID(ST_GeomFromText('{point_wkt}'), 4326))
                        LIMIT 1
                    """)
                    
                    try:
                        query_result = await db.execute(query)
                        row = query_result.mappings().first()
                        value = row['value'] if row and 'value' in row else None
                        
                        if value is not None:
                            point_values.append({
                                "date": date_key,
                                "year": year,
                                "month": month,
                                "day": day,
                                "value": value
                            })
                    except Exception:
                        # Skip if error
                        pass
            except Exception:
                # Handle any errors in the table lookup process
                pass
        
        # Add this point to the result if it has values
        if point_values:
            result["points"].append({
                "lat": lat,
                "lon": lon,
                "values": point_values
            })
    
    # Only return points that have data
    if not result["points"]:
        return {
            "message": f"No time series data found within the bounding box for {data_source.value}-{variable.value}",
            "bbox": result["bbox"],
            "data_source": result["data_source"],
            "variable": result["variable"],
            "cadence": result["cadence"],
            "points": []
        }
    
    return result

# Mount the static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

# Add an endpoint to serve the HTML
@app.get("/ui/", response_class=HTMLResponse)
async def get_ui():
    with open("static/timeseriesv3.html", "r") as f:
        return f.read()