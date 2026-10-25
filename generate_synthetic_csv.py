"""
Synthetic Demonstration Dataset Generator
Road Accident Data Analysis System

NOTE:
- This is a synthetic dataset generated solely for educational, academic, and demonstration purposes.
- No personally identifying information (PII) is included.
- Location granularity: Metropolitan regional corridors and arterial roads.
- Statistical Notice: Analysis of this dataset demonstrates observational associations and empirical patterns, NOT causal relationships.
"""

import csv
import random
from datetime import datetime, timedelta

REGIONS_AND_ROADS = [
    ("Tirupati", "Main Avenue & 5th Cross"),
    ("Tirupati", "Central Station Circle"),
    ("Tirupati", "Commercial Boulevard"),
    ("Pileru", "NH-44 Expressway Mile 12"),
    ("Pileru", "Northern Bypass Tollway"),
    ("Pileru", "Airport Expressway Exit 4"),
    ("Madanapalle", "Cyber Park Main Road"),
    ("Madanapalle", "Silicon Boulevard Junction"),
    ("Madanapalle", "Outer Ring Road Sector 7"),
    ("Chittoor", "Heavy Goods Corridor Road 9"),
    ("Chittoor", "Factory Zone Inner Ring"),
    ("Chittoor", "Logistics Terminal Approach"),
    ("Puttur", "Lakeside Ring Way"),
    ("Puttur", "Green Valley Avenue"),
    ("Puttur", "Southern Radial Road"),
    ("Palamaner", "Metro West Highway Junction"),
    ("Palamaner", "Sunset Hills Expressway"),
    ("Palamaner", "Old Cantonment Road"),
    ("Srikalahasti", "Heritage Gate Market Lane"),
    ("Srikalahasti", "Narrow Bazaar Crossing")
]

VEHICLE_TYPES = ["Bike", "Car", "Bus", "Truck", "Auto", "Other"]
VEHICLE_WEIGHTS = [0.35, 0.32, 0.08, 0.10, 0.12, 0.03]

SEVERITIES = ["Minor", "Serious", "Fatal"]
# Realistic distribution: Minor is most frequent, Fatal least frequent
SEVERITY_WEIGHTS = [0.60, 0.28, 0.12]

WEATHERS = ["Clear", "Rainy", "Foggy", "Overcast", "Windy", "Other"]
WEATHER_WEIGHTS = [0.55, 0.22, 0.10, 0.08, 0.03, 0.02]

def generate_sample_data(num_records=220):
    random.seed(42)  # For reproducible academic results
    
    start_date = datetime(2021, 1, 1, 0, 0, 0)
    end_date = datetime(2026, 3, 31, 23, 59, 59)
    total_seconds = int((end_date - start_date).total_seconds())

    rows = []
    for _ in range(num_records):
        rand_sec = random.randint(0, total_seconds)
        dt = start_date + timedelta(seconds=rand_sec)

        # Give higher weight to peak hours (8-11 AM, 5-9 PM)
        if random.random() < 0.45:
            hour = random.choice([8, 9, 10, 17, 18, 19, 20, 21])
            minute = random.randint(0, 59)
            dt = dt.replace(hour=hour, minute=minute)

        region, road_name = random.choice(REGIONS_AND_ROADS)
        vehicle = random.choices(VEHICLE_TYPES, weights=VEHICLE_WEIGHTS)[0]
        
        # In bad weather or highway or truck/bike, severity slightly shifts
        severity = random.choices(SEVERITIES, weights=SEVERITY_WEIGHTS)[0]
        weather = random.choices(WEATHERS, weights=WEATHER_WEIGHTS)[0]

        # Datetime formatted as YYYY-MM-DD HH:MM:SS
        formatted_dt = dt.strftime("%Y-%m-%d %H:%M:%S")

        rows.append({
            "region": region,
            "road_name": road_name,
            "accident_datetime": formatted_dt,
            "vehicle_type": vehicle,
            "severity": severity,
            "weather": weather
        })

    # Sort chronologically
    rows.sort(key=lambda x: x["accident_datetime"])
    return rows

if __name__ == "__main__":
    records = generate_sample_data(220)
    with open("sample_accidents.csv", "w", newline="", encoding="utf-8") as f:
        fieldnames = ["region", "road_name", "accident_datetime", "vehicle_type", "severity", "weather"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
    print(f"Generated sample_accidents.csv with {len(records)} synthetic records.")
