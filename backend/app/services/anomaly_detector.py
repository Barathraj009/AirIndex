"""
AirIndex India — Surge & Fare Anomaly Detection Engine
======================================================
Identifies price gouging, festival surges, weather disruptions,
and sudden route monopoly pricing anomalies across observed domestic fares.
"""

from __future__ import annotations

from typing import List, Dict
import pandas as pd
import numpy as np


def detect_fare_anomalies(df: pd.DataFrame) -> List[Dict]:
    """
    Scans valid fare observations for statistical price spikes and anomalies.
    """
    if df.empty or "total_fare" not in df.columns:
        return []

    valid_df = df[df["data_quality_status"] == "VALID"].copy()
    if len(valid_df) < 5:
        return []

    anomalies = []

    # 1. Route-level surge detection (fares exceeding route median + 2.5 * MAD)
    for (origin, dest), group in valid_df.groupby(["origin", "destination"]):
        if len(group) < 4:
            continue

        median_fare = float(group["total_fare"].median())
        mad = float(np.median(np.abs(group["total_fare"] - median_fare)))
        threshold = median_fare + max(2.5 * (mad if mad > 0 else median_fare * 0.2), 2000.0)

        spikes = group[group["total_fare"] > threshold]
        for _, row in spikes.head(3).iterrows():
            fare = float(row["total_fare"])
            deviation_pct = round(((fare - median_fare) / median_fare) * 100, 1)
            severity = "HIGH" if deviation_pct > 80 else ("MEDIUM" if deviation_pct > 40 else "LOW")

            anomalies.append({
                "route": f"{origin}-{dest}",
                "origin": origin,
                "destination": dest,
                "airline": row.get("airline", "Unknown"),
                "travel_date": str(row.get("travel_date", "")),
                "booking_window_days": int(row.get("booking_window_days", 0)) if pd.notna(row.get("booking_window_days")) else None,
                "observed_fare": round(fare, 2),
                "route_median_fare": round(median_fare, 2),
                "deviation_pct": deviation_pct,
                "anomaly_type": "SURGE_SPIKE",
                "severity": severity,
                "description": f"Fare is {deviation_pct}% above route median (₹{fare:,.0f} vs ₹{median_fare:,.0f})",
            })

    # 2. Last-minute gouging detection (T+1 fare > 2.2x T+30 median)
    for (origin, dest), group in valid_df.groupby(["origin", "destination"]):
        t1_fares = group[group["booking_window_days"] == 1]["total_fare"]
        t30_fares = group[group["booking_window_days"] == 30]["total_fare"]

        if not t1_fares.empty and not t30_fares.empty:
            t1_median = float(t1_fares.median())
            t30_median = float(t30_fares.median())
            if t30_median > 0 and t1_median > 2.2 * t30_median:
                markup_pct = round(((t1_median - t30_median) / t30_median) * 100, 1)
                anomalies.append({
                    "route": f"{origin}-{dest}",
                    "origin": origin,
                    "destination": dest,
                    "airline": "All Carriers",
                    "travel_date": "Next 24-48 Hours",
                    "booking_window_days": 1,
                    "observed_fare": round(t1_median, 2),
                    "route_median_fare": round(t30_median, 2),
                    "deviation_pct": markup_pct,
                    "anomaly_type": "LAST_MINUTE_GOUGING",
                    "severity": "HIGH" if markup_pct > 150 else "MEDIUM",
                    "description": f"Severe last-minute markup of +{markup_pct}% on T+1 departures vs advance booking",
                })

    # Sort anomalies by severity and deviation percentage
    severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    anomalies.sort(key=lambda x: (severity_order.get(x["severity"], 3), -x["deviation_pct"]))

    return anomalies[:25]
