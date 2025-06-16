import pandas as pd
from datetime import datetime
import time, json, argparse, hashlib, os
import asyncio
import sys
import subprocess
from tqdm import tqdm
from dateutil.parser import parse as try_parse_date
from collections import defaultdict
import glob
import zipfile


# Add virtual environment site-packages to path
venv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Api-v1", "venv"))
if sys.platform == 'win32':
    site_packages = os.path.join(venv_path, "Lib", "site-packages")
else:
    site_packages = os.path.join(venv_path, "lib", "python3.9", "site-packages")
if os.path.exists(site_packages):
    sys.path.insert(0, site_packages)

os.makedirs('batches', exist_ok=True)

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


STATIC_SOURCES = {'elev', 'soil', 'bio', 'koppen'}

DATA_SOURCES = {
    "wc": ["prec", "tmax", "tmin"],
    "spei": ["spei"],
    "chirps": ["chirps"],
    "et": ["et"],
    "elev": ["aspect", "elev", "flowdir", "hillshade", "roughness", "tpi", "tri", "slope"],
    "soil": ["bdod", "cec", "cfvo", "clay", "nitrogen", "ocd", "ocs", "phh2o", "sand", "silt", "soc", "wv0010", "wv0030", "wv1500"],
    "tc": ["aet", "def", "pdsi", "pet", "ppt", "q", "soil", "srad", "tmin", "tmax", "vap", "vpd", "ws"],
    "np": ["airmass", "allsky_kt", "allsky_nkt", "allsky_sfc_lw_dwn", "allsky_sfc_lw_up", "allsky_sfc_par_diff",
           "allsky_sfc_par_dirh", "allsky_sfc_par_tot", "allsky_sfc_sw_diff", "allsky_sfc_sw_dirh", "allsky_sfc_sw_dni",
           "allsky_sfc_sw_dwn", "allsky_sfc_sw_up", "allsky_sfc_uv_index", "allsky_sfc_uva", "allsky_sfc_uvb",
           "allsky_srf_alb", "midday_insol", "original_allsky_sfc_sw_diff", "original_allsky_sfc_sw_dirh", "psh", "pw",
           "srf_alb_adj", "toa_sw_dni", "toa_sw_dwn", "ts_adj"],
    "era5": ["evaptrans", "latheat", "netsolrad", "press", "sktemp", "sotemp1", "sotemp2", "sotemp3", "temp",
             "totprec", "uwind", "vwind", "volsowat1", "volsowat12", "volsowat13"],
    "bio": ["bio1", "bio2", "bio3", "bio4", "bio5",
        "bio6", "bio7", "bio8", "bio9", "bio10",
        "bio11", "bio12", "bio13", "bio14", "bio15",
        "bio16", "bio17", "bio18", "bio19"],
    "koppen": ["bsh", "dfb", "cfc", "cfa", "ef", "cwc", "af", "et", "cwb", "cwa",
    "csc", "bwk", "aw", "bsk", "dsb", "csa", "all", "dwb", "am", "dfc",
    "dwc", "cfb", "bwh", "csb", "dsc"]
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

    variable_key = (
        ','.join(variable) if isinstance(variable, list) else str(variable)
        if variable is not None else "None"
    )

    cache_key = f"{lat}_{lon}_{start_date}_{end_date}_{data_source}_{variable_key}"
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

def group_selected_vars_by_source(selected_set):
    by_source = defaultdict(list)
    for key in selected_set:
        src, var = key.split(':', 1)
        by_source[src].append(var)
    return by_source


def zip_batches(batch_pattern, zip_output_path):
    import glob
    batch_files = sorted(glob.glob(batch_pattern))
    with zipfile.ZipFile(zip_output_path, 'w') as zipf:
        for file in batch_files:
            zipf.write(file, arcname=os.path.basename(file))
    print(f"✅ Zipped all batches to {zip_output_path}")

async def process_one_row(
    row,
    index,
    start_col,
    end_col,
    selected_set,
    cache,
    semaphore
):
    async with semaphore:
        lat = row['latitude']
        lon = row['longitude']

        start_date_raw = row.get(start_col)
        end_date_raw = row.get(end_col)
        start_date = convert_date_format(start_date_raw)
        end_date = convert_date_format(end_date_raw)

        row_updates = {}

        # GROUP selected variables by data source
        vars_by_source = group_selected_vars_by_source(selected_set)

        for source, variables in vars_by_source.items():
            # Pass all variables for the source in a single call
            data = await query_climate_data(
                lat, lon, start_date, end_date, source, variables, cache
            )
            if not data or 'data' not in data:
                continue

            for entry in data['data']:
                if source in STATIC_SOURCES:
                    # Static: one value per variable
                    key = f"{source}_{entry['variable']}"
                    row_updates[key] = entry['value']
                else:
                    # Time series: values per date
                    date_str = entry.get("date") or f"{entry['year']}-{entry['month']:02d}"
                    for v, val in entry.get("values", {}).items():
                        key = f"{source}_{v}_{date_str}"
                        # Convert ERA5 units if needed
                        if source == "era5" and v in {"sktemp", "sotemp1", "sotemp2", "sotemp3", "temp"}:
                            val = val - 273.15
                        if source == 'era5' and v in {"totprec"}:
                            val = val * 1000
                        row_updates[key] = val

        return (index, row_updates)

async def process_csv_file(
    input_csv_path,
    output_csv_path,
    default_start_date=None,
    default_end_date=None,
    cache_file_path="climate_data_cache.json",
    selected_set=None,
    max_concurrent=60,
    checkpoint_size=100,      # <--- rows per output file
    checkpoint_prefix="batches/results_batch_",
    zip_output_path = "batches/"
):
    import math
    cache = load_cache(cache_file_path)
    df = pd.read_csv(input_csv_path)
    results_df = df.copy()
    start_col, end_col = detect_date_columns(df)
    semaphore = asyncio.Semaphore(max_concurrent)

    batch_updates = []
    batch_indices = []
    batch_number = 0

    tasks = [
        process_one_row(
            row,
            idx,
            start_col,
            end_col,
            selected_set,
            cache,
            semaphore
        )
        for idx, row in df.iterrows()
    ]

    updates = []
    for i, f in enumerate(tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="Processing rows")):
        result = await f
        updates.append(result)
        batch_updates.append(result)
        batch_indices.append(result[0])

        # Every checkpoint_size rows, write a checkpoint CSV
        if (i + 1) % checkpoint_size == 0:
            indices = []
            updates_dicts = []
            for idx, row_updates in batch_updates:
                indices.append(idx)
                updates_dicts.append(row_updates)
            updates_df = pd.DataFrame(updates_dicts, index=indices)
            file_name = f"{checkpoint_prefix}{batch_number}.csv"
            # Only output the batch
            batch_df = pd.concat([results_df.iloc[indices], updates_df], axis=1)
            batch_df = batch_df.copy()
            batch_df.to_csv(file_name, index=False)
            print(f"✅ Saved checkpoint {file_name} ({i+1} rows)")

            batch_updates = []
            batch_indices = []
            batch_number += 1

    # Write any remaining rows
    if batch_updates:
        indices = []
        updates_dicts = []
        for idx, row_updates in batch_updates:
            indices.append(idx)
            updates_dicts.append(row_updates)
        updates_df = pd.DataFrame(updates_dicts, index=indices)
        file_name = f"{checkpoint_prefix}{batch_number}.csv"
        batch_df = pd.concat([results_df.iloc[indices], updates_df], axis=1)
        batch_df = batch_df.copy()
        batch_df.to_csv(file_name, index=False)
        print(f"✅ Saved checkpoint {file_name} (final batch)")
    
    batch_pattern = f"{checkpoint_prefix}*.csv"
    zip_batches(batch_pattern, output_csv_path)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default="forest_data_v1.csv")
    parser.add_argument('--output', default="forest_data_with_climate.csv")
    parser.add_argument('--default-start-date', default="2000-01-01")
    parser.add_argument('--default-end-date', default="2000-12-31")
    parser.add_argument('--cache-file', default="climate_data_cache.json")
    parser.add_argument('--vars', default="[]")
    args = parser.parse_args()

    selected_pairs = json.loads(args.vars)
    selected_set = set(selected_pairs)

    await process_csv_file(
        input_csv_path=args.input,
        output_csv_path=args.output,
        default_start_date=args.default_start_date,
        default_end_date=args.default_end_date,
        cache_file_path=args.cache_file,
        selected_set=selected_set
    )

if __name__ == "__main__":
    asyncio.run(main())
