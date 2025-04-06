import pandas as pd
import numpy as np
import requests
import os
from datetime import datetime
import time
import json
import argparse
import hashlib
from typing import List, Dict, Any, Optional
def get_hemisphere(latitude):
    """
    Determine hemisphere based on latitude
    """
    return "southern" if latitude < 0 else "northern"
def query_climate_data(lat: float, lon: float, start_date: str, end_date: str, 
                       data_source: str, variable: Optional[str] = None, 
                       cache: Optional[dict] = None) -> Optional[dict]:
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

def determine_season(month: int, hemisphere: str = 'north') -> str:
    """
    Determine season based on month and hemisphere
    
    North Hemisphere:
    - Winter: Dec, Jan, Feb
    - Spring: Mar, Apr, May
    - Summer: Jun, Jul, Aug
    - Fall: Sep, Oct, Nov
    
    South Hemisphere:
    - Winter: Jun, Jul, Aug
    - Spring: Sep, Oct, Nov
    - Summer: Dec, Jan, Feb
    - Fall: Mar, Apr, May
    """
    if hemisphere == 'north':
        season_map = {
            (12, 1, 2): 'winter',
            (3, 4, 5): 'spring', 
            (6, 7, 8): 'summer', 
            (9, 10, 11): 'fall'
        }
    else:  # south
        season_map = {
            (6, 7, 8): 'winter', 
            (9, 10, 11): 'spring',
            (12, 1, 2): 'summer', 
            (3, 4, 5): 'fall'
        }
    
    for months, season in season_map.items():
        if month in months:
            return season

import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional, Callable

def is_valid_numeric_value(value: Any) -> bool:
    """
    Check if a value is a valid numeric value for processing
    """
    return (
        value is not None and 
        not pd.isna(value) and 
        isinstance(value, (int, float, np.number))
    )

def count_seasonal_conditions(climate_data: List[Dict], 
                               condition_func: Callable[[float], bool], 
                               hemisphere: str = 'north') -> Dict[str, int]:
    """
    Count occurrences of a condition by season with robust error handling
    """
    # Handle cases where climate_data might be None or empty
    if not climate_data:
        return {'winter': 0, 'spring': 0, 'summer': 0, 'fall': 0}
    
    seasonal_counts = {
        'winter': 0, 'spring': 0, 'summer': 0, 'fall': 0
    }
    
    for entry in climate_data:
        # Ensure entry is a dictionary with required keys
        if not isinstance(entry, dict):
            continue
        
        # Extract value safely
        value = entry.get('value')
        
        # Skip invalid or None values
        if not is_valid_numeric_value(value):
            continue
        
        try:
            # Convert to float to ensure numeric comparison
            numeric_value = float(value)
            
            # Determine season
            month = entry.get('month')
            if month is None:
                continue
            
            season = determine_season(month, hemisphere)
            
            # Apply condition
            if condition_func(numeric_value):
                seasonal_counts[season] += 1
        
        except (TypeError, ValueError):
            # Skip entries that can't be processed
            continue
    
    return seasonal_counts

def calculate_consecutive_dry_days(climate_data: List[Dict], 
                                    hemisphere: str = 'north') -> Dict[str, int]:
    """
    Calculate max consecutive days with zero precipitation by season
    with robust error handling
    """
    # Handle cases where climate_data might be None or empty
    if not climate_data:
        return {'winter': 0, 'spring': 0, 'summer': 0, 'fall': 0}
    
    seasonal_dry_streaks = {
        'winter': 0, 'spring': 0, 'summer': 0, 'fall': 0
    }
    
    seasonal_data = {
        'winter': [], 'spring': [], 'summer': [], 'fall': []
    }
    
    for entry in climate_data:
        # Ensure entry is a dictionary with required keys
        if not isinstance(entry, dict):
            continue
        
        # Extract value safely
        value = entry.get('value')
        
        # Skip invalid or None values
        if not is_valid_numeric_value(value):
            continue
        
        try:
            # Convert to float to ensure numeric processing
            numeric_value = float(value)
            
            # Determine season
            month = entry.get('month')
            if month is None:
                continue
            
            season = determine_season(month, hemisphere)
            seasonal_data[season].append(numeric_value)
        
        except (TypeError, ValueError):
            # Skip entries that can't be processed
            continue
    
    for season, values in seasonal_data.items():
        max_streak = 0
        current_streak = 0
        
        for value in values:
            if value == 0:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0
        
        seasonal_dry_streaks[season] = max_streak
    
    return seasonal_dry_streaks

def aggregate_seasonal_data(climate_data: List[Dict], 
                             hemisphere: str = 'north', 
                             aggregations: List[str] = ['mean']) -> Dict[str, float]:
    """
    Aggregate climate data by season with multiple statistical methods
    Handles potential null or empty data scenarios with comprehensive error handling
    """
    # Handle cases where climate_data might be None or empty
    if not climate_data:
        return {}
    
    # Prepare seasonal data storage
    seasonal_data = {
        'winter': [], 'spring': [], 'summer': [], 'fall': []
    }
    
    for entry in climate_data:
        # Ensure entry is a dictionary with required keys
        if not isinstance(entry, dict):
            continue
        
        # Extract value safely
        value = entry.get('value')
        
        # Skip invalid or None values
        if not is_valid_numeric_value(value):
            continue
        
        try:
            # Convert to float to ensure numeric processing
            numeric_value = float(value)
            
            # Determine season
            month = entry.get('month')
            if month is None:
                continue
            
            season = determine_season(month, hemisphere)
            seasonal_data[season].append(numeric_value)
        
        except (TypeError, ValueError):
            # Skip entries that can't be processed
            continue
    
    results = {}
    for season, values in seasonal_data.items():
        if not values:  # Skip seasons with no valid data
            continue
        
        for agg in aggregations:
            key = f"{season}_{agg}"
            try:
                if agg == 'mean':
                    results[key] = float(np.mean(values))
                elif agg == 'max':
                    results[key] = float(np.max(values))
                elif agg == 'min':
                    results[key] = float(np.min(values))
                elif agg == 'std':
                    results[key] = float(np.std(values))
                elif agg == 'coefficient_variation':
                    results[key] = (float(np.std(values)) / float(np.mean(values)) * 100) if np.mean(values) != 0 else 0
            except Exception as e:
                print(f"Error processing {agg} for {season}: {e}")
    
    return results

def process_worldclim_climate_metrics(climate_data: Dict, 
                                      hemisphere: str = 'north') -> Dict[str, Any]:
    """
    Process WorldClim climate metrics with robust error handling
    """
    # Validate input
    if not isinstance(climate_data, dict):
        print("Invalid climate data input")
        return {}
    
    # Check if required keys exist
    if 'variable' not in climate_data or 'values' not in climate_data:
        print("Missing required keys in climate data")
        return {}
    
    seasonal_metrics = {}
    
    # Specific processing for each variable type
    variable_aggregations = {
        'tmax': ['max', 'mean', 'std', 'coefficient_variation'],
        'tmin': ['min', 'mean', 'max', 'std', 'coefficient_variation'],
        'prec': ['max', 'median', 
                 'count_less_than_10', 
                 'count_zero', 
                 'max_consecutive_zero']
    }
    
    # Get current variable and data
    var = climate_data.get('variable', '')
    data = climate_data.get('values', [])
    
    # Check if variable is supported
    if var not in variable_aggregations:
        print(f"Unsupported variable: {var}")
        return {}
    
    agg_methods = variable_aggregations[var]
    
    # Seasonal aggregations
    try:
        seasonal_stats = aggregate_seasonal_data(
            data, 
            hemisphere, 
            [m for m in agg_methods if m in ['max', 'mean', 'min', 'std', 'coefficient_variation']]
        )
        seasonal_metrics.update(seasonal_stats)
    except Exception as e:
        print(f"Error in seasonal aggregation: {e}")
    
    # Days above conditions for temperature
    if var == 'tmax':
        try:
            temp_above_35 = count_seasonal_conditions(
                data, 
                lambda x: x > 35, 
                hemisphere
            )
            seasonal_metrics.update({
                f'days_above_35_{season}': count 
                for season, count in temp_above_35.items()
            })
        except Exception as e:
            print(f"Error processing temperature conditions: {e}")
    
    # Precipitation specific metrics
    if var == 'prec':
        try:
            prec_less_10 = count_seasonal_conditions(
                data, 
                lambda x: x < 10, 
                hemisphere
            )
            prec_zero = count_seasonal_conditions(
                data, 
                lambda x: x == 0, 
                hemisphere
            )
            
            seasonal_metrics.update({
                f'prec_less_10_{season}': count 
                for season, count in prec_less_10.items()
            })
            seasonal_metrics.update({
                f'prec_zero_{season}': count 
                for season, count in prec_zero.items()
            })
            
            # Consecutive zero precipitation days
            max_dry_days = calculate_consecutive_dry_days(data, hemisphere)
            seasonal_metrics.update({
                f'max_consecutive_dry_{season}': days 
                for season, days in max_dry_days.items()
            })
        except Exception as e:
            print(f"Error processing precipitation metrics: {e}")
    
    return seasonal_metrics

def process_chirps_precipitation(climate_data: Dict, 
                                 hemisphere: str = 'north') -> Dict[str, Any]:
    """
    Process CHIRPS precipitation data with seasonal calculations
    """
    # Ensure it's precipitation data
    if 'chirps' not in climate_data.get('data_source', '').lower():
        return {}
    
    data = climate_data['values']
    
    # Precipitation seasonal metrics
    seasonal_metrics = aggregate_seasonal_data(
        data, hemisphere, 
        ['max', 'median', 'mean']
    )
    
    # Precipitation occurrence metrics
    prec_less_10 = count_seasonal_conditions(
        data, 
        lambda x: x < 10, 
        hemisphere
    )
    prec_zero = count_seasonal_conditions(
        data, 
        lambda x: x == 0, 
        hemisphere
    )
    
    seasonal_metrics.update({
        f'prec_less_10_{season}': count 
        for season, count in prec_less_10.items()
    })
    seasonal_metrics.update({
        f'prec_zero_{season}': count 
        for season, count in prec_zero.items()
    })
    
    # Consecutive zero precipitation days
    max_dry_days = calculate_consecutive_dry_days(data, hemisphere)
    seasonal_metrics.update({
        f'max_consecutive_dry_{season}': days 
        for season, days in max_dry_days.items()
    })
    
    return seasonal_metrics

def convert_date_format(date_str):
    """Convert date string to YYYY-MM-DD format"""
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
    
    print(f"Warning: Could not parse date '{date_str}'. Using as-is.")
    return date_str

DATA_SOURCES = {
    "wc": ["prec","tmax","tmin"],
    "spei": ["spei"],
    "chirps": ["chirps"],
    "et": ["et"]
}

def process_csv_file(input_csv_path, output_csv_path, 
                     default_start_date=None, default_end_date=None, 
                     process_all=False, cache_file_path="climate_data_cache.json"):
    """
    Process a CSV file with lat/lon coordinates, query climate data for each row,
    and add the results as new columns to the output CSV
    
    Enhanced to copy over last successful data for duplicate coordinates
    """
    # Load the cache
    cache = load_cache(cache_file_path)
    
    # Read the input CSV file
    try:
        df = pd.read_csv(input_csv_path)
        df = df.iloc[:50]  # Limit to first 100 rows for testing
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
    last_successful_data = {}  # Store last successful data for each unique coordinate
    
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
            print(f"Processing coordinate ({lat}, {lon}) - Row {index+1}/{len(df)}")
            print(f"  Date range: {start_date} to {end_date}")
            
            # Check if we have previous successful data for this coordinate
            if coord_key in last_successful_data:
                print(f"  Using cached data for ({lat}, {lon})")
                for col, value in last_successful_data[coord_key].items():
                    results_df.at[index, col] = value
                continue
            
            # Initialize dictionary to store results for this coordinate
            coord_data = {}
            
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
                            hemisphere = get_hemisphere(lat)
                            
                            # Process WorldClim data
                            if data_source == 'wc':
                                seasonal_metrics = process_worldclim_climate_metrics(
                                    climate_data, 
                                    hemisphere
                                )
                                
                                # Add seasonal metrics to results
                                for metric, value in seasonal_metrics.items():
                                    col_name = f"wc_{variable}_{metric}"
                                    results_df.at[index, col_name] = value
                                    coord_data[col_name] = value
                            
                            # Process CHIRPS precipitation data
                            elif data_source == 'chirps':
                                seasonal_metrics = process_chirps_precipitation(
                                    climate_data, 
                                    hemisphere
                                )
                                
                                # Add seasonal metrics to results
                                for metric, value in seasonal_metrics.items():
                                    col_name = f"chirps_prec_{metric}"
                                    results_df.at[index, col_name] = value
                                    coord_data[col_name] = value
                        
                        time.sleep(0.1)
                
                # Store successful data for this coordinate
                if coord_data:
                    last_successful_data[coord_key] = coord_data
        
        save_cache(cache, cache_file_path)
    
    try:
        results_df.to_csv(output_csv_path, index=False)
        print(f"Results saved to {output_csv_path}")
        
        print(f"Cache now contains {len(cache)} entries")
        
    except Exception as e:
        print(f"Error saving output CSV: {str(e)}")
        
        
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

def main():
    parser = argparse.ArgumentParser(description='Process climate data for coordinates in a CSV file')
    parser.add_argument('--input', default="forest_data.csv", help='Input CSV file path')
    parser.add_argument('--output', default="forest_data_with_climate.csv", help='Output CSV file path')
    parser.add_argument('--default-start-date', default="2000-01-01", help='Default start date if data_final column is missing or empty')
    parser.add_argument('--default-end-date', default="2000-12-31", help='Default end date if date_final column is missing or empty')
    parser.add_argument('--all-variables', action='store_true', help='Process all data sources and variables')
    parser.add_argument('--cache-file', default="climate_data_cache.json", help='Cache file path')
    
    args = parser.parse_args()
    
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