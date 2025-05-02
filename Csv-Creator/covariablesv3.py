import pandas as pd
import re
from tqdm import tqdm
import argparse
from datetime import datetime

def get_hemisphere(latitude):
    return "southern" if latitude < 0 else "northern"

def get_season_monthly(month, hemisphere):
    if hemisphere == "northern":
        if month in [12, 1, 2]: return "Winter"
        if month in [3, 4, 5]: return "Spring"
        if month in [6, 7, 8]: return "Summer"
        if month in [9, 10, 11]: return "Autumn"
    else:
        if month in [12, 1, 2]: return "Summer"
        if month in [3, 4, 5]: return "Autumn"
        if month in [6, 7, 8]: return "Winter"
        if month in [9, 10, 11]: return "Spring"

def get_season(date, hemisphere):
    month, day = date.month, date.day
    year = date.year
    if hemisphere == "northern":
        if (month == 12 and day >= 15) or (month <= 3 and (month < 3 or day < 15)):
            return year, "Winter"
        elif (month == 3 and day >= 15) or (month <= 6 and (month < 6 or day < 15)):
            return year, "Spring"
        elif (month == 6 and day >= 15) or (month <= 9 and (month < 9 or day < 15)):
            return year, "Summer"
        elif (month == 9 and day >= 15) or (month <= 12 and (month < 12 or day < 15)):
            return year, "Autumn"
    else:
        if (month == 12 and day >= 15) or (month <= 3 and (month < 3 or day < 15)):
            return year, "Summer"
        elif (month == 3 and day >= 15) or (month <= 6 and (month < 6 or day < 15)):
            return year, "Autumn"
        elif (month == 6 and day >= 15) or (month <= 9 and (month < 9 or day < 15)):
            return year, "Winter"
        elif (month == 9 and day >= 15) or (month <= 12 and (month < 12 or day < 15)):
            return year, "Spring"
    return None, None

def extract_et_covariates(df: pd.DataFrame) -> pd.DataFrame:
    pattern = re.compile(r"et_et_(\d{4})-(\d{2})")
    et_columns = [col for col in df.columns if pattern.match(col)]
    if not et_columns:
        print("No ET columns found.")
        return pd.DataFrame()

    date_range = [pd.to_datetime("{}-{}-01".format(*pattern.match(col).groups())) for col in et_columns]
    all_results = []

    for idx, row in tqdm(df.iterrows(), total=len(df), desc="Processing ET seasonal covariates"):
        lat = row['latitude']
        lon = row['longitude']
        hemisphere = get_hemisphere(lat)
        values = row[et_columns].values.tolist()

        tmp_df = pd.DataFrame({
            'Date': date_range,
            'ET': pd.to_numeric(values, errors='coerce')
        })
        tmp_df['Year'], tmp_df['Season'] = zip(*tmp_df['Date'].apply(lambda d: get_season(d, hemisphere)))
        tmp_df = tmp_df[tmp_df['ET'].notna()]

        grouped = tmp_df.groupby(['Year', 'Season'])['ET']
        if grouped.size().empty:
            continue

        summary_df = grouped.agg(['min', 'max', 'std']).reset_index()
        summary_df['CV'] = summary_df['std'] / grouped.mean().values

        for _, row_cov in summary_df.iterrows():
            result = {
                'latitude': lat,
                'longitude': lon,
                'year': int(row_cov['Year'])
            }
            season_code = row_cov['Season'][:2]  # Wi, Sp, Su, Au
            result[f'ET_Min_{season_code}'] = row_cov['min']
            result[f'ET_Max_{season_code}'] = row_cov['max']
            result[f'ET_Std_{season_code}'] = row_cov['std']
            result[f'ET_CV_{season_code}'] = row_cov['CV']
            all_results.append(result)

    return pd.DataFrame(all_results)

def extract_chirps_covariates_from_daily_columns(df: pd.DataFrame) -> pd.DataFrame:
    chirps_columns = [col for col in df.columns if re.match(r"chirps_chirps_\d{4}-\d{2}-\d{2}", col)]
    if not chirps_columns:
        print("No CHIRPS daily columns found.")
        return pd.DataFrame()

    date_range = [pd.to_datetime(col.replace("chirps_chirps_", ""), format="%Y-%m-%d") for col in chirps_columns]

    all_results = []

    for idx, row in tqdm(df.iterrows(), total=len(df), desc="Processing CHIRPS seasonal covariates"):
        lat = row['latitude']
        lon = row['longitude']
        precip_values = row[chirps_columns].values.tolist()
        seasonal_df = calculate_precip_covariates(date_range, (lon, lat), precip_values)

        for _, cov_row in seasonal_df.iterrows():
            result = {
                'latitude': lat,
                'longitude': lon,
                'year': cov_row['Year']
            }
            for col in cov_row.index:
                if col not in ['Year', 'Location']:
                    result[col] = cov_row[col]
            all_results.append(result)

    return pd.DataFrame(all_results)

def calculate_precip_covariates(date_range, coordinates, precip_values):
    df = pd.DataFrame({"Date": pd.to_datetime(date_range), "Precipitation": precip_values})

    hemisphere = get_hemisphere(coordinates[1])

    df["Year"], df["Season"] = zip(*df["Date"].apply(lambda d: get_season(d, hemisphere)))
    df.dropna(inplace=True)

    seasonal_stats = df.groupby(["Year", "Season"])["Precipitation"].agg(
        Sum="sum", Mean="mean", Median="median", Std_Dev="std"
    ).reset_index()

    seasonal_stats["CV"] = seasonal_stats["Std_Dev"] / seasonal_stats["Mean"]

    days_at_0mm = (
        df[df["Precipitation"] == 0]
        .groupby(["Year", "Season"])
        .size()
        .reset_index(name="DAt_0")
    )
    seasonal_stats = seasonal_stats.merge(days_at_0mm, on=["Year", "Season"], how="left").fillna(0)

    days_below_10mm = (
        df[df["Precipitation"] < 10]
        .groupby(["Year", "Season"])
        .size()
        .reset_index(name="DB_10")
    )
    seasonal_stats = seasonal_stats.merge(days_below_10mm, on=["Year", "Season"], how="left").fillna(0)

    def max_consecutive_days(series):
        return series.groupby((~series).cumsum()).transform("size").max() if series.any() else 0

    df["No_PR"] = df["Precipitation"] == 0
    max_consecutive = (
        df.groupby(["Year", "Season"])["No_PR"]
        .apply(max_consecutive_days)
        .reset_index(name="Cons_0_PR")
    )
    seasonal_stats = seasonal_stats.merge(max_consecutive, on=["Year", "Season"], how="left").fillna(0)

    seasonal_stats["Location"] = f"lat{coordinates[1]}_lon{coordinates[0]}"
    seasonal_stats = seasonal_stats.pivot(index=["Year", "Location"], columns="Season").reset_index()
    seasonal_stats.columns = [
        col[0] if col[1] == "" else f"{col[0]}_{col[1]}" for col in seasonal_stats.columns
    ]
    seasonal_stats.columns = seasonal_stats.columns.str.replace("Autumn", "Au").str.replace("Spring", "Sp").str.replace("Winter", "Wi").str.replace("Summer", "Su")
    seasonal_stats = seasonal_stats.rename(
        columns={col: f"ERA5_{col}" for col in seasonal_stats.columns if col not in ["Location", "Year"]}
    )
    return seasonal_stats

def extract_era5_covariates(df: pd.DataFrame) -> pd.DataFrame:
    all_results = []

    for var in ["evaptrans", "latheat", "netsolrad", "press", "sktemp", "sotemp1", "sotemp2", "sotemp3", "temp", "uwind", "vwind", "volsowat1", "volsowat12", "volsowat13"]:
        pattern = re.compile(rf"era5_{var}_(\d{{4}})-(\d{{2}})-(\d{{2}})")
        matching_cols = [col for col in df.columns if pattern.match(col)]
        if not matching_cols:
            continue

        dates = [pd.to_datetime(pattern.match(col).group(1) + '-' + pattern.match(col).group(2) + '-' + pattern.match(col).group(3)) for col in matching_cols]

        for idx, row in tqdm(df.iterrows(), total=len(df), desc=f"Processing ERA5 {var} covariates"):
            lat = row['latitude']
            lon = row['longitude']
            hemisphere = get_hemisphere(lat)
            values = pd.to_numeric(row[matching_cols].values.tolist(), errors='coerce')

            tmp_df = pd.DataFrame({'Date': dates, 'Value': values})
            tmp_df = tmp_df.dropna()
            tmp_df['Year'] = tmp_df['Date'].dt.year
            tmp_df['Season'] = tmp_df['Date'].apply(lambda d: get_season(d, hemisphere)[1])

            grouped = tmp_df.groupby(['Year', 'Season'])['Value']
            summary = grouped.agg(['min', 'max', 'std']).reset_index()
            std = grouped.std().reset_index(name="Std")
            mean = grouped.mean().reset_index(name="Mean")
            cv = (grouped.std() / grouped.mean()).reset_index(name="CV")

            summary = std.merge(mean, on=['Year', 'Season']).merge(cv, on=['Year', 'Season'])

            for _, row_cov in summary.iterrows():
                result = {
                    'latitude': lat,
                    'longitude': lon,
                    'year': int(row_cov['Year'])
                }
                for stat in ['min', 'max', 'std', 'CV']:
                    season_code = row_cov['Season'][:2]
                    result[f"ERA5_{var}_{stat}_{season_code}"] = row_cov[stat]
                all_results.append(result)

    return pd.DataFrame(all_results)

def extract_era5_totprec(df: pd.DataFrame) -> pd.DataFrame:
    pattern = re.compile(r"era5_totprec_(\d{4})-(\d{2})-(\d{2})")
    matching_columns = [col for col in df.columns if pattern.match(col)]
    if not matching_columns:
        print("No ERA5 totprec columns found.")
        return pd.DataFrame()

    date_range = [pd.to_datetime("{}-{}-{}".format(*pattern.match(col).groups())) for col in matching_columns]

    all_results = []
    for idx, row in tqdm(df.iterrows(), total=len(df), desc="Processing ERA5 totprec seasonal covariates"):
        lat = row['latitude']
        lon = row['longitude']
        precip_values = row[matching_columns].values.tolist()
        seasonal_df = calculate_precip_covariates(date_range, (lon, lat), precip_values)

        for _, cov_row in seasonal_df.iterrows():
            result = {
                'latitude': lat,
                'longitude': lon,
                'year': cov_row['Year']
            }
            for col in cov_row.index:
                if col not in ['Year', 'Location']:
                    result[col] = cov_row[col]
            all_results.append(result)

    return pd.DataFrame(all_results)

def extract_monthly_covariates(df: pd.DataFrame, source: str, variables: list, prefix: str) -> pd.DataFrame:
    all_results = []

    for var in variables:
        pattern = re.compile(rf"{source}_{var}_(\d{{4}})-(\d{{2}})")
        matching_columns = [col for col in df.columns if pattern.match(col)]
        if not matching_columns:
            print(f"No columns found for {source}/{var}")
            continue

        date_range = [pd.to_datetime("{}-{}-01".format(*pattern.match(col).groups())) for col in matching_columns]

        for idx, row in tqdm(df.iterrows(), total=len(df), desc=f"Processing {prefix} {var} covariates"):
            lat = row['latitude']
            lon = row['longitude']
            hemisphere = get_hemisphere(lat)
            values = row[matching_columns].values.tolist()

            tmp_df = pd.DataFrame({
                'Date': date_range,
                'Value': pd.to_numeric(values, errors='coerce')
            })
            tmp_df['Year'] = tmp_df['Date'].dt.year
            tmp_df['Season'] = tmp_df['Date'].dt.month.apply(lambda m: get_season_monthly(m, hemisphere))
            tmp_df = tmp_df[tmp_df['Value'].notna()]

            group = tmp_df.groupby(['Year', 'Season'])['Value']
            summary = {
                'Min': group.min(),
                'Max': group.max(),
                'Std': group.std(),
                'CV': group.std() / group.mean()
            }
            if source == 'wc':
                summary['Sum'] = group.sum()

            summary_df = pd.concat(summary, axis=1).reset_index()
            for _, row_cov in summary_df.iterrows():
                result = {
                    'latitude': lat,
                    'longitude': lon,
                    'year': int(row_cov['Year'])
                }
                for col in summary_df.columns[2:]:
                    season_code = row_cov['Season'][:2]
                    key = f"{prefix}_{var}_{col}_{season_code}"
                    result[key] = row_cov[col]
                all_results.append(result)

    return pd.DataFrame(all_results)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default="forest_data_with_climate.csv")
    parser.add_argument('--output', default="forest_data_with_covariates.csv")
    args = parser.parse_args()

    try:
        df = pd.read_csv(args.input)
        print(f"Loaded input CSV with {len(df)} rows.")
    except Exception as e:
        print(f"Failed to load input CSV: {e}")
        return

    chirps_df = extract_chirps_covariates_from_daily_columns(df)
    et_df = extract_et_covariates(df)
    wc_df = extract_monthly_covariates(df, 'wc', ["prec", "tmax", "tmin"], 'WC')
    spei_df = extract_monthly_covariates(df, 'spei', ["spei"], 'SPEI')
    tc_df = extract_monthly_covariates(df, 'tc', ["aet", "def", "pdsi", "pet", "ppt", "q", "soil", "srad", "tmin", "vap", "vpd", "ws"], 'TC')
    np_df = extract_monthly_covariates(df, 'np', ["airmass", "allsky_kt", "allsky_nkt", "allsky_sfc_lw_dwn", "allsky_sfc_lw_up", "allsky_sfc_par_diff",
           "allsky_sfc_par_dirh", "allsky_sfc_par_tot", "allsky_sfc_sw_diff", "allsky_sfc_sw_dirh", "allsky_sfc_sw_dni",
           "allsky_sfc_sw_dwn", "allsky_sfc_sw_up", "allsky_sfc_uv_index", "allsky_sfc_uva", "allsky_sfc_uvb",
           "allsky_srf_alb", "aod_55", "aod_55_adj", "aod_84", "cloud_amt", "cloud_amt_day", "cloud_amt_night",
           "cloud_od", "clrsky_days", "clrsky_kt", "clrsky_nkt", "clrsky_sfc_lw_dwn", "clrsky_sfc_lw_up",
           "clrsky_sfc_par_diff", "clrsky_sfc_par_dirh", "clrsky_sfc_par_tot", "clrsky_sfc_sw_diff",
           "clrsky_sfc_sw_dirh", "clrsky_sfc_sw_dni", "clrsky_sfc_sw_dwn", "clrsky_sfc_sw_up", "clrsky_srf_alb",
           "midday_insol", "original_allsky_sfc_sw_diff", "original_allsky_sfc_sw_dirh", "psh", "pw",
           "srf_alb_adj", "toa_sw_dni", "toa_sw_dwn", "ts_adj"], 'NP')
    era5_p_df = extract_era5_totprec(df)
    era5_rest_df = extract_era5_covariates(df)

    dfs = [chirps_df, et_df, wc_df, spei_df, tc_df, np_df, era5_p_df, era5_rest_df]
    for i, d in enumerate(dfs):
        if d is not None and not d.empty:
            dfs[i] = d.groupby(['latitude', 'longitude', 'year']).first().reset_index()

    from functools import reduce
    merged_df = reduce(lambda left, right: pd.merge(left, right, on=['latitude', 'longitude', 'year'], how='outer'), [d for d in dfs if not d.empty])

    if merged_df is not None and not merged_df.empty:
        for col in merged_df.columns:
            if col.startswith(('WC_', 'SPEI_', 'TC_', 'NP_')):
                merged_df[col] = pd.to_numeric(merged_df[col], errors='coerce')
                merged_df[col] = merged_df[col].apply(lambda x: pd.NA if isinstance(x, int) and x == 0 else x)

        merged_df.to_csv(args.output, index=False)
        print(f"✅ Saved merged seasonal covariates to {args.output}")
    else:
        print("⚠️ No covariates were generated. Output not saved.")

if __name__ == "__main__":
    main()
