"""
Seed Synthetic Demonstration Data into Database
Road Accident Data Analysis System
"""

import csv
import os
import sys
from database import init_db, add_accident, execute_query, get_db_status

def seed_sample_accidents(csv_filepath="sample_accidents.csv", wipe_first=False):
    print("=" * 60)
    print(" ROAD ACCIDENT DATA ANALYSIS SYSTEM - DATABASE SEEDER ")
    print("=" * 60)
    init_db()
    status = get_db_status()
    print(f"Target Database Driver: {status['driver'].upper()}")
    print(f"Connection Status: {status['message']}")

    if not os.path.exists(csv_filepath):
        print(f"Error: {csv_filepath} not found!")
        return 0

    if wipe_first:
        print("Clearing existing data...")
        execute_query("DELETE FROM accidents")
        execute_query("DELETE FROM locations")
        print("Tables cleared.")

    # Check existing count
    existing_count = execute_query("SELECT COUNT(*) as cnt FROM accidents", fetch="one")["cnt"]
    if existing_count > 0 and not wipe_first:
        print(f"Database already contains {existing_count} records. Seeding new additional records from {csv_filepath}...")

    inserted = 0
    errors = 0
    with open(csv_filepath, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row_idx, row in enumerate(reader, start=1):
            try:
                add_accident(
                    accident_datetime_str=row["accident_datetime"].strip(),
                    region=row["region"].strip(),
                    road_name=row.get("road_name", "").strip(),
                    vehicle_type=row["vehicle_type"].strip(),
                    severity=row["severity"].strip(),
                    weather=row.get("weather", "Clear").strip()
                )
                inserted += 1
            except Exception as e:
                errors += 1
                if errors <= 3:
                    print(f"Row {row_idx} failed: {e}")

    total_accidents = execute_query("SELECT COUNT(*) as cnt FROM accidents", fetch="one")["cnt"]
    total_locations = execute_query("SELECT COUNT(*) as cnt FROM locations", fetch="one")["cnt"]

    print("-" * 60)
    print(f"Successfully seeded: {inserted} accident records.")
    if errors > 0:
        print(f"Errors encountered: {errors} rows skipped.")
    print(f"Current Total Accidents in DB: {total_accidents}")
    print(f"Current Total Unique Locations: {total_locations}")
    print("=" * 60)
    return inserted

if __name__ == "__main__":
    wipe = "--reset" in sys.argv or "-r" in sys.argv
    seed_sample_accidents(wipe_first=wipe)
