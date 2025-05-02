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
    variable: Optional[str],
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
            if data_source == DataSource.SOILGRIDS:
                variables = AVAILABLE_VARIABLES.get(data_source, [])
                query = text(f"""
                    SELECT 
                        {", ".join([f"MAX(CASE WHEN var_name = '{var}' THEN point_value END) AS {var}" for var in variables])}
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
            else:
                query = text(f"""
                    SELECT ST_Value(rast, {point_wkt}) AS value
                    FROM {table_name}
                    WHERE ST_Intersects(rast, {point_wkt})
                    LIMIT 1
                """)
                row = (await db.execute(query)).mappings().first()
                if row and row["value"] is not None:
                    result["data"] = [{"value": row["value"]}]
            return result

        elif data_source in DATASOURCES_WITH_VARIABLES:
            variables = [variable] if variable else AVAILABLE_VARIABLES.get(data_source, [])
            var_list = ', '.join([f"'{v}'" for v in variables])
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
            for row in rows:
                val = row[column]
                if val is not None:
                    result["data"].append({
                    "date": row["date_id"].strftime("%Y-%m-%d"),
                    "year": row["date_id"].year,
                    "month": row["date_id"].month,
                    "values": {variable: val}
                })
            return result

    except Exception as e:
        result["error"] = str(e)
        return result
