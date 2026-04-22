"""
Optimized climate data service with parallel query patterns.

Key optimizations:
1. Array aggregation to reduce result set size
2. CTE (Common Table Expressions) that PostgreSQL can parallelize
3. Force parallel execution for large date ranges
4. Batch multiple variables efficiently
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import text

async def get_climate_data_optimized(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
    table_name: str,
    variables: List[str],
    db
) -> dict:
    """
    Optimized query with array aggregation and parallel execution hints.
    
    Returns single row with arrays instead of 365+ rows.
    """
    
    point_wkt = f"ST_SetSRID(ST_MakePoint({lon}, {lat}), 4326)"
    start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
    end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
    
    # Build variable-specific column selections
    var_columns = ", ".join([
        f"array_agg(CASE WHEN var_name = '{v}' THEN point_value END ORDER BY date_id) FILTER (WHERE var_name = '{v}') AS {v}_values"
        for v in variables
    ])
    
    # Optimized query with CTE and aggregation
    query = text(f"""
        WITH extracted_values AS (
            SELECT 
                date_id,
                var_name,
                ST_Value(rast, {point_wkt}) AS point_value
            FROM {table_name}
            WHERE date_id BETWEEN :start AND :end
              AND var_name = ANY(:vars)
              AND ST_Intersects(rast, {point_wkt})
        )
        SELECT 
            array_agg(DISTINCT date_id ORDER BY date_id) AS dates,
            {var_columns}
        FROM extracted_values;
    """)
    
    result = (await db.execute(query, {
        "start": start_date_obj,
        "end": end_date_obj,
        "vars": variables
    })).mappings().first()
    
    # Transform to API response format
    if not result or not result['dates']:
        return {"data": []}
    
    dates = result['dates']
    data = []
    
    for i, date in enumerate(dates):
        item = {
            "date": date.strftime("%Y-%m-%d"),
            "year": date.year,
            "month": date.month,
            "values": {}
        }
        
        for var in variables:
            var_array = result[f"{var}_values"]
            if var_array and len(var_array) > i:
                item["values"][var] = var_array[i]
        
        data.append(item)
    
    return {"data": data}


async def get_chirps_timeseries_optimized(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
    db
) -> dict:
    """
    Optimized CHIRPS query with JSON aggregation.
    
    Returns single JSON object: {"2025-01-01": 12.3, "2025-01-02": 8.5, ...}
    """
    
    point_wkt = f"ST_SetSRID(ST_MakePoint({lon}, {lat}), 4326)"
    start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
    end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
    
    query = text(f"""
        SELECT json_object_agg(
            date_id::text,
            ST_Value(rast, {point_wkt})
        ) AS data
        FROM chirps_data
        WHERE date_id BETWEEN :start AND :end
          AND ST_Intersects(rast, {point_wkt});
    """)
    
    result = (await db.execute(query, {
        "start": start_date_obj,
        "end": end_date_obj
    })).mappings().first()
    
    return {"data": result['data'] if result else {}}


async def get_multi_location_batch(
    locations: List[dict],  # [{"lat": 8.5, "lon": -80.5}, ...]
    date: str,
    table_name: str,
    variables: List[str],
    db
) -> List[dict]:
    """
    Batch query for multiple locations on same date.
    
    Uses array of points for single query instead of N queries.
    PostgreSQL will parallelize across points.
    """
    
    date_obj = datetime.strptime(date, "%Y-%m-%d").date()
    
    # Build UNION of points
    points_cte = ", ".join([
        f"(ST_SetSRID(ST_MakePoint({loc['lon']}, {loc['lat']}), 4326), {i})"
        for i, loc in enumerate(locations)
    ])
    
    var_list = "', '".join(variables)
    
    query = text(f"""
        WITH points AS (
            SELECT * FROM (VALUES {points_cte}) AS t(geom, location_id)
        ),
        extracted AS (
            SELECT 
                p.location_id,
                d.var_name,
                ST_Value(d.rast, p.geom) AS value
            FROM points p
            CROSS JOIN LATERAL (
                SELECT var_name, rast
                FROM {table_name}
                WHERE date_id = :date
                  AND var_name IN ('{var_list}')
                  AND ST_Intersects(rast, p.geom)
            ) d
        )
        SELECT 
            location_id,
            json_object_agg(var_name, value) AS values
        FROM extracted
        GROUP BY location_id
        ORDER BY location_id;
    """)
    
    rows = (await db.execute(query, {"date": date_obj})).mappings().all()
    
    # Merge with location metadata
    results = []
    for row in rows:
        loc_idx = row['location_id']
        results.append({
            **locations[loc_idx],
            "values": row['values']
        })
    
    return results


async def force_parallel_execution(db):
    """
    Ensure parallel execution is enabled for this session.
    Call once per API session/connection.
    """
    await db.execute(text("SET max_parallel_workers_per_gather = 4;"))
    await db.execute(text("SET parallel_tuple_cost = 0.01;"))
    await db.execute(text("SET force_parallel_mode = ON;"))  # Force parallel for testing
