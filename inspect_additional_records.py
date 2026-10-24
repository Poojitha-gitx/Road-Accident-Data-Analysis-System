"""
Read-Only Inspection Script
Inspects the additional accident records beyond the original 220 in accident_analysis_db.
Does NOT modify, delete, or reset any records.
"""

import database

def inspect():
    database.check_and_set_driver()
    status = database.get_db_status()
    print("=" * 80)
    print(" ACCIDENT_ANALYSIS_DB - DATABASE AUDIT REPORT")
    print("=" * 80)
    print(f" Database Driver: {status['driver'].upper()}")
    print(f" Database Name:   {status['db_name']}")

    total_row = database.execute_query("SELECT COUNT(*) as cnt FROM accidents", fetch="one")
    total_count = total_row["cnt"] if total_row else 0
    print(f" Total Accidents in DB: {total_count}")

    # Query all records with accident_id > 220
    query = """
    SELECT 
        a.accident_id,
        a.accident_datetime,
        a.vehicle_type,
        a.severity,
        a.weather,
        a.created_at,
        l.location_id,
        l.region,
        l.road_name
    FROM accidents a
    JOIN locations l ON a.location_id = l.location_id
    WHERE a.accident_id > 220
    ORDER BY a.accident_id ASC
    """
    extra_records = database.execute_query(query, fetch="all")

    print(f"\n Found {len(extra_records)} record(s) beyond ID #220:")
    print("-" * 80)
    print(f" {'ID':<6} | {'Date & Time':<19} | {'Region / Road Name':<32} | {'Vehicle':<8} | {'Severity':<8} | {'Created At':<19}")
    print("-" * 80)

    for r in extra_records:
        loc = f"{r['region']} ({r['road_name'] or 'N/A'})"
        dt_str = str(r['accident_datetime'])[:19]
        created_str = str(r.get('created_at', 'N/A'))[:19]
        print(f" #{r['accident_id']:<5} | {dt_str:<19} | {loc:<32} | {r['vehicle_type']:<8} | {r['severity']:<8} | {created_str:<19}")

    print("=" * 80)

if __name__ == "__main__":
    inspect()
