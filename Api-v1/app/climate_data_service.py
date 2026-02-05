from datetime import datetime
from typing import Optional
from sqlalchemy import text
from app.main import (
    DataSource, Cadence, DATA_SOURCE_CADENCE, DATA_SOURCE_TABLES,
    AVAILABLE_VARIABLES, DATASOURCES_WITH_VARIABLES, STATIC_DATA_SOURCES
)

async def table_exists(db, table_name: str) -> bool:
    query = text(f"""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = '{table_name}'
        );
    """)
    result = await db.execute(query)
    return result.scalar()

async def get_climate_data_timeseries_logic(
    lat: float,
    lon: float,
    start_date: Optional[str],
    end_date: Optional[str],
    data_source: DataSource,
    variable: Optional[object],  # Accept list, str, or None
    db
) -> dict:
    result = {
        "data_source": data_source.value,
        "location": {"lat": lat, "lon": lon},
        "cadence": DATA_SOURCE_CADENCE.get(data_source, Cadence.MONTHLY).value,
        "data": []
    }

    if data_source not in STATIC_DATA_SOURCES and (start_date is None or end_date is None):
        result["error"] = "Missing required date range for time series query"
        return result

    start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None
    end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None
    point_wkt = f"ST_SetSRID(ST_MakePoint({lon}, {lat}), 4326)"
    table_name = DATA_SOURCE_TABLES.get(data_source)

    if not await table_exists(db, table_name):
        result["error"] = f"Table {table_name} does not exist"
        return result

    try:
        if data_source in STATIC_DATA_SOURCES:
            # --- Static case ---
            if variable:
                # If variable is list, batch all; else do as before
                variables = variable if isinstance(variable, list) else [variable]
                query = text(f"""
                    SELECT 
                        {", ".join([f"MAX(CASE WHEN var_name = :var_{i} THEN point_value END) AS var_{i}" for i in range(len(variables))])}
                    FROM (
                        SELECT 
                            var_name,
                            ST_Value(rast, {point_wkt}) AS point_value
                        FROM 
                            {table_name}
                        WHERE 
                            ST_Intersects(rast, {point_wkt})
                            AND var_name IN ({', '.join([f':var_{i}' for i in range(len(variables))])})
                    ) sub
                """)
                query_args = {f"var_{i}": v for i, v in enumerate(variables)}
                row = (await db.execute(query, query_args)).mappings().first()
                if row:
                    result["data"] = [
                        {"variable": variables[i], "value": row[f"var_{i}"]}
                        for i in range(len(variables)) if row[f"var_{i}"] is not None
                    ]
                return result
            else:
                # All variables for this source
                variables = AVAILABLE_VARIABLES.get(data_source, [])
                query = text(f"""
                    SELECT 
                        {", ".join([f"MAX(CASE WHEN var_name = '{v}' THEN point_value END) AS {v}" for v in variables])}
                    FROM (
                        SELECT 
                            var_name,
                            ST_Value(rast, {point_wkt}) AS point_value
                        FROM 
                            {table_name}
                        WHERE 
                            ST_Intersects(rast, {point_wkt})
                            AND var_name IN ({', '.join([f"'{v}'" for v in variables])})
                    ) sub
                """)
                row = (await db.execute(query)).mappings().first()
                result["data"] = [{"variable": var, "value": row[var]} for var in variables if row[var] is not None]
                return result

        elif data_source in DATASOURCES_WITH_VARIABLES:
            # --- Time series/batched variables ---
            variables = []
            if variable:
                variables = variable if isinstance(variable, list) else [variable]
            else:
                variables = AVAILABLE_VARIABLES.get(data_source, [])
            var_list = ', '.join([f"'{v}'" for v in variables])

            # -- Correct the latitude if it's a flipped Brazil table --
            corrected_lat = lat
            if table_name.startswith("brazil"):
                corrected_lat = -67.505 - lat  # Flip latitude over southern Brazil

            point_wkt = f"ST_SetSRID(ST_Point({lon}, {corrected_lat}), 4326)"

            query = text(f"""
                SELECT 
                    date_id,
                    {', '.join([f"MAX(CASE WHEN var_name = '{v}' THEN point_value END) AS {v}" for v in variables])}
                FROM (
                    SELECT date_id, var_name, ST_Value(rast, {point_wkt}) AS point_value
                    FROM {table_name}
                    WHERE date_id BETWEEN :start AND :end
                    AND var_name IN ({var_list})
                    AND ST_Intersects(rast, {point_wkt})
                ) sub
                GROUP BY date_id
                ORDER BY date_id
            """)

            rows = (await db.execute(query, {"start": start_date_obj, "end": end_date_obj})).mappings().all()
            for row in rows:
                item = {
                    "date": row["date_id"].strftime("%Y-%m-%d"),
                    "year": row["date_id"].year,
                    "month": row["date_id"].month,
                    "values": {k: v for k, v in row.items() if k != "date_id" and v is not None}
                }
                result["data"].append(item)

            return result

        else:
            column = AVAILABLE_VARIABLES.get(data_source, [])[0] if data_source in AVAILABLE_VARIABLES else "value"
            query = text(f"""
                SELECT date_id, ST_Value(rast, {point_wkt}) AS {column}
                FROM {table_name}
                WHERE date_id BETWEEN :start AND :end
                AND ST_Intersects(rast, {point_wkt})
                ORDER BY date_id
            """)
            rows = (await db.execute(query, {"start": start_date_obj, "end": end_date_obj})).mappings().all()
            
            varname = variable[0] if isinstance(variable, list) and len(variable) == 1 else variable
            for row in rows:
                val = row[column]
                if val is not None:
                    result["data"].append({
                        "date": row["date_id"].strftime("%Y-%m-%d"),
                        "year": row["date_id"].year,
                        "month": row["date_id"].month,
                        "values": {varname: val}
                    })
            return result


    except Exception as e:
        result["error"] = str(e)
        return result
