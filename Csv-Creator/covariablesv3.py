import pandas as pd
import re
from tqdm import tqdm
import argparse
from datetime import datetime
import numpy as np
from scipy.stats import kurtosis, skew


def compute_biovars(prec, tmin, tmax):
    temp = (np.array(tmin) + np.array(tmax)) / 2
    prec = np.array(prec)

    bio = np.empty(19)

    bio[0]  = temp.mean()                          # BIO1: Annual Mean Temperature
    bio[1]  = np.mean(np.array(tmax) - np.array(tmin))  # BIO2: Mean Diurnal Range
    bio[2]  = (bio[1] / (np.max(tmax) - np.min(tmin))) * 100  # BIO3: Isothermality
    bio[3]  = np.std(temp, ddof=1) * 100            # BIO4: Temperature Seasonality
    bio[4]  = np.max(tmax)                          # BIO5: Max Temp of Warmest Month
    bio[5]  = np.min(tmin)                          # BIO6: Min Temp of Coldest Month
    bio[6]  = bio[4] - bio[5]                       # BIO7: Temperature Annual Range
    bio[7]  = temp[np.argmax(prec)]                 # BIO8: Mean Temp of Wettest Month
    bio[8]  = temp[np.argmin(prec)]                 # BIO9: Mean Temp of Driest Month
    bio[9]  = np.mean([tmax[month - 1] + tmin[month - 1] for month in [6, 7, 8]]) / 2  # BIO10: Mean Temp of Warmest Quarter
    bio[10] = np.mean([tmax[month - 1] + tmin[month - 1] for month in [11, 12, 1]]) / 2 # BIO11: Mean Temp of Coldest Quarter
    bio[11] = prec.sum()                            # BIO12: Annual Precipitation
    bio[12] = prec.max()                            # BIO13: Precip of Wettest Month
    bio[13] = prec.min()                            # BIO14: Precip of Driest Month
    bio[14] = (np.std(prec, ddof=1) / np.mean(prec)) * 100  # BIO15: Precip Seasonality (CV)

    quarters = [sum(prec[i:i+3]) for i in [0, 3, 6, 9]]
    wettest_q = np.argmax(quarters)
    driest_q = np.argmin(quarters)

    bio[15] = quarters[wettest_q]                   # BIO16: Precip of Wettest Quarter
    bio[16] = quarters[driest_q]                    # BIO17: Precip of Driest Quarter

    bio[17] = sum(prec[i] for i in range(wettest_q * 3, wettest_q * 3 + 3))  # BIO18: Precip of Warmest Quarter (assumed same as wettest)
    bio[18] = sum(prec[i] for i in range(driest_q * 3, driest_q * 3 + 3))    # BIO19: Precip of Coldest Quarter (assumed same as driest)

    return bio


def get_season_monthly(month):
    if month in [1, 2, 3]: return "Summer"
    if month in [4, 5, 6]: return "Autumn"
    if month in [7, 8, 9]: return "Winter"
    if month in [10, 11, 12]: return "Spring"

def get_season(date):
    month = date.month
    year = date.year
    if month in [1, 2, 3]:
        return year, "Summer"
    elif month in [4, 5, 6]:
        return year, "Autumn"
    elif month in [7, 8, 9]:
        return year, "Winter"
    else:
        return year, "Spring"
    
def compute_solar_radiation_from_wc_range(df: pd.DataFrame) -> pd.DataFrame:
    from math import pi

    output_rows = []

    for idx, row in tqdm(df.iterrows(), total=len(df), desc="SolarRad"):
        lat = row['latitude']
        lon = row['longitude']
        try:
            start = pd.to_datetime(row['start'])
            end = pd.to_datetime(row['end'])
            if pd.isna(start) or pd.isna(end):
                continue
        except Exception:
            continue


        months = pd.date_range(start=start, end=end, freq='MS')
        rs_by_year = {}

        for dt in months:
            year = dt.year
            month_str = dt.strftime('%Y-%m') + '-01'
            tmax_col = f'wc_tmax_{month_str}'
            tmin_col = f'wc_tmin_{month_str}'

            if tmax_col not in df.columns or tmin_col not in df.columns:
                continue

            try:
                tmax = float(row[tmax_col])
                tmin = float(row[tmin_col])
                if np.isnan(tmax) or np.isnan(tmin): continue
            except:
                continue

            J = 30 * (dt.month - 1) + 15
            lat_rad = lat * pi / 180
            delta = 0.409 * np.sin(2 * pi * J / 365 - 1.39)
            dr = 1 + 0.033 * np.cos(2 * pi * J / 365)
            ws = np.arccos(-np.tan(lat_rad) * np.tan(delta))
            Ra = (24 * 60 / pi) * 0.0820 * dr * (
                ws * np.sin(lat_rad) * np.sin(delta) +
                np.cos(lat_rad) * np.cos(delta) * np.sin(ws)
            )
            Rs = 0.16 * np.sqrt(tmax - tmin) * Ra
            rs_by_year.setdefault(year, []).append(Rs)

        for year, rs_list in rs_by_year.items():
            avg_rs = np.nanmean(rs_list)
            output_rows.append({
                'latitude': lat,
                'longitude': lon,
                'year': year,
                'Har_SolarRad_Mean': avg_rs
            })
    
    print(f"Computed solar radiation for {len(output_rows)} location-years.")
    return pd.DataFrame(output_rows)


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
        values = row[et_columns].values.tolist()

        tmp_df = pd.DataFrame({
            'Date': date_range,
            'ET': pd.to_numeric(values, errors='coerce')
        })
        tmp_df['Year'], tmp_df['Season'] = zip(*tmp_df['Date'].apply(lambda d: get_season(d)))
        tmp_df = tmp_df[tmp_df['ET'].notna()]

        grouped = tmp_df.groupby(['Year', 'Season'])['ET']
        if grouped.size().empty:
            continue

        summary_df = grouped.agg(['min', 'max', 'std', 'mean']).reset_index()
        summary_df['CV'] = summary_df['std'] / grouped.mean().values

        for _, row_cov in summary_df.iterrows():
            result = {
                'latitude': lat,
                'longitude': lon,
                'year': int(row_cov['Year'])
            }
            season_code = row_cov['Season'][:2]  # Wi, Sp, Su, Au
            result[f'ET_Mean_{season_code}'] = row_cov['mean']
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
        seasonal_df = calculate_precip_covariates(date_range, (lon, lat), precip_values, prefix="CHIRPS_")

        for _, cov_row in seasonal_df.iterrows():
            result = {'latitude': lat, 'longitude': lon, 'year': cov_row['Year']}
            for col in cov_row.index:
                if col not in ['Year', 'Location']:
                    result[col] = cov_row[col]
            all_results.append(result)

    return pd.DataFrame(all_results)

def calculate_precip_covariates(date_range, coordinates, precip_values, prefix="ERA5_"):
    df = pd.DataFrame({"Date": pd.to_datetime(date_range), "Precipitation": precip_values})
    df["Year"], df["Season"] = zip(*df["Date"].apply(get_season))
    df.dropna(inplace=True)

    # Add month column for extra annual stats
    df["Month"] = df["Date"].dt.month

    # Seasonal aggregation
    seasonal_stats = df.groupby(["Year", "Season"], as_index=False)["Precipitation"].agg(
        Sum="sum",
        Mean="mean",
        Median="median",
        Std_Dev="std",
        CV=lambda x: x.std() / x.mean() if x.mean() != 0 else np.nan,
        Skew=lambda x: skew(x, nan_policy='omit'),
        Kurtosis=lambda x: kurtosis(x, nan_policy='omit') if x.count() >= 4 and x.std() > 0 else np.nan,
        Q5=lambda x: x.quantile(0.05),
        Q95=lambda x: x.quantile(0.95)
    )

    # Additional seasonal indicators
    days_at_0mm = df[df["Precipitation"] == 0].groupby(["Year", "Season"]).size().reset_index(name="DAt_0")
    days_below_10mm = df[df["Precipitation"] < 10].groupby(["Year", "Season"]).size().reset_index(name="DB_10")
    df["No_PR"] = df["Precipitation"] == 0
    max_consecutive = df.groupby(["Year", "Season"])["No_PR"].apply(
        lambda s: s.groupby((~s).cumsum()).transform("size").max() if s.any() else 0
    ).reset_index(name="Cons_0_PR")

    # Merge all seasonal components
    seasonal_stats = seasonal_stats.merge(days_at_0mm, on=["Year", "Season"], how="left").fillna(0)
    seasonal_stats = seasonal_stats.merge(days_below_10mm, on=["Year", "Season"], how="left").fillna(0)
    seasonal_stats = seasonal_stats.merge(max_consecutive, on=["Year", "Season"], how="left").fillna(0)

    # Pivot seasonal stats to wide format
    seasonal_stats["Location"] = f"lat{coordinates[1]}_lon{coordinates[0]}"
    seasonal_stats = seasonal_stats.pivot(index=["Year", "Location"], columns="Season").reset_index()
    seasonal_stats.columns = [
        col[0] if col[1] == "" else f"{col[0]}_{col[1]}" for col in seasonal_stats.columns
    ]
    seasonal_stats.columns = seasonal_stats.columns.str.replace("Autumn", "Au").str.replace("Spring", "Sp") \
        .str.replace("Winter", "Wi").str.replace("Summer", "Su")
    seasonal_stats = seasonal_stats.rename(
        columns={col: f"{prefix}{col}" for col in seasonal_stats.columns if col not in ["Location", "Year"]}
    )

    monthly_sum = df.groupby(["Year", "Month"])["Precipitation"].sum().reset_index()
    annual_total = df.groupby("Year")["Precipitation"].sum().reset_index(name=f"{prefix}Pr_Total")
    wet_dry = monthly_sum.groupby("Year")["Precipitation"].agg([
        ("WetMon", "max"),
        ("DryMon", "min")
    ]).reset_index()
    wet_dry = wet_dry.rename(columns={
        "WetMon": f"{prefix}Pr_WetMon",
        "DryMon": f"{prefix}Pr_DryMon"
    })
    extra = pd.merge(annual_total, wet_dry, on="Year")
    extra["Location"] = f"lat{coordinates[1]}_lon{coordinates[0]}"

    # Merge seasonal + annual
    full_df = pd.merge(seasonal_stats, extra, on=["Year", "Location"], how="outer")
    return full_df


def extract_era5_covariates(df: pd.DataFrame) -> pd.DataFrame:
    all_results = []

    for var in ["evaptrans", "latheat", "netsolrad", "press", "sktemp", "sotemp1", "sotemp2", "sotemp3",
                "temp", "uwind", "vwind", "volsowat1", "volsowat12", "volsowat13"]:
        
        pattern = re.compile(rf"era5_{var}_(\d{{4}})-(\d{{2}})-(\d{{2}})")
        matching_cols = [col for col in df.columns if pattern.match(col)]
        if not matching_cols:
            continue

        for idx, row in tqdm(df.iterrows(), total=len(df), desc=f"Processing ERA5 {var} covariates"):
            lat = row['latitude']
            lon = row['longitude']

            valid_cols = [col for col in matching_cols if not pd.isna(row[col])]
            if not valid_cols:
                continue

            dates, values = [], []
            for col in valid_cols:
                m = pattern.match(col)
                if m:
                    dates.append(pd.to_datetime(f"{m.group(1)}-{m.group(2)}-{m.group(3)}"))
                    values.append(pd.to_numeric(row[col], errors='coerce'))

            if not values or all(pd.isna(values)):
                continue

            tmp_df = pd.DataFrame({'Date': dates, 'Value': values}).dropna()
            tmp_df['Year'] = tmp_df['Date'].dt.year
            tmp_df['Season'] = tmp_df['Date'].apply(lambda d: get_season(d)[1])

            grouped = tmp_df.groupby(['Year', 'Season'])['Value']
            summary = grouped.agg(
                mean='mean',
                min='min',
                max='max',
                std='std',
                skew='skew',
                kurtosis=lambda x: kurtosis(x, nan_policy='omit') if x.count() >= 4 and x.std() > 0 else np.nan,
                p5=lambda x: x.quantile(0.05),
                p95=lambda x: x.quantile(0.95),
                cv=lambda x: x.std() / x.mean() if x.mean() != 0 else np.nan
            ).reset_index()

            for _, row_cov in summary.iterrows():
                result = {
                    'latitude': lat,
                    'longitude': lon,
                    'year': int(row_cov['Year'])
                }
                season_code = row_cov['Season'][:2]
                for stat_key, label in zip(
                    ['mean', 'min', 'max', 'std', 'cv', 'skew', 'kurtosis', 'p5', 'p95'],
                    ['mean', 'min', 'max', 'std', 'CV', 'Skew', 'Kurtosis', 'Q5', 'Q95']
                ):
                    result[f"ERA5_{var}_{label}_{season_code}"] = row_cov[stat_key]
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
        seasonal_df = calculate_precip_covariates(date_range, (lon, lat), precip_values, prefix="ERA5_prec_")

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

def extract_era5_temp_precip_covariates(df: pd.DataFrame) -> pd.DataFrame:
    import re
    all_results = []

    pattern_temp = re.compile(r"era5_temp_(\d{4})-(\d{2})-(\d{2})")
    pattern_prec = re.compile(r"era5_totprec_(\d{4})-(\d{2})-(\d{2})")

    temp_cols = [col for col in df.columns if pattern_temp.match(col)]
    prec_cols = [col for col in df.columns if pattern_prec.match(col)]

    # Sanity check
    if not temp_cols or not prec_cols:
        print("Missing ERA5 daily temperature or precipitation columns.")
        return pd.DataFrame()

    # Convert column names to dates
    dates_temp = [pd.to_datetime(f"{pattern_temp.match(col).group(1)}-{pattern_temp.match(col).group(2)}-{pattern_temp.match(col).group(3)}")
                  for col in temp_cols]
    dates_prec = [pd.to_datetime(f"{pattern_prec.match(col).group(1)}-{pattern_prec.match(col).group(2)}-{pattern_prec.match(col).group(3)}")
                  for col in prec_cols]

    for idx, row in tqdm(df.iterrows(), total=len(df), desc="ERA5 temp+precip covariates"):
        lat = row['latitude']
        lon = row['longitude']
        temp_series = pd.Series(pd.to_numeric(row[temp_cols].values, errors='coerce'), index=dates_temp)
        prec_series = pd.Series(pd.to_numeric(row[prec_cols].values, errors='coerce'), index=dates_prec)

        # Align indexes just in case
        df_temp = temp_series.dropna().reset_index()
        df_temp.columns = ['time', 'Temp']
        df_prec = prec_series.dropna().reset_index()
        df_prec.columns = ['time', 'Precipitation']

        # Compute mock Tmax and Tmin using rolling windows (daily data only available)
        df_temp['Tmax'] = df_temp['Temp'].rolling(3, min_periods=1).max()
        df_temp['Tmin'] = df_temp['Temp'].rolling(3, min_periods=1).min()

        df_merged = pd.merge(df_temp, df_prec, on='time', how='inner')
        df_merged['Year'] = df_merged['time'].dt.year
        df_merged['Month'] = df_merged['time'].dt.month

        if df_merged.empty:
            continue

        # Annual temperature stats
        temp_stats = df_merged.groupby(['Year']).apply(lambda x: pd.Series({
            "ERA5_Temp_Mean": ((x['Tmax'] + x['Tmin']) / 2).mean(),
            "ERA5_Mean_Diu_Rng": (x['Tmax'] - x['Tmin']).mean(),
            "ERA5_Temp_Max_HotMon": x.groupby(x['Month'])['Tmax'].mean().max(),
            "ERA5_Temp_Min_ColdMon": x.groupby(x['Month'])['Tmin'].mean().min(),
            "ERA5_Temp_Rng": x['Tmax'].max() - x['Tmin'].min()
        })).reset_index()

        # Quarterly aggregation
        results = []
        for year in df_merged['Year'].unique():
            df_y = df_merged[df_merged['Year'] == year].copy()
            df_y = df_y.set_index('time')

            quarters = {
                "Q1": slice(f"{year}-01-01", f"{year}-03-31"),
                "Q2": slice(f"{year}-04-01", f"{year}-06-30"),
                "Q3": slice(f"{year}-07-01", f"{year}-09-30"),
                "Q4": slice(f"{year}-10-01", f"{year}-12-31")
            }

            q_metrics = {}
            for q, rng in quarters.items():
                q_tmax = df_y.loc[rng]['Tmax'].mean()
                q_tmin = df_y.loc[rng]['Tmin'].mean()
                q_prec = df_y.loc[rng]['Precipitation'].sum()
                q_metrics[q] = {
                    "mean_temp": (q_tmax + q_tmin) / 2,
                    "precip": q_prec
                }

            wettest_q = max(q_metrics, key=lambda k: q_metrics[k]["precip"])
            driest_q = min(q_metrics, key=lambda k: q_metrics[k]["precip"])
            hottest_q = max(q_metrics, key=lambda k: q_metrics[k]["mean_temp"])
            coldest_q = min(q_metrics, key=lambda k: q_metrics[k]["mean_temp"])

            results.append({
                "latitude": lat,
                "longitude": lon,
                "year": year,
                "ERA5_Temp_Mean_WetQ": q_metrics[wettest_q]["mean_temp"],
                "ERA5_Temp_Mean_DryQ": q_metrics[driest_q]["mean_temp"],
                "ERA5_Temp_Mean_HotQ": q_metrics[hottest_q]["mean_temp"],
                "ERA5_Temp_Mean_ColdQ": q_metrics[coldest_q]["mean_temp"],
                "ERA5_Pr_Mean_WetQ": q_metrics[wettest_q]["precip"],
                "ERA5_Pr_Mean_DryQ": q_metrics[driest_q]["precip"],
                "ERA5_Pr_Mean_HotQ": q_metrics[hottest_q]["precip"],
                "ERA5_Pr_Mean_ColdQ": q_metrics[coldest_q]["precip"]
            })

        df_quarters = pd.DataFrame(results)
        final = pd.merge(temp_stats, df_quarters, left_on='Year', right_on='year', how='inner').drop(columns=['year'])
        final['latitude'] = lat
        final['longitude'] = lon
        final = final.rename(columns={'Year': 'year'})  # Optional but consistent
        all_results.append(final)

    return pd.concat(all_results, ignore_index=True) if all_results else pd.DataFrame()


def extract_biovars_from_tc_and_chirps(df, tc_vars=['tmax', 'tmin'], chirps_prefix='chirps_chirps_'):
    all_results = []

    # --- Gather TC tmax/tmin columns ---
    tc_col_map = {}
    for var in tc_vars:
        tc_col_map[var] = [col for col in df.columns if re.match(rf"tc_{var}_(\d{{4}})-(\d{{2}})", col)]

    # --- Gather all daily CHIRPS columns ---
    chirps_day_cols = [col for col in df.columns if re.match(rf"{chirps_prefix}\d{{4}}-\d{{2}}-\d{{2}}", col)]

    for idx, row in tqdm(df.iterrows(), total=len(df), desc="BIOVARS from TC + CHIRPS"):
        lat, lon = row['latitude'], row['longitude']

        # Aggregate CHIRPS daily data to monthly sums for this row
        chirps_monthly = {}
        if chirps_day_cols:
            dates_vals = [
                (pd.to_datetime(col.replace(chirps_prefix, ""), format="%Y-%m-%d"),
                 pd.to_numeric(row[col], errors='coerce'))
                for col in chirps_day_cols if not pd.isna(row[col])
            ]
            if dates_vals:
                chirps_mo_df = pd.DataFrame(dates_vals, columns=['date', 'prec'])
                chirps_mo_df['year'] = chirps_mo_df['date'].dt.year
                chirps_mo_df['month'] = chirps_mo_df['date'].dt.month
                grouped = chirps_mo_df.groupby(['year', 'month'])['prec'].sum().reset_index()
                chirps_monthly = {(int(y), int(m)): v for y, m, v in grouped.itertuples(index=False)}

        # Gather TC tmax/tmin monthly for this row
        tc_monthly = {}
        for var in tc_vars:
            for col in tc_col_map[var]:
                m = re.search(r"tc_(\w+)_(\d{4})-(\d{2})", col)
                if m:
                    year, month = int(m.group(2)), int(m.group(3))
                    val = pd.to_numeric(row[col], errors='coerce')
                    tc_monthly.setdefault((year, month), {})[var] = val

        # For years where we have all 12 months of tmax, tmin (TC) and CHIRPS precip
        all_years = set(y for (y, m) in chirps_monthly.keys()) & set(y for (y, m) in tc_monthly.keys())

        for year in sorted(all_years):
            tmax_vals = np.array([tc_monthly.get((year, m), {}).get('tmax', np.nan) for m in range(1, 13)])
            tmin_vals = np.array([tc_monthly.get((year, m), {}).get('tmin', np.nan) for m in range(1, 13)])
            prec_vals = np.array([chirps_monthly.get((year, m), np.nan) for m in range(1, 13)])

            # Require at least 10 months of data for each
            valid_mask = lambda arr: np.count_nonzero(~np.isnan(arr)) >= 10
            if all(valid_mask(arr) for arr in [tmax_vals, tmin_vals, prec_vals]):
                try:
                    bio = compute_biovars(prec_vals, tmin_vals, tmax_vals)
                    bio_result = {
                        'latitude': lat,
                        'longitude': lon,
                        'year': year
                    }
                    bio_result.update({f"TC_CHIRPS_BIO_{idx+1}": val for idx, val in enumerate(bio)})
                    all_results.append(bio_result)
                except Exception as e:
                    print(f"[BIOVARS ERROR] lat={lat} lon={lon} year={year} — {e}")

    return pd.DataFrame(all_results)


def extract_monthly_covariates(df: pd.DataFrame, source: str, variables: list, prefix: str) -> pd.DataFrame:
    all_results = []
    data_by_var = {}

    # --- Collect all matching columns for each variable ---
    for var in variables:
        pattern = re.compile(rf"{source}_{var}_(\d{{4}})-(\d{{2}})")
        matching_columns = [col for col in df.columns if pattern.match(col)]
        if matching_columns:
            data_by_var[var] = matching_columns
        else:
            print(f"No columns found for {source}/{var}")


    for idx, row in tqdm(df.iterrows(), total=len(df), desc=f"Processing {source.upper()} covariates"):
        lat, lon = row['latitude'], row['longitude']

        # --- Seasonal stats for each variable ---
        for var, matching_columns in data_by_var.items():
            values = pd.to_numeric(row[matching_columns], errors='coerce')
            regex = re.compile(r"(\d{4})-(\d{2})")
            dates = [pd.to_datetime(f"{regex.search(col).group(0)}-01") for col in matching_columns]
            tmp_df = pd.DataFrame({'Date': dates, 'Value': values})
            tmp_df['Year'] = tmp_df['Date'].dt.year
            tmp_df['Season'] = tmp_df['Date'].dt.month.apply(lambda m: get_season_monthly(m))
            tmp_df = tmp_df[tmp_df['Value'].notna()]

            group = tmp_df.groupby(['Year', 'Season'])['Value']
            summary = {
                'Mean': group.mean(),
                'Min': group.min(),
                'Max': group.max(),
                'Std': group.std(),
                'CV': group.std() / group.mean(),
                'Skew': group.apply(lambda x: x.skew()),
                'Q5': group.apply(lambda x: x.quantile(0.05)),
                'Q95': group.apply(lambda x: x.quantile(0.95))
            }
            if source == 'wc' and var == 'prec':
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

            if source == 'tc':
                ann_mean = tmp_df.groupby('Year')['Value'].mean().reset_index()
                for _, row_ann in ann_mean.iterrows():
                    all_results.append({
                        'latitude': lat,
                        'longitude': lon,
                        'year': int(row_ann['Year']),
                        f"{prefix}_{var}_Mean_year": row_ann['Value']
                    })

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
    
        # --- Extract static elev_ and soil_ columns ---
    static_cols = ['latitude', 'longitude'] + [col for col in df.columns if col.startswith("elev_") or col.startswith("soil_") or col.startswith("bio_") or col.startswith("koppen_")]
    static_df = df[static_cols].drop_duplicates(subset=["latitude", "longitude"])

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
    era5_quartile = extract_era5_temp_precip_covariates(df)
    SolarRad = compute_solar_radiation_from_wc_range(df)
    bio_df = extract_biovars_from_tc_and_chirps(df)

    dynamic_dfs = [chirps_df, et_df, wc_df, spei_df, tc_df, np_df, era5_p_df, era5_rest_df, era5_quartile, SolarRad, bio_df]
    for i, d in enumerate(dynamic_dfs):
        if d is not None and not d.empty:
            dynamic_dfs[i] = d.groupby(['latitude', 'longitude', 'year']).first().reset_index()

    from functools import reduce
    merged_df = reduce(lambda left, right: pd.merge(left, right, on=['latitude', 'longitude', 'year'], how='outer'), [d for d in dynamic_dfs if not d.empty])

    # Merge static columns after
    if not static_df.empty and not merged_df.empty:
        merged_df = pd.merge(merged_df, static_df, on=['latitude', 'longitude'], how='left')

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
