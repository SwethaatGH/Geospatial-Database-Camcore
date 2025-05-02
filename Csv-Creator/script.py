# script.py (updated to match new service and main.py)
import pandas as pd
from datetime import datetime
import time, json, argparse, hashlib, os
import asyncio
import sys

# Add virtual environment site-packages to path
venv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Api-v1", "venv"))
if sys.platform == 'win32':
    site_packages = os.path.join(venv_path, "Lib", "site-packages")
else:
    site_packages = os.path.join(venv_path, "lib", "python3.9", "site-packages")
if os.path.exists(site_packages):
    sys.path.insert(0, site_packages)
    print(f"Added site-packages to path: {site_packages}")

# Add API source path
import sys
import os

# Resolve path to Api-v1 and add it to sys.path
api_v1_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Api-v1"))
if api_v1_path not in sys.path:
    sys.path.insert(0, api_v1_path)

# Imports
from app.database import get_db
from app.main import DataSource  # Use only DataSource enum
from app.climate_data_service import get_climate_data_timeseries_logic


def convert_date_format(date_str):
    formats = ['%m/%d/%Y', '%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%Y/%m/%d']
    for fmt in formats:
        try:
            date_obj = datetime.strptime(date_str, fmt)
            return date_obj.strftime('%Y-%m-%d')
        except ValueError:
            continue
    return date_str

DATA_SOURCES = {
    "wc": ["prec", "tmax", "tmin"],
    "spei": ["spei"],
    "chirps": ["chirps"],
    "et": ["et"],
    "elev": ["aspect", "elev", "flowdir", "hillshade", "roughness", "tpi", "tri", "slope"],
    "sg": ["bdod", "cec", "cfvo", "clay", "nitrogen", "ocd", "ocs", "phh2o", "sand", "silt", "soc", "wv0010", "wv0030", "wv1500"],
    "tc": ["aet", "def", "pdsi", "pet", "ppt", "q", "soil", "srad", "tmin", "vap", "vpd", "ws"],
    "np": ["airmass", "allsky_kt", "allsky_nkt", "allsky_sfc_lw_dwn", "allsky_sfc_lw_up", "allsky_sfc_par_diff",
           "allsky_sfc_par_dirh", "allsky_sfc_par_tot", "allsky_sfc_sw_diff", "allsky_sfc_sw_dirh", "allsky_sfc_sw_dni",
           "allsky_sfc_sw_dwn", "allsky_sfc_sw_up", "allsky_sfc_uv_index", "allsky_sfc_uva", "allsky_sfc_uvb",
           "allsky_srf_alb", "aod_55", "aod_55_adj", "aod_84", "cloud_amt", "cloud_amt_day", "cloud_amt_night",
           "cloud_od", "clrsky_days", "clrsky_kt", "clrsky_nkt", "clrsky_sfc_lw_dwn", "clrsky_sfc_lw_up",
           "clrsky_sfc_par_diff", "clrsky_sfc_par_dirh", "clrsky_sfc_par_tot", "clrsky_sfc_sw_diff",
           "clrsky_sfc_sw_dirh", "clrsky_sfc_sw_dni", "clrsky_sfc_sw_dwn", "clrsky_sfc_sw_up", "clrsky_srf_alb",
           "midday_insol", "original_allsky_sfc_sw_diff", "original_allsky_sfc_sw_dirh", "psh", "pw",
           "srf_alb_adj", "toa_sw_dni", "toa_sw_dwn", "ts_adj"],
    "era5": ["evaptrans", "latheat", "netsolrad", "press", "sktemp", "sotemp1", "sotemp2", "sotemp3", "temp",
             "totprec", "uwind", "vwind", "volsowat1", "volsowat12", "volsowat13"]
}


def save_cache(cache, cache_file_path):
    with open(cache_file_path, 'w') as f:
        json.dump(cache, f)


def load_cache(cache_file_path):
    try:
        with open(cache_file_path, 'r') as f:
            return json.load(f)
    except:
        return {}


async def query_climate_data(lat, lon, start_date, end_date, data_source, variable=None, cache=None):
    cache_key = f"{lat}_{lon}_{start_date}_{end_date}_{data_source}_{variable}"
    cache_hash = hashlib.md5(cache_key.encode()).hexdigest()
    if cache and cache_hash in cache:
        return cache[cache_hash]

    db_gen = get_db()
    db = await db_gen.__anext__()
    try:
        result = await get_climate_data_timeseries_logic(
            lat=lat, lon=lon,
            start_date=start_date, end_date=end_date,
            data_source=DataSource(data_source),
            variable=variable,
            db=db
        )
    finally:
        await db_gen.aclose()

    if cache is not None:
        cache[cache_hash] = result
    return result


async def process_csv_file(input_csv_path, output_csv_path, default_start_date=None, default_end_date=None,
                           process_all=False, cache_file_path="climate_data_cache.json"):
    cache = load_cache(cache_file_path)
    df = pd.read_csv(input_csv_path)
    results_df = df.copy()
    all_variable_dates = {}
    processed_coords = {}

    for index, row in df.iterrows():
        lat = row['latitude']
        lon = row['longitude']
        start_date = convert_date_format(row['data_final']) if 'data_final' in row and not pd.isna(row['data_final']) else default_start_date
        end_date = convert_date_format(row['date_final']) if 'date_final' in row and not pd.isna(row['date_final']) else default_end_date
        coord_key = f"{lat}_{lon}_{start_date}_{end_date}"

        if coord_key in processed_coords:
            for temp_key, api_response in processed_coords[coord_key].items():
                results_df.at[index, temp_key] = api_response
            continue

        coord_api_responses = {}
        for source, variables in DATA_SOURCES.items():
            for var in variables:
                data = await query_climate_data(lat, lon, start_date, end_date, source, var, cache)
                if not data or 'values' not in data:
                    continue
                temp_key = f"_api_response_{source}_{var}"
                results_df.at[index, temp_key] = json.dumps(data)
                coord_api_responses[temp_key] = json.dumps(data)
                for val in data['values']:
                    date_str = val.get('date') or f"{val.get('year')}-{val.get('month'):02d}"
                    col = f"{source}_{var}_{date_str}"
                    all_variable_dates[col] = True
        processed_coords[coord_key] = coord_api_responses
        time.sleep(0.1)

    save_cache(cache, cache_file_path)

    for col in sorted(all_variable_dates.keys()):
        results_df[col] = None

    for index, row in results_df.iterrows():
        for col in row.index:
            if col.startswith('_api_response_') and pd.notna(row[col]):
                data = json.loads(row[col])
                for val in data['values']:
                    date_str = val.get('date') or f"{val.get('year')}-{val.get('month'):02d}"
                    value = val.get('value') or val.get('values', {}).get(data.get('variable', 'value'))
                    key = f"{data['data_source']}_{data.get('variable', 'value')}_{date_str}"
                    if key in results_df.columns:
                        results_df.at[index, key] = value

    results_df.drop(columns=[col for col in results_df.columns if col.startswith('_api_response_')], inplace=True)
    results_df.to_csv(output_csv_path, index=False)
    print(f"Saved output to {output_csv_path}")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default="forest_data_v1.csv")
    parser.add_argument('--output', default="forest_data_with_climate.csv")
    parser.add_argument('--default-start-date', default="2000-01-01")
    parser.add_argument('--default-end-date', default="2000-12-31")
    parser.add_argument('--all-variables', action='store_true')
    parser.add_argument('--cache-file', default="climate_data_cache.json")
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
