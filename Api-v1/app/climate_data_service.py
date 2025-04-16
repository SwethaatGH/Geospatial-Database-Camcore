# climate_data_service.py
from datetime import datetime, timedelta
from sqlalchemy import text
from app.main import DataSource, Variable, Cadence, get_table_name, get_cadence_for_data_source
from typing import Optional

# Shared helper to check if a table exists
async def table_exists(db, table_name: str) -> bool:
    check_query = text("""
        SELECT EXISTS (
            SELECT 1 
            FROM information_schema.tables 
            WHERE table_name = :table_name
        )
    """)
    result = await db.execute(check_query, {"table_name": table_name})
    return result.scalar()

# Core business logic for querying climate data
async def get_climate_data_timeseries_logic(
    lat: float,
    lon: float,
    start_date: Optional[str],
    end_date: Optional[str],
    data_source: DataSource,
    variable: Optional[Variable],
    db
) -> dict:
    """
    Returns climate data either as static (one value) or time series based on cadence.
    The function parses parameters, builds SQL queries and returns a dict of results.
    """
    # Define the point string used by PostGIS:
    point = f"POINT({lon} {lat})"
    cadence = get_cadence_for_data_source(data_source)
    results = {
        "lon": lon,
        "lat": lat,
        "data_source": data_source.value,
        "variable": variable.value if variable else "",
        "cadence": cadence.value,
        "values": []
    }
    
    # --- STATIC DATA (Elevation, SoilGrids) ---
    if data_source in [DataSource.ELEVATION, DataSource.SOILGRIDS]:
        if variable is None:
            # Set a default variable if none provided
            if data_source == DataSource.ELEVATION:
                variable = Variable.ELEVATION
            elif data_source == DataSource.SOILGRIDS:
                variable = Variable.BDOD  # Default for SoilGrids
        try:
            table_name = get_table_name(data_source, variable)
        except Exception as e:
            results["error"] = f"Error generating table name: {str(e)}"
            return results
        
        query = text(f"""
            SELECT ST_Value(rast, ST_SetSRID(ST_GeomFromText(:point), 4326)) AS value
            FROM {table_name}
            WHERE ST_Intersects(rast, ST_SetSRID(ST_GeomFromText(:point), 4326))
            LIMIT 1
        """)
        try:
            res = await db.execute(query, {"point": point})
            row = res.mappings().first()
            if row and row.get("value") is not None:
                results["values"].append({"value": row["value"]})
            else:
                results["message"] = f"No data found for {data_source.value}-{variable.value}"
        except Exception as e:
            results["error"] = f"Database error: {str(e)}"
        return results

    # --- TIMESERIES DATA ---
    # start_date and end_date are required for time series data.
    try:
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
    except Exception as e:
        results["error"] = f"Invalid date format: {str(e)}"
        return results

    if cadence == Cadence.MONTHLY:
        current_date = datetime(start_date_obj.year, start_date_obj.month, 1)
        end_month = datetime(end_date_obj.year, end_date_obj.month, 1)
        while current_date <= end_month:
            year = current_date.year
            month = current_date.month
            date_key = f"{year}-{month:02d}"
            try:
                table_name = get_table_name(data_source, variable, year, month)
            except Exception as e:
                results["values"].append({
                    "date": date_key,
                    "year": year,
                    "month": month,
                    "value": None,
                    "error": str(e)
                })
                if month == 12:
                    current_date = datetime(year + 1, 1, 1)
                else:
                    current_date = datetime(year, month + 1, 1)
                continue

            if await table_exists(db, table_name):
                query = text(f"""
                    SELECT ST_Value(rast, ST_SetSRID(ST_GeomFromText(:point), 4326)) AS value
                    FROM {table_name}
                    WHERE ST_Intersects(rast, ST_SetSRID(ST_GeomFromText(:point), 4326))
                    LIMIT 1
                """)
                try:
                    res = await db.execute(query, {"point": point})
                    row = res.mappings().first()
                    value = row["value"] if row and "value" in row else None
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
                results["values"].append({
                    "date": date_key,
                    "year": year,
                    "month": month,
                    "value": None,
                    "error": "No data available for this date"
                })
            if current_date.month == 12:
                current_date = datetime(current_date.year + 1, 1, 1)
            else:
                current_date = datetime(current_date.year, current_date.month + 1, 1)

    elif cadence == Cadence.DAILY:
        current_date = start_date_obj
        while current_date <= end_date_obj:
            year = current_date.year
            month = current_date.month
            day = current_date.day
            date_key = f"{year}-{month:02d}-{day:02d}"
            try:
                table_name = get_table_name(data_source, variable, year, month, day)
            except Exception as e:
                results["values"].append({
                    "date": date_key,
                    "year": year,
                    "month": month,
                    "day": day,
                    "value": None,
                    "error": str(e)
                })
                current_date += timedelta(days=1)
                continue

            if await table_exists(db, table_name):
                query = text(f"""
                    SELECT ST_Value(rast, ST_SetSRID(ST_GeomFromText(:point), 4326)) AS value
                    FROM {table_name}
                    WHERE ST_Intersects(rast, ST_SetSRID(ST_GeomFromText(:point), 4326))
                    LIMIT 1
                """)
                try:
                    res = await db.execute(query, {"point": point})
                    row = res.mappings().first()
                    value = row["value"] if row and "value" in row else None
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
                results["values"].append({
                    "date": date_key,
                    "year": year,
                    "month": month,
                    "day": day,
                    "value": None,
                    "error": "No data available for this date"
                })
            current_date += timedelta(days=1)
    elif cadence == Cadence.EIGHT_DAY:
        # You can add similar logic to loop through 8-day intervals.
        results["error"] = "EIGHT_DAY cadence not implemented in refactored version."
    
    return results
