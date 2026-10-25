"""
Data Analysis & Visualization Engine
Road Accident Data Analysis System

Uses:
- Pandas for grouping, slicing, aggregations, cross-tabulations, and time-series extraction.
- NumPy for descriptive statistics (mean, median, standard deviation, variance, quantiles).
- Matplotlib for rendering high-quality analytical charts (PNG bytes and base64).
"""

import io
import base64
from datetime import datetime
import pandas as pd
import numpy as np
import matplotlib
# Use non-interactive Agg backend for thread safety and server environments
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

from database import get_raw_records_for_df

# Custom aesthetic color palette
PALETTE = {
    "primary": "#3B82F6",      # Bright Blue
    "secondary": "#8B5CF6",    # Purple
    "accent": "#06B6D4",       # Cyan
    "minor": "#10B981",        # Emerald Green
    "serious": "#F59E0B",      # Amber Yellow
    "fatal": "#EF4444",        # Crimson Red
    "dark_bg": "#0F172A",      # Slate 900
    "card_bg": "#1E293B",      # Slate 800
    "text": "#F8FAFC",         # Slate 50
    "muted_text": "#94A3B8",   # Slate 400
    "grid": "#334155"          # Slate 700
}

SEVERITY_COLORS = {
    "Minor": PALETTE["minor"],
    "Serious": PALETTE["serious"],
    "Fatal": PALETTE["fatal"]
}

def load_dataframe(filters=None):
    """
    Pulls accident data from the database and constructs an enriched Pandas DataFrame.
    """
    records = get_raw_records_for_df(filters)
    if not records:
        # Return empty dataframe with expected schema
        return pd.DataFrame(columns=[
            "accident_id", "accident_datetime", "vehicle_type",
            "severity", "weather", "region", "road_name",
            "year", "month", "month_name", "hour", "day_name", "time_of_day"
        ])

    df = pd.DataFrame(records)
    df["accident_datetime"] = pd.to_datetime(df["accident_datetime"])
    
    # Enrich with temporal features
    df["year"] = df["accident_datetime"].dt.year
    df["month"] = df["accident_datetime"].dt.month
    df["month_name"] = df["accident_datetime"].dt.strftime("%b")
    df["day_name"] = df["accident_datetime"].dt.day_name()
    df["hour"] = df["accident_datetime"].dt.hour

    # Time-of-day classification
    def categorize_time(hour):
        if 5 <= hour < 12:
            return "Morning (05:00 - 11:59)"
        elif 12 <= hour < 17:
            return "Afternoon (12:00 - 16:59)"
        elif 17 <= hour < 22:
            return "Evening (17:00 - 21:59)"
        else:
            return "Night (22:00 - 04:59)"

    df["time_of_day"] = df["hour"].apply(categorize_time)
    return df


def get_summary_statistics(filters=None):
    """
    Computes key metrics and NumPy descriptive statistics.
    """
    df = load_dataframe(filters)
    total_accidents = len(df)

    if total_accidents == 0:
        return {
            "total_accidents": 0,
            "minor_count": 0,
            "serious_count": 0,
            "fatal_count": 0,
            "minor_pct": 0,
            "serious_pct": 0,
            "fatal_pct": 0,
            "mean_per_month": 0,
            "median_per_month": 0,
            "std_per_month": 0,
            "iqr_per_month": 0,
            "most_common_vehicle": "N/A",
            "peak_risk_region": "N/A",
            "peak_risk_hour": "N/A",
            "disclaimer": "Analysis demonstrates observational associations and empirical patterns, not causal relationships."
        }

    # Severity counts & proportions
    sev_counts = df["severity"].value_counts().to_dict()
    minor = sev_counts.get("Minor", 0)
    serious = sev_counts.get("Serious", 0)
    fatal = sev_counts.get("Fatal", 0)

    # Monthly accident aggregation for NumPy descriptive statistics
    monthly_series = df.set_index("accident_datetime").resample("ME").size()
    monthly_counts = monthly_series.to_numpy()

    if len(monthly_counts) > 0:
        mean_monthly = float(np.mean(monthly_counts))
        median_monthly = float(np.median(monthly_counts))
        std_monthly = float(np.std(monthly_counts, ddof=1)) if len(monthly_counts) > 1 else 0.0
        q75, q25 = np.percentile(monthly_counts, [75, 25])
        iqr_monthly = float(q75 - q25)
    else:
        mean_monthly = median_monthly = std_monthly = iqr_monthly = 0.0

    # Mode / Top entities
    top_vehicle = df["vehicle_type"].mode().iloc[0] if not df["vehicle_type"].empty else "N/A"
    top_region = df["region"].mode().iloc[0] if not df["region"].empty else "N/A"
    top_hour_int = int(df["hour"].mode().iloc[0]) if not df["hour"].empty else 0
    top_hour_str = f"{top_hour_int:02d}:00 - {(top_hour_int+1)%24:02d}:00"

    return {
        "total_accidents": int(total_accidents),
        "minor_count": int(minor),
        "serious_count": int(serious),
        "fatal_count": int(fatal),
        "minor_pct": round((minor / total_accidents) * 100, 1),
        "serious_pct": round((serious / total_accidents) * 100, 1),
        "fatal_pct": round((fatal / total_accidents) * 100, 1),
        "mean_per_month": round(mean_monthly, 2),
        "median_per_month": round(median_monthly, 2),
        "std_per_month": round(std_monthly, 2),
        "iqr_per_month": round(iqr_monthly, 2),
        "most_common_vehicle": top_vehicle,
        "peak_risk_region": top_region,
        "peak_risk_hour": top_hour_str,
        "dataset_source": "Synthetic Demonstration Dataset (Simulated Urban Transit & Corridor Data across Andhra Pradesh)",
        "location_granularity": "Andhra Pradesh Regional Sectors (Tirupati, Madanapalle, Chittoor, Pileru, Srikalahasti, Puttur, Palamaner)",
        "disclaimer": "Analysis demonstrates observational associations and empirical distributions, not causal relationships."
    }


def get_detailed_analysis(filters=None):
    """
    Computes cross-tabulations and aggregations across Year, Location, Vehicle, Time, and Weather.
    """
    df = load_dataframe(filters)
    if df.empty:
        return {}

    # 1. Year-wise Analysis
    year_group = df.groupby(["year", "severity"]).size().unstack(fill_value=0)
    for col in ["Minor", "Serious", "Fatal"]:
        if col not in year_group.columns:
            year_group[col] = 0
    year_group["Total"] = year_group["Minor"] + year_group["Serious"] + year_group["Fatal"]
    year_group["Fatality_Rate_Pct"] = (year_group["Fatal"] / year_group["Total"] * 100).round(1)
    year_summary = year_group.reset_index().to_dict(orient="records")

    # 2. Location-wise Analysis (Top regions)
    loc_group = df.groupby(["region", "severity"]).size().unstack(fill_value=0)
    for col in ["Minor", "Serious", "Fatal"]:
        if col not in loc_group.columns:
            loc_group[col] = 0
    loc_group["Total"] = loc_group["Minor"] + loc_group["Serious"] + loc_group["Fatal"]
    loc_group = loc_group.sort_values(by="Total", ascending=False)
    loc_summary = loc_group.reset_index().to_dict(orient="records")

    # 3. Vehicle-wise Analysis
    veh_group = df.groupby(["vehicle_type", "severity"]).size().unstack(fill_value=0)
    for col in ["Minor", "Serious", "Fatal"]:
        if col not in veh_group.columns:
            veh_group[col] = 0
    veh_group["Total"] = veh_group["Minor"] + veh_group["Serious"] + veh_group["Fatal"]
    veh_group["Pct_Of_Total"] = (veh_group["Total"] / len(df) * 100).round(1)
    veh_summary = veh_group.sort_values(by="Total", ascending=False).reset_index().to_dict(orient="records")

    # 4. Time-of-Day Analysis
    tod_order = ["Morning (05:00 - 11:59)", "Afternoon (12:00 - 16:59)", "Evening (17:00 - 21:59)", "Night (22:00 - 04:59)"]
    tod_group = df.groupby("time_of_day").agg(
        Total=("accident_id", "count"),
        Fatal=("severity", lambda s: (s == "Fatal").sum()),
        Serious=("severity", lambda s: (s == "Serious").sum()),
        Minor=("severity", lambda s: (s == "Minor").sum())
    ).reindex(tod_order).fillna(0)
    tod_group["Pct_Of_Total"] = (tod_group["Total"] / len(df) * 100).round(1)
    tod_summary = tod_group.reset_index().to_dict(orient="records")

    # 5. Weather Severity Matrix
    weather_group = df.groupby(["weather", "severity"]).size().unstack(fill_value=0)
    for col in ["Minor", "Serious", "Fatal"]:
        if col not in weather_group.columns:
            weather_group[col] = 0
    weather_group["Total"] = weather_group["Minor"] + weather_group["Serious"] + weather_group["Fatal"]
    weather_summary = weather_group.sort_values(by="Total", ascending=False).reset_index().to_dict(orient="records")

    return {
        "yearly": year_summary,
        "locations": loc_summary,
        "vehicles": veh_summary,
        "time_of_day": tod_summary,
        "weather": weather_summary
    }


# ============================================================
# Matplotlib Visualization Engine
# ============================================================

def _apply_dark_style(fig, ax):
    """Applies modern slate styling to Matplotlib figures."""
    fig.patch.set_facecolor("#1E293B")  # Slate 800
    ax.set_facecolor("#0F172A")         # Slate 900
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#475569")
    ax.spines["bottom"].set_color("#475569")
    ax.tick_params(colors="#94A3B8", labelsize=9)
    ax.yaxis.label.set_color("#E2E8F0")
    ax.xaxis.label.set_color("#E2E8F0")
    ax.title.set_color("#F8FAFC")
    ax.grid(True, linestyle="--", alpha=0.25, color="#64748B")


def generate_chart_bytes(chart_type, filters=None):
    """
    Renders requested chart type using Matplotlib and returns raw PNG bytes.
    """
    df = load_dataframe(filters)
    
    # 1. Yearly & Severity Progression Chart
    if chart_type == "yearly_trend":
        fig, ax = plt.subplots(figsize=(8, 4.5), dpi=130)
        _apply_dark_style(fig, ax)

        if not df.empty:
            yearly = df.groupby(["year", "severity"]).size().unstack(fill_value=0)
            years = [str(y) for y in yearly.index]
            
            for sev in ["Minor", "Serious", "Fatal"]:
                if sev in yearly.columns:
                    ax.plot(
                        years,
                        yearly[sev],
                        marker="o",
                        linewidth=2.5,
                        markersize=6,
                        label=sev,
                        color=SEVERITY_COLORS.get(sev, "#3B82F6")
                    )

            ax.set_title("Yearly Accident Trends by Severity Level", fontsize=12, fontweight="bold", pad=12)
            ax.set_xlabel("Year", fontsize=10, labelpad=8)
            ax.set_ylabel("Number of Accidents", fontsize=10, labelpad=8)
            ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))
            ax.legend(facecolor="#1E293B", edgecolor="#475569", labelcolor="#F8FAFC", fontsize=9)
        else:
            ax.text(0.5, 0.5, "No Data Available", color="#94A3B8", ha="center", va="center")

    # 2. Severity Breakdown Donut Chart
    elif chart_type == "severity_donut":
        fig, ax = plt.subplots(figsize=(6, 4.5), dpi=130)
        fig.patch.set_facecolor("#1E293B")
        ax.set_facecolor("#1E293B")

        if not df.empty:
            sev_counts = df["severity"].value_counts()
            labels = sev_counts.index.tolist()
            sizes = sev_counts.values.tolist()
            colors = [SEVERITY_COLORS.get(s, "#3B82F6") for s in labels]

            wedges, texts, autotexts = ax.pie(
                sizes,
                labels=labels,
                autopct="%1.1f%%",
                startangle=140,
                colors=colors,
                textprops=dict(color="#F8FAFC", fontsize=9, fontweight="bold"),
                wedgeprops=dict(width=0.42, edgecolor="#1E293B", linewidth=2.5),
                pctdistance=0.78
            )
            for autotext in autotexts:
                autotext.set_color("#FFFFFF")
                autotext.set_fontsize(9)

            ax.set_title("Accident Severity Proportion", fontsize=12, fontweight="bold", color="#F8FAFC", pad=12)
        else:
            ax.text(0.5, 0.5, "No Data Available", color="#94A3B8", ha="center", va="center")

    # 3. Vehicle Type vs Severity Grouped Bar Chart
    elif chart_type == "vehicle_severity":
        fig, ax = plt.subplots(figsize=(9, 4.8), dpi=130)
        _apply_dark_style(fig, ax)

        if not df.empty:
            veh_sev = df.groupby(["vehicle_type", "severity"]).size().unstack(fill_value=0)
            vehicles = veh_sev.index.tolist()
            x = np.arange(len(vehicles))
            width = 0.25

            for i, sev in enumerate(["Minor", "Serious", "Fatal"]):
                vals = veh_sev[sev].values if sev in veh_sev.columns else [0] * len(vehicles)
                ax.bar(
                    x + (i - 1) * width,
                    vals,
                    width,
                    label=sev,
                    color=SEVERITY_COLORS.get(sev, "#3B82F6"),
                    edgecolor="#0F172A",
                    linewidth=1
                )

            ax.set_title("Vehicle Type vs Accident Severity Breakdown", fontsize=12, fontweight="bold", pad=12)
            ax.set_xlabel("Vehicle Classification", fontsize=10, labelpad=8)
            ax.set_ylabel("Accident Count", fontsize=10, labelpad=8)
            ax.set_xticks(x)
            ax.set_xticklabels(vehicles, rotation=15, ha="right")
            ax.legend(facecolor="#1E293B", edgecolor="#475569", labelcolor="#F8FAFC", fontsize=9)
            ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))
        else:
            ax.text(0.5, 0.5, "No Data Available", color="#94A3B8", ha="center", va="center")

    # 4. Hourly Risk Profile
    elif chart_type == "hourly_distribution":
        fig, ax = plt.subplots(figsize=(9, 4.5), dpi=130)
        _apply_dark_style(fig, ax)

        if not df.empty:
            hour_counts = df["hour"].value_counts().reindex(range(24), fill_value=0)
            hours = [f"{h:02d}:00" for h in range(24)]
            ax.bar(
                range(24),
                hour_counts.values,
                color="#06B6D4",
                edgecolor="#0891B2",
                linewidth=1,
                alpha=0.85
            )
            ax.plot(
                range(24),
                hour_counts.values,
                color="#F59E0B",
                linewidth=2,
                marker="o",
                markersize=4
            )
            ax.set_title("24-Hour Accident Distribution (Diurnal Risk Pattern)", fontsize=12, fontweight="bold", pad=12)
            ax.set_xlabel("Hour of the Day", fontsize=10, labelpad=8)
            ax.set_ylabel("Total Recorded Accidents", fontsize=10, labelpad=8)
            ax.set_xticks(range(0, 24, 2))
            ax.set_xticklabels([f"{h:02d}:00" for h in range(0, 24, 2)], rotation=30)
            ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))
        else:
            ax.text(0.5, 0.5, "No Data Available", color="#94A3B8", ha="center", va="center")

    # 5. Top Regional Corridors (Horizontal Bar)
    elif chart_type == "regional_ranking":
        fig, ax = plt.subplots(figsize=(9, 5), dpi=130)
        _apply_dark_style(fig, ax)

        if not df.empty:
            reg_counts = df["region"].value_counts().head(7).iloc[::-1]
            y_pos = np.arange(len(reg_counts))
            
            bars = ax.barh(
                y_pos,
                reg_counts.values,
                color="#3B82F6",
                edgecolor="#2563EB",
                height=0.65
            )
            ax.set_yticks(y_pos)
            ax.set_yticklabels(reg_counts.index, fontsize=9)
            ax.set_title("Top High-Risk Geographical Regions / Corridors", fontsize=12, fontweight="bold", pad=12)
            ax.set_xlabel("Number of Accidents", fontsize=10, labelpad=8)
            ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))

            # Add count labels on bars
            for bar in bars:
                w = bar.get_width()
                ax.text(w + 0.3, bar.get_y() + bar.get_height()/2, f"{int(w)}",
                        va="center", ha="left", color="#E2E8F0", fontsize=8, fontweight="bold")
        else:
            ax.text(0.5, 0.5, "No Data Available", color="#94A3B8", ha="center", va="center")

    # 6. Weather Condition Distribution
    elif chart_type == "weather_distribution":
        fig, ax = plt.subplots(figsize=(8, 4.5), dpi=130)
        _apply_dark_style(fig, ax)

        if not df.empty:
            weather_sev = df.groupby(["weather", "severity"]).size().unstack(fill_value=0)
            weathers = weather_sev.index.tolist()
            x = np.arange(len(weathers))
            width = 0.25

            for i, sev in enumerate(["Minor", "Serious", "Fatal"]):
                vals = weather_sev[sev].values if sev in weather_sev.columns else [0] * len(weathers)
                ax.bar(
                    x + (i - 1) * width,
                    vals,
                    width,
                    label=sev,
                    color=SEVERITY_COLORS.get(sev, "#3B82F6"),
                    edgecolor="#0F172A",
                    linewidth=1
                )

            ax.set_title("Weather Conditions vs Severity Breakdown", fontsize=12, fontweight="bold", pad=12)
            ax.set_xlabel("Weather Condition", fontsize=10, labelpad=8)
            ax.set_ylabel("Accident Count", fontsize=10, labelpad=8)
            ax.set_xticks(x)
            ax.set_xticklabels(weathers, rotation=15, ha="right")
            ax.legend(facecolor="#1E293B", edgecolor="#475569", labelcolor="#F8FAFC", fontsize=9)
            ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))
        else:
            ax.text(0.5, 0.5, "No Data Available", color="#94A3B8", ha="center", va="center")

    else:
        fig, ax = plt.subplots(figsize=(6, 3), dpi=130)
        _apply_dark_style(fig, ax)
        ax.text(0.5, 0.5, f"Unknown chart type: {chart_type}", color="#EF4444", ha="center", va="center")

    plt.tight_layout()
    img_buf = io.BytesIO()
    plt.savefig(img_buf, format="png", bbox_inches="tight", facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    img_buf.seek(0)
    return img_buf.getvalue()


def generate_text_summary_report(filters=None):
    """
    Generates a formal academic/statistical text summary report.
    """
    stats = get_summary_statistics(filters)
    details = get_detailed_analysis(filters)

    lines = []
    lines.append("=" * 72)
    lines.append("       ROAD ACCIDENT DATA ANALYSIS SYSTEM - ANALYTICAL SUMMARY REPORT")
    lines.append("=" * 72)
    lines.append(f"Generated On: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Dataset Provenance: {stats.get('dataset_source', 'Synthetic Dataset')}")
    lines.append(f"Geographic Granularity: {stats.get('location_granularity', 'Corridor Level')}")
    lines.append("-" * 72)
    lines.append("IMPORTANT STATISTICAL & ETHICAL DISCLAIMER:")
    lines.append("Analysis demonstrates observational associations and empirical distributions,")
    lines.append("NOT direct causal relationships. No personally identifying information (PII)")
    lines.append("is stored or analyzed.")
    lines.append("-" * 72)
    lines.append("\n[1] OVERALL KEY PERFORMANCE INDICATORS (KPIs):")
    lines.append(f" - Total Recorded Incidents:      {stats['total_accidents']}")
    lines.append(f" - Minor Incidents:               {stats['minor_count']} ({stats['minor_pct']}%)")
    lines.append(f" - Serious Injury Incidents:       {stats['serious_count']} ({stats['serious_pct']}%)")
    lines.append(f" - Fatal Incidents:                {stats['fatal_count']} ({stats['fatal_pct']}%)")
    lines.append(f" - Most Incident-Prone Vehicle:   {stats['most_common_vehicle']}")
    lines.append(f" - Highest Incident Corridor:     {stats['peak_risk_region']}")
    lines.append(f" - Peak Incident Diurnal Window:  {stats['peak_risk_hour']}")

    lines.append("\n[2] NUMPY DESCRIPTIVE STATISTICS (MONTHLY INCIDENT FREQUENCY):")
    lines.append(f" - Mean Incidents / Month:        {stats['mean_per_month']:.2f}")
    lines.append(f" - Median Incidents / Month:      {stats['median_per_month']:.2f}")
    lines.append(f" - Standard Deviation (sigma):    {stats['std_per_month']:.2f}")
    lines.append(f" - Interquartile Range (IQR):     {stats['iqr_per_month']:.2f}")

    if details.get("yearly"):
        lines.append("\n[3] YEAR-WISE LONGITUDINAL PROGRESSION:")
        lines.append(f" {'Year':<6} | {'Minor':<7} | {'Serious':<8} | {'Fatal':<6} | {'Total':<6} | {'Fatality Rate':<14}")
        lines.append(" " + "-" * 62)
        for y in details["yearly"]:
            lines.append(f" {y['year']:<6} | {y.get('Minor',0):<7} | {y.get('Serious',0):<8} | {y.get('Fatal',0):<6} | {y.get('Total',0):<6} | {y.get('Fatality_Rate_Pct',0):>5.1f}%")

    if details.get("vehicles"):
        lines.append("\n[4] VEHICLE CLASSIFICATION PROFILE:")
        lines.append(f" {'Vehicle Type':<14} | {'Minor':<7} | {'Serious':<8} | {'Fatal':<6} | {'Total':<6} | {'Share':<8}")
        lines.append(" " + "-" * 62)
        for v in details["vehicles"]:
            lines.append(f" {v['vehicle_type']:<14} | {v.get('Minor',0):<7} | {v.get('Serious',0):<8} | {v.get('Fatal',0):<6} | {v.get('Total',0):<6} | {v.get('Pct_Of_Total',0):>5.1f}%")

    if details.get("time_of_day"):
        lines.append("\n[5] DIURNAL / TIME-OF-DAY INCIDENT BREAKDOWN:")
        lines.append(f" {'Time Interval':<28} | {'Total':<6} | {'Fatal':<6} | {'Share':<8}")
        lines.append(" " + "-" * 56)
        for t in details["time_of_day"]:
            lines.append(f" {t['time_of_day']:<28} | {t.get('Total',0):<6} | {t.get('Fatal',0):<6} | {t.get('Pct_Of_Total',0):>5.1f}%")

    lines.append("\n" + "=" * 72)
    lines.append("                      END OF ANALYTICAL REPORT")
    lines.append("=" * 72)
    return "\n".join(lines)
