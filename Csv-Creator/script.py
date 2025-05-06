import pandas as pd
from datetime import datetime
import time, json, argparse, hashlib, os
import asyncio
import sys
from tqdm import tqdm
from dateutil.parser import parse as try_parse_date

# Add virtual environment site-packages to path
venv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Api-v1", "venv"))
if sys.platform == 'win32':
    site_packages = os.path.join(venv_path, "Lib", "site-packages")
else:
    site_packages = os.path.join(venv_path, "lib", "python3.9", "site-packages")
if os.path.exists(site_packages):
    sys.path.insert(0, site_packages)

# Add API source path
api_v1_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Api-v1"))
if api_v1_path not in sys.path:
    sys.path.insert(0, api_v1_path)

from app.database import get_db
from app.main import DataSource
from app.climate_data_service import get_climate_data_timeseries_logic

def convert_date_format(date_str):
    if pd.isna(date_str):  # handle NaN explicitly
        return None
    date_str = str(date_str).strip()  # ensure it's a clean string
    formats = ['%m/%d/%Y', '%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%Y/%m/%d']
    for fmt in formats:
        try:
            date_obj = datetime.strptime(date_str, fmt)
            return date_obj.strftime('%Y-%m-%d')
        except ValueError:
            continue
    return date_str  # fallback: return as-is


def detect_date_columns(df):
    """Detect two datetime columns from the DataFrame."""
    date_cols = []
    for col in df.columns:
        try:
            # Try first non-null value
            sample_val = df[col].dropna().iloc[0]
            if isinstance(sample_val, (int, float)) and sample_val < 10000:
                continue  # Likely not a date (e.g., lat/lon)
            parsed = try_parse_date(str(sample_val), fuzzy=False)
            date_cols.append(col)
        except (ValueError, IndexError, TypeError):
            continue
    if len(date_cols) >= 2:
        return date_cols[:2]
    elif len(date_cols) == 1:
        return date_cols[0], date_cols[0]
    else:
        return None, None


STATIC_SOURCES = {'elev', 'soil', 'bio'}

DATA_SOURCES = {
    "wc": ["prec", "tmax", "tmin"],
    "spei": ["spei"],
    "chirps": ["chirps"],
    "et": ["et"],
    "elev": ["aspect", "elev", "flowdir", "hillshade", "roughness", "tpi", "tri", "slope"],
    "soil": ["bdod", "cec", "cfvo", "clay", "nitrogen", "ocd", "ocs", "phh2o", "sand", "silt", "soc", "wv0010", "wv0030", "wv1500"],
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
             "totprec", "uwind", "vwind", "volsowat1", "volsowat12", "volsowat13"],
    "bio": ["bio1", "bio2", "bio3", "bio4", "bio5",
        "bio6", "bio7", "bio8", "bio9", "bio10",
        "bio11", "bio12", "bio13", "bio14", "bio15",
        "bio16", "bio17", "bio18", "bio19"]
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

async def process_csv_file(input_csv_path, output_csv_path, default_start_date=None, default_end_date=None, cache_file_path="climate_data_cache.json"):
    cache = load_cache(cache_file_path)
    df = pd.read_csv(input_csv_path)
    results_df = df.copy()
    new_columns = set()

    all_rows_updates = []

    # Detect date columns once
    start_col, end_col = detect_date_columns(df)

    for index, row in tqdm(df.iterrows(), total=len(df), desc="Processing rows"):
        lat = row['latitude']
        lon = row['longitude']

        start_date_raw = row.get(start_col) if start_col else default_start_date
        end_date_raw = row.get(end_col) if end_col else default_end_date

        start_date = convert_date_format(start_date_raw)
        end_date = convert_date_format(end_date_raw)

        row_updates = {}

        for source, variables in DATA_SOURCES.items():
            for var in variables:
                data = await query_climate_data(lat, lon, start_date, end_date, source, var, cache)
                if not data or 'data' not in data:
                    continue

                for entry in data['data']:
                    if source in STATIC_SOURCES:
                        key = f"{source}_{entry['variable']}"
                        row_updates[key] = entry['value']
                        new_columns.add(key)
                    else:
                        date_str = entry.get("date") or f"{entry['year']}-{entry['month']:02d}"
                        for v, val in entry.get("values", {}).items():
                            key = f"{source}_{v}_{date_str}"
                            row_updates[key] = val
                            new_columns.add(key)

        all_rows_updates.append(row_updates)
        # time.sleep(0.05)

    # Add new columns to avoid fragmentation
    for col in sorted(new_columns):
        if col not in results_df.columns:
            results_df[col] = pd.NA

    # Apply all updates efficiently
    for i, updates in enumerate(all_rows_updates):
        if updates:
            for key, value in updates.items():
                results_df.iat[i, results_df.columns.get_loc(key)] = value

    save_cache(cache, cache_file_path)

    results_df.to_csv(output_csv_path, index=False)
    print(f"✅ Saved output to {output_csv_path}")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default="forest_data_v1.csv")
    parser.add_argument('--output', default="forest_data_with_climate.csv")
    parser.add_argument('--default-start-date', default="2000-01-01")
    parser.add_argument('--default-end-date', default="2000-12-31")
    parser.add_argument('--cache-file', default="climate_data_cache.json")
    args = parser.parse_args()

    await process_csv_file(
        input_csv_path=args.input,
        output_csv_path=args.output,
        default_start_date=args.default_start_date,
        default_end_date=args.default_end_date,
        cache_file_path=args.cache_file
    )

if __name__ == "__main__":
    asyncio.run(main())
