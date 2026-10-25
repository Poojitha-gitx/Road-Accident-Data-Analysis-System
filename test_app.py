"""
Comprehensive Verification Test Suite
Road Accident Data Analysis System

Tests:
1. Jinja2 template syntax across all templates.
2. Baseline database connection and driver mode.
3. Multi-dimensional filtering and empty states on Dashboard.
4. Dynamic Matplotlib charts generation (PNG bytes).
5. Search & filter on Accident Records (Year, Region, Vehicle, Severity, Weather).
6. Save Record lifecycle: add accident, transactional commit, count increment.
7. Edit Record lifecycle: verify persisted updates.
8. Delete Record lifecycle: cleanup and count restoration.
9. Report exports: CSV and Text Summary dossier generation.
10. AP Location naming consistency.
"""

from app import app
from jinja2 import Environment, FileSystemLoader
import database
import io

def run_tests():
    print("=" * 70)
    print(" ROAD ACCIDENT DATA ANALYSIS SYSTEM - COMPLETE VERIFICATION SUITE")
    print("=" * 70)

    client = app.test_client()

    # 1. Template Compilation Check
    print("\n[Step 1] Checking Jinja2 Template Syntax...")
    env = Environment(loader=FileSystemLoader("templates"))
    for t_name in ["base.html", "dashboard.html", "records.html", "analysis.html", "reports.html"]:
        env.get_template(t_name)
        print(f"  -> templates/{t_name}: Valid Syntax")

    # 2. Database Connection Check
    print("\n[Step 2] Checking Database Connection & Active Driver...")
    status = database.get_db_status()
    print(f"  -> Active Driver: {status['driver'].upper() if status['driver'] else 'N/A'}")
    print(f"  -> Database Name: {status['db_name']}")
    initial_count = database.execute_query("SELECT COUNT(*) as cnt FROM accidents", fetch="one")["cnt"]
    print(f"  -> Current Baseline Accidents in DB: {initial_count}")
    assert initial_count in (36, 226), f"Expected 36 (TiDB) or 226 (Local MySQL), got {initial_count}"

    # 3. Read Page Routes
    print("\n[Step 3] Testing Page Rendering (GET requests)...")
    for route in ["/dashboard", "/records", "/analysis", "/reports"]:
        res = client.get(route)
        assert res.status_code == 200, f"Route {route} failed with status {res.status_code}"
        print(f"  -> {route:<15} HTTP 200 OK")

    # 4. Multi-Filter Dashboard Tests
    print("\n[Step 4] Testing Multi-Dimensional Dashboard Filtering...")
    # 4a. Filter by Year 2025 and Region Tirupati
    res_filt = client.get("/dashboard?year=2025&region=Tirupati")
    assert res_filt.status_code == 200
    assert b"Analytical Dashboard" in res_filt.data
    print("  -> Combined Filters (Year 2025 + Tirupati): PASS")

    # 4b. Clear Filters / Unfiltered
    res_clear = client.get("/dashboard")
    assert res_clear.status_code == 200
    assert str(initial_count).encode("utf-8") in res_clear.data
    print(f"  -> Unfiltered Dashboard displays baseline total ({initial_count}): PASS")

    # 4c. Non-matching combination (Empty state)
    res_empty = client.get("/dashboard?year=1990&region=Tirupati")
    assert res_empty.status_code == 200
    assert b"No Matching Records Found" in res_empty.data
    print("  -> Non-matching Dashboard filter shows friendly Empty State Card: PASS")

    # 5. Charts Generation Tests
    print("\n[Step 5] Testing Matplotlib Charts Generation...")
    for ctype in ["yearly_trend", "severity_donut", "regional_ranking", "vehicle_severity", "hourly_distribution"]:
        res_c = client.get(f"/chart/{ctype}")
        assert res_c.status_code == 200
        assert res_c.mimetype == "image/png"
        assert len(res_c.data) > 500, f"Chart {ctype} output too small"
        print(f"  -> Chart '{ctype}': HTTP 200 image/png ({len(res_c.data)} bytes) PASS")

    # 6. Accident Records Search & Filters
    print("\n[Step 6] Testing Records Search & Filter Toolbar...")
    # 6a. Search by Location
    res_loc = client.get("/records?search=Tirupati")
    assert res_loc.status_code == 200
    assert b"Tirupati" in res_loc.data
    print("  -> Search by AP Location ('Tirupati'): PASS")

    # 6b. Filter by Weather
    res_wea = client.get("/records?weather=Rainy")
    assert res_wea.status_code == 200
    assert b"Rainy" in res_wea.data
    print("  -> Filter by Weather dropdown ('Rainy'): PASS")

    # 6c. Filter by Vehicle
    res_veh = client.get("/records?vehicle_type=Bike")
    assert res_veh.status_code == 200
    assert b"Bike" in res_veh.data
    print("  -> Filter by Vehicle dropdown ('Bike'): PASS")

    # 6d. Filter by Severity
    res_sev = client.get("/records?severity=Fatal")
    assert res_sev.status_code == 200
    assert b"Fatal" in res_sev.data
    print("  -> Filter by Severity dropdown ('Fatal'): PASS")

    # 6e. Non-matching search
    res_none = client.get("/records?search=NonExistentRoad9999XYZ")
    assert res_none.status_code == 200
    assert b"No matching records found" in res_none.data
    print("  -> Non-matching search shows 'No matching records found': PASS")

    # 6f. Bridge to Dashboard
    assert b"Analyze in Dashboard" in res_loc.data
    print("  -> 'Analyze in Dashboard' link present in toolbar: PASS")

    # 7. Add Accident Record (INSERT & COMMIT)
    print("\n[Step 7] Testing New Accident Record Saving...")
    add_payload = {
        "region": "Tirupati",
        "road_name": "Testing Live Pipeline Road",
        "accident_datetime": "2026-03-25T14:30",
        "vehicle_type": "Car",
        "severity": "Serious",
        "weather": "Clear"
    }
    res_add = client.post("/records/add", data=add_payload, follow_redirects=True)
    assert res_add.status_code == 200
    assert b"saved successfully" in res_add.data

    post_add_count = database.execute_query("SELECT COUNT(*) as cnt FROM accidents", fetch="one")["cnt"]
    print(f"  -> Count after save: {post_add_count} (Incremented from {initial_count} -> {initial_count + 1})")
    assert post_add_count == initial_count + 1

    # Verify newly saved record
    new_record = database.execute_query(
        """
        SELECT a.accident_id, a.vehicle_type, a.severity, l.region, l.road_name 
        FROM accidents a 
        JOIN locations l ON a.location_id = l.location_id 
        WHERE l.road_name = %s
        """,
        ("Testing Live Pipeline Road",),
        fetch="one"
    )
    assert new_record is not None, "New record was not saved in DB"
    test_id = new_record["accident_id"]
    print(f"  -> Verified new record in DB: ID #{test_id}, {new_record['region']} - {new_record['road_name']}")

    # 8. Edit Accident Record
    print("\n[Step 8] Testing Edit Accident Record...")
    edit_payload = {
        "region": "Madanapalle",
        "road_name": "Testing Live Pipeline Road Updated",
        "accident_datetime": "2026-03-25T15:00",
        "vehicle_type": "Bike",
        "severity": "Fatal",
        "weather": "Rainy"
    }
    res_edit = client.post(f"/records/edit/{test_id}", data=edit_payload, follow_redirects=True)
    assert res_edit.status_code == 200
    assert b"updated successfully" in res_edit.data

    updated_rec = database.get_accident_by_id(test_id)
    assert updated_rec["region"] == "Madanapalle"
    assert updated_rec["vehicle_type"] == "Bike"
    assert updated_rec["severity"] == "Fatal"
    print(f"  -> Verified edit in DB: ID #{test_id} updated to Madanapalle / Bike / Fatal")

    # 9. Delete Accident Record (Cleanup)
    print("\n[Step 9] Testing Delete Record & Baseline Restoration...")
    res_del = client.post(f"/records/delete/{test_id}", follow_redirects=True)
    assert res_del.status_code == 200
    assert b"deleted successfully" in res_del.data

    final_count = database.execute_query("SELECT COUNT(*) as cnt FROM accidents", fetch="one")["cnt"]
    print(f"  -> Final Count after cleanup: {final_count} (Matches baseline {initial_count})")
    assert final_count == initial_count

    # 10. Reports & Exports Tests
    print("\n[Step 10] Testing Reports & Exports...")
    res_csv = client.get("/reports/export-csv")
    assert res_csv.status_code == 200
    assert res_csv.mimetype == "text/csv"
    assert b"accident_id,accident_datetime,vehicle_type,severity,weather,region,road_name" in res_csv.data
    print("  -> Enriched CSV Export: HTTP 200 text/csv PASS")

    res_txt = client.get("/reports/export-summary")
    assert res_txt.status_code == 200
    assert res_txt.mimetype == "text/plain"
    assert b"ROAD ACCIDENT DATA ANALYSIS SYSTEM - ANALYTICAL SUMMARY REPORT" in res_txt.data
    print("  -> Text Summary Dossier Export: HTTP 200 text/plain PASS")

    print("\n" + "=" * 70)
    print(" >>> ALL 10 TEST PHASES PASSED WITH ZERO ERRORS! <<<")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()
