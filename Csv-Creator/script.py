import pandas as pd
import requests
import os
from datetime import datetime
import time
import json
import argparse
import hashlib

def query_climate_data(lat, lon, start_date, end_date, data_source, variable=None, cache=None):
    """
    Query the climate data API for a specific coordinate and time range,
    with caching to avoid duplicate requests
    
    Args:
        lat (float): Latitude coordinate
        lon (float): Longitude coordinate
        start_date (str): Start date in YYYY-MM-DD format
        end_date (str): End date in YYYY-MM-DD format
        data_source (str): Data source (wc, spei, chirps, et)
        variable (str, optional): Climate variable (prec, tmax, tmin, spei, et)
        cache (dict, optional): Cache dictionary to store results
        
    Returns:
        dict: API response containing climate data values
    """
    # Generate cache key based on the request parameters
    cache_key = f"{lat}_{lon}_{start_date}_{end_date}_{data_source}_{variable}"
    cache_key_hash = hashlib.md5(cache_key.encode()).hexdigest()
    
    # Check if we have this result in cache
    if cache is not None and cache_key_hash in cache:
        print(f"  Cache hit for ({lat}, {lon}), {data_source}/{variable}")
        return cache[cache_key_hash]
    
    base_url = "http://localhost:8000"  # Change this to your API host/port
    
    # Construct the API endpoint URL with query parameters
    url = f"{base_url}/climate-data-timeseries/"
    
    params = {
        "lat": lat,
        "lon": lon,
        "start_date": start_date,
        "end_date": end_date,
        "data_source": data_source
    }
    
    # Add variable parameter if provided
    if variable:
        params["variable"] = variable
    
    # Make the API request
    try:
        print(url, params)
        response = requests.get(url, params=params)
        
        # Check if the request was successful
        if response.status_code == 200:
            result = response.json()
            
            # Store in cache if provided
            if cache is not None:
                cache[cache_key_hash] = result
                
            return result
        else:
            print(f"API request failed for coordinates ({lat}, {lon}), data_source={data_source}, variable={variable}")
            print(f"Status code: {response.status_code}, Error: {response.text}")
            return None
    except Exception as e:
        print(f"Exception during API request: {str(e)}")
        return None

def convert_date_format(date_str):
    """Convert date string to YYYY-MM-DD format"""
    # Try different date formats
    formats = [
        '%m/%d/%Y',  # 9/1/1996
        '%d/%m/%Y',  # 1/9/1996
        '%Y-%m-%d',  # 1996-09-01
        '%d-%m-%Y',  # 01-09-1996
        '%Y/%m/%d',  # 1996/09/01
    ]
    
    for fmt in formats:
        try:
            date_obj = datetime.strptime(date_str, fmt)
            return date_obj.strftime('%Y-%m-%d')
        except ValueError:
            continue
    
    # If none of the formats match, return the original string
    print(f"Warning: Could not parse date '{date_str}'. Using as-is.")
    return date_str

DATA_SOURCES = {
    "wc": ["prec","tmax","tmin"],
    "spei": ["spei"],
    "chirps": ["chirps"],
    "et": ["et"]
}

def save_cache(cache, cache_file_path):
    """Save the cache to a file"""
    with open(cache_file_path, 'w') as f:
        json.dump(cache, f)
    print(f"Cache saved to {cache_file_path}")

def load_cache(cache_file_path):
    """Load the cache from a file"""
    try:
        with open(cache_file_path, 'r') as f:
            cache = json.load(f)
        print(f"Loaded cache from {cache_file_path} with {len(cache)} entries")
        return cache
    except (FileNotFoundError, json.JSONDecodeError):
        print(f"No valid cache found at {cache_file_path}, creating new cache")
        return {}

def process_csv_file(input_csv_path, output_csv_path, default_start_date=None, default_end_date=None, 
                    process_all=False, cache_file_path="climate_data_cache.json"):
    """
    Process a CSV file with lat/lon coordinates, query climate data for each row,
    and add the results as new columns to the output CSV
    """
    # Load the cache
    cache = load_cache(cache_file_path)
    
    # Read the input CSV file
    try:
        df = pd.read_csv(input_csv_path)
        df = df.iloc[:100]  # Limit to first 10 rows for testing
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
    
    print("Querying API for all unique coordinate and date range combinations...")
    
    chunk_size = 10
    num_chunks = (len(df) + chunk_size - 1) // chunk_size
    
    for chunk_idx in range(num_chunks):
        chunk_start = chunk_idx * chunk_size
        chunk_end = min((chunk_idx + 1) * chunk_size, len(df))
        
        print(f"Processing chunk {chunk_idx + 1}/{num_chunks} (rows {chunk_start + 1}-{chunk_end})")
        
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
                print(f"Skipping duplicate coordinate ({lat}, {lon}) with date range {start_date} to {end_date} - Row {index+1}/{len(df)}")
                
                for temp_key, api_response in processed_coords[coord_key].items():
                    results_df.at[index, temp_key] = api_response
                    
                continue
            
            print(f"Processing coordinate ({lat}, {lon}) - Row {index+1}/{len(df)}")
            print(f"  Date range: {start_date} to {end_date}")
            
            coord_api_responses = {}
            
            if process_all:
                for data_source, variables in DATA_SOURCES.items():
                    for variable in variables:
                        print(f"  Querying {data_source}/{variable}...")
                        
                        climate_data = query_climate_data(
                            lat=lat,
                            lon=lon,
                            start_date=start_date,
                            end_date=end_date,
                            data_source=data_source,
                            variable=variable,
                            cache=cache
                        )
                                                
                        if climate_data and 'values' in climate_data:
                            var_name = climate_data.get('variable', variable)
                            
                            temp_key = f"_api_response_{data_source}_{var_name}"
                            results_df.at[index, temp_key] = json.dumps(climate_data)
                            coord_api_responses[temp_key] = json.dumps(climate_data)
                            
                            for value_data in climate_data['values']:
                                # In the first pass, modify column key generation
                                if data_source == 'wc':
                                    column_key = f"{var_name}_{value_data['year']}-{value_data['month']:02d}"
                                else:
                                    column_key = f"{var_name}_{value_data['date']}"
                                
                                all_variable_dates[column_key] = True
                            
                        time.sleep(0.1)
            else:
                # Existing ET processing code remains the same
                pass
            
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
                        # In the second pass, modify column name generation
                        if data_source == 'wc':
                            column_name = f"{var_name}_{value_data['year']}-{value_data['month']:02d}"
                        else:
                            column_name = f"{var_name}_{value_data['date']}"
                        
                        value = value_data.get('value')
                        
                        if column_name in results_df.columns:
                            results_df.at[index, column_name] = value
                except Exception as e:
                    print(f"Error processing row {index}, column {col}: {str(e)}")
    
    # Remove temporary API response columns
    temp_columns = [col for col in results_df.columns if col.startswith('_api_response_')]
    results_df = results_df.drop(temp_columns, axis=1)
    
    try:
        results_df.to_csv(output_csv_path, index=False)
        print(f"Results saved to {output_csv_path}")
        
        variable_groups = {}
        for col in var_date_keys:
            var_name = col.split('_')[0]
            if var_name not in variable_groups:
                variable_groups[var_name] = 0
            variable_groups[var_name] += 1
        
        print("Summary of added climate data:")
        for var_name, count in variable_groups.items():
            print(f"  - {var_name}: {count} time points")
        
        print(f"Cache now contains {len(cache)} entries")
        
    except Exception as e:
        print(f"Error saving output CSV: {str(e)}")

def main():
    parser = argparse.ArgumentParser(description='Process climate data for coordinates in a CSV file')
    parser.add_argument('--input', default="forest_data.csv", help='Input CSV file path')
    parser.add_argument('--output', default="forest_data_with_climate.csv", help='Output CSV file path')
    parser.add_argument('--default-start-date', default="2000-01-01", help='Default start date if data_final column is missing or empty')
    parser.add_argument('--default-end-date', default="2000-12-31", help='Default end date if date_final column is missing or empty')
    parser.add_argument('--all-variables', action='store_true', help='Process all data sources and variables')
    parser.add_argument('--cache-file', default="climate_data_cache.json", help='Cache file path')
    
    args = parser.parse_args()
    
    # Process the CSV file
    process_csv_file(
        input_csv_path=args.input,
        output_csv_path=args.output,
        default_start_date=args.default_start_date,
        default_end_date=args.default_end_date,
        process_all=args.all_variables,
        cache_file_path=args.cache_file
    )

if __name__ == "__main__":
    main()