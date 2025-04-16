# script.py
import pandas as pd
from datetime import datetime
import time, json, argparse, hashlib, os
import asyncio
import sys

# # Add the site-packages from the virtual environment to the Python path
venv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Api-v1", "venv"))
if sys.platform == 'win32':
    site_packages = os.path.join(venv_path, "Lib", "site-packages")
else:
    # Adjust for Python version if needed
    site_packages = os.path.join(venv_path, "lib", "python3.9", "site-packages")

if os.path.exists(site_packages):
    sys.path.insert(0, site_packages)
    print(f"Added site-packages to path: {site_packages}")
else:
    print(f"Site-packages directory not found at: {site_packages}")

# Also add the Api-v1 directory to the path
api_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Api-v1"))
sys.path.insert(0, api_path)
print(f"Added Api-v1 to path: {api_path}")

# Add detailed debugging
try:
    import sqlalchemy
    print(f"SQLAlchemy found at: {sqlalchemy.__file__}, version: {sqlalchemy.__version__}")
except ImportError as e:
    print(f"SQLAlchemy import failed: {e}")
    print("Python path:")
    for p in sys.path:
        print(f"  - {p}")
        
# Import shared business logic and dependencies
from app.database import get_db  # Assumes you have your asynchronous DB setup here.
from app.main import DataSource, Variable  # Import your enums
from app.climate_data_service import get_climate_data_timeseries_logic

def convert_date_format(date_str):
    formats = ['%m/%d/%Y', '%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%Y/%m/%d']
    for fmt in formats:
        try:
            date_obj = datetime.strptime(date_str, fmt)
            return date_obj.strftime('%Y-%m-%d')
        except ValueError:
            continue
    print(f"Warning: Could not parse date '{date_str}'. Using as-is.")
    return date_str

DATA_SOURCES = {
    "wc": ["prec","tmax","tmin"],
    "spei": ["spei"],
    "chirps": ["chirps"],
    "et": ["et"]
}

def save_cache(cache, cache_file_path):
    with open(cache_file_path, 'w') as f:
        json.dump(cache, f)
    print(f"Cache saved to {cache_file_path}")

def load_cache(cache_file_path):
    try:
        with open(cache_file_path, 'r') as f:
            cache = json.load(f)
        print(f"Loaded cache from {cache_file_path} with {len(cache)} entries")
        return cache
    except (FileNotFoundError, json.JSONDecodeError):
        print(f"No valid cache found at {cache_file_path}, creating new cache")
        return {}

# A synchronous wrapper around the async climate query
# A synchronous wrapper around the async climate query
async def query_climate_data(lat, lon, start_date, end_date, data_source, variable=None, cache=None):
    cache_key = f"{lat}_{lon}_{start_date}_{end_date}_{data_source}_{variable}"
    cache_key_hash = hashlib.md5(cache_key.encode()).hexdigest()
    if cache is not None and cache_key_hash in cache:
        print(f"  Cache hit for ({lat}, {lon}), {data_source}/{variable}")
        return cache[cache_key_hash]
    
    db_gen = get_db()
    db = await db_gen.__anext__()
    try:
        result = await get_climate_data_timeseries_logic(
            lat, lon, start_date, end_date,
            DataSource(data_source),
            Variable(variable) if variable else None,
            db
        )
    finally:
        await db_gen.aclose()
    if cache is not None:
        cache[cache_key_hash] = result
    return result

async def process_csv_file(input_csv_path, output_csv_path, default_start_date=None, default_end_date=None, 
                     process_all=False, cache_file_path="climate_data_cache.json"):
    cache = load_cache(cache_file_path)
    try:
        df = pd.read_csv(input_csv_path)
        df = df.iloc[:10]  # Use first 10 rows for testing
        print(f"Loaded CSV with {len(df)} rows")
    except Exception as e:
        print(f"Error reading input CSV: {str(e)}")
        return
    required_columns = ['latitude', 'longitude']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        print(f"Error: Input CSV is missing required columns: {missing_columns}")
        return
    date_columns = {'start': 'data_final', 'end': 'date_final'}
    missing_date_columns = []
    for purpose, column in date_columns.items():
        if column not in df.columns:
            missing_date_columns.append(column)
            print(f"Warning: '{column}' column not found. Will use default {purpose} date.")
    if missing_date_columns and (default_start_date is None or default_end_date is None):
        print("Error: Date columns are missing and no default dates provided.")
        return
    
    results_df = df.copy()
    all_variable_dates = {}
    processed_coords = {}
    print("Querying climate data for all unique coordinate and date range combinations...")
    chunk_size = 10
    num_chunks = (len(df) + chunk_size - 1) // chunk_size
    for chunk_idx in range(num_chunks):
        chunk_start = chunk_idx * chunk_size
        chunk_end = min((chunk_idx + 1) * chunk_size, len(df))
        print(f"Processing chunk {chunk_idx+1}/{num_chunks} (rows {chunk_start+1}-{chunk_end})")
        for index in range(chunk_start, chunk_end):
            row = df.iloc[index]
            lat = row['latitude']
            lon = row['longitude']
            if 'data_final' in row and not pd.isna(row['data_final']):
                start_date = convert_date_format(str(row['data_final']))
            else:
                start_date = default_start_date
            if 'date_final' in row and not pd.isna(row['date_final']):
                end_date = convert_date_format(str(row['date_final']))
            else:
                end_date = default_end_date
            coord_key = f"{lat}_{lon}_{start_date}_{end_date}"
            if coord_key in processed_coords:
                print(f"Skipping duplicate coordinate ({lat}, {lon}) with date range {start_date} to {end_date}")
                for temp_key, api_response in processed_coords[coord_key].items():
                    results_df.at[index, temp_key] = api_response
                continue
            print(f"Processing coordinate ({lat}, {lon}) - Row {index+1}/{len(df)}")
            print(f"  Date range: {start_date} to {end_date}")
            coord_api_responses = {}
            for data_source, variables in DATA_SOURCES.items():
                for var in variables:
                    print(f"  Querying {data_source}/{var}...")
                    climate_data = await query_climate_data(
                        lat=lat,
                        lon=lon,
                        start_date=start_date,
                        end_date=end_date,
                        data_source=data_source,
                        variable=var,
                        cache=cache
                    )
                    if climate_data and 'values' in climate_data:
                        var_name = climate_data.get('variable', var)
                        temp_key = f"_api_response_{data_source}_{var_name}"
                        results_df.at[index, temp_key] = json.dumps(climate_data)
                        coord_api_responses[temp_key] = json.dumps(climate_data)
                        for value_data in climate_data['values']:
                            if data_source == 'wc':
                                column_key = f"{data_source}_{var_name}_{value_data['year']}-{value_data['month']:02d}"
                            else:
                                column_key = f"{data_source}_{var_name}_{value_data.get('date', '')}"
                            all_variable_dates[column_key] = True
                    time.sleep(0.1)
            processed_coords[coord_key] = coord_api_responses
        save_cache(cache, cache_file_path)
    
    var_date_keys = sorted(all_variable_dates.keys())
    print(f"Creating {len(var_date_keys)} columns for climate data...")
    for var_date_key in var_date_keys:
        results_df[var_date_key] = None
    print("Processing climate data values...")
    for index, row in results_df.iterrows():
        for col in row.index:
            if col.startswith('_api_response_') and not pd.isna(row[col]):
                try:
                    climate_data = json.loads(row[col])
                    var_name = climate_data.get('variable', 'value')
                    data_source = climate_data.get('data_source', '')
                    for value_data in climate_data['values']:
                        if data_source == 'wc':
                            column_name = f"{data_source}_{var_name}_{value_data['year']}-{value_data['month']:02d}"
                        else:
                            column_name = f"{data_source}_{var_name}_{value_data.get('date', '')}"
                        value = value_data.get('value')
                        if column_name in results_df.columns:
                            results_df.at[index, column_name] = value
                except Exception as e:
                    print(f"Error processing row {index}, column {col}: {str(e)}")
    temp_columns = [col for col in results_df.columns if col.startswith('_api_response_')]
    results_df = results_df.drop(temp_columns, axis=1)
    try:
        results_df.to_csv(output_csv_path, index=False)
        print(f"Results saved to {output_csv_path}")
        variable_groups = {}
        for col in var_date_keys:
            var_name = col.split('_')[0]
            variable_groups[var_name] = variable_groups.get(var_name, 0) + 1
        print("Summary of added climate data:")
        for var_name, count in variable_groups.items():
            print(f"  - {var_name}: {count} time points")
        print(f"Cache now contains {len(cache)} entries")
    except Exception as e:
        print(f"Error saving output CSV: {str(e)}")

async def main():
    parser = argparse.ArgumentParser(description='Process climate data for coordinates in a CSV file')
    parser.add_argument('--input', default="forest_data_v1.csv", help='Input CSV file path')
    parser.add_argument('--output', default="forest_data_with_climate.csv", help='Output CSV file path')
    parser.add_argument('--default-start-date', default="2000-01-01", help='Default start date if missing')
    parser.add_argument('--default-end-date', default="2000-12-31", help='Default end date if missing')
    parser.add_argument('--all-variables', action='store_true', help='Process all data sources and variables')
    parser.add_argument('--cache-file', default="climate_data_cache.json", help='Cache file path')
    args = parser.parse_args()
    
    await process_csv_file(
        input_csv_path=args.input,
        output_csv_path=args.output,
        default_start_date=args.default_start_date,
        default_end_date=args.default_end_date,
        process_all=args.all_variables,
        cache_file_path=args.cache_file
    )

if __name__ == "__main__":
    asyncio.run(main())

