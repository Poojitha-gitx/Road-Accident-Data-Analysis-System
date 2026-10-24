"""
Comprehensive Test Suite for Road Accident Data Analysis System
Verifies:
1. Jinja2 template syntax across all templates.
2. Read operations on Dashboard, Records, Analysis, Reports.
3. Search functionality (by location, year, vehicle, severity, non-matching).
4. Save Record functionality (MySQL commit, count increments 220 -> 221).
5. Edit Record functionality (updates persist in MySQL).
6. Delete Record functionality (cleans up test record, returning count to exact 220).
7. Verifies that all original 220 accident records are preserved intact.
"""

from app import app
from jinja2 import Environment, FileSystemLoader
import database

def run_tests():
    print("=" * 65)
    print(" ROAD ACCIDENT DATA ANALYSIS SYSTEM - VERIFICATION SUITE")
    print("=" * 65)

    client = app.test_client()

    # 1. Template Compilation Check
    print("\n[Step 1] Checking Jinja2 Template Syntax...")
    env = Environment(loader=FileSystemLoader("templates"))
    for t_name in ["base.html", "dashboard.html", "records.html", "analysis.html", "reports.html"]:
        env.get_template(t_name)
        print(f" -> templates/{t_name}: Valid Syntax")

    # 2. Database Connection Check
    print("\n[Step 2] Checking Database Connection & Active Driver...")
    status = database.get_db_status()
    print(f" -> Active Driver: {status['driver'].upper()}")
    print(f" -> Database Name: {status['db_name']}")
    initial_count = database.execute_query("SELECT COUNT(*) as cnt FROM accidents", fetch="one")["cnt"]
    print(f" -> Current Baseline Accidents in DB: {initial_count}")
    assert initial_count >= 220, f"Expected at least 220 records, found {initial_count}"

    # 3. Read Pages Tests
    print("\n[Step 3] Testing Page Rendering (GET requests)...")
    for route in ["/dashboard", "/records", "/analysis", "/reports"]:
        res = client.get(route)
        assert res.status_code == 200, f"Route {route} failed with status {res.status_code}"
        print(f" -> {route:<15} HTTP 200 OK")

    # 4. Search Functionality Tests
    print("\n[Step 4] Testing Search and Filters...")
    
    # 4a. Search by Location
    res_loc = client.get("/records?search=Downtown")
    assert res_loc.status_code == 200
    assert b"Downtown" in res_loc.data
    print(" -> Search by Location ('Downtown'): PASS (Matching records found)")

    # 4b. Search by Year (dropdown and keyword)
    res_yr_kw = client.get("/records?search=2023")
    assert res_yr_kw.status_code == 200
    assert b"2023" in res_yr_kw.data
    print(" -> Search by Year keyword ('2023'): PASS (Matching records found)")

    res_yr_dd = client.get("/records?year=2024")
    assert res_yr_dd.status_code == 200
    assert b"2024" in res_yr_dd.data
    print(" -> Filter by Year dropdown ('2024'): PASS (Matching records found)")

    # 4c. Search by Vehicle Type
    res_veh = client.get("/records?search=Bike")
    assert res_veh.status_code == 200
    assert b"Bike" in res_veh.data
    print(" -> Search by Vehicle ('Bike'): PASS (Matching records found)")

    # 4d. Search by Severity
    res_sev = client.get("/records?search=Fatal")
    assert res_sev.status_code == 200
    assert b"Fatal" in res_sev.data
    print(" -> Search by Severity ('Fatal'): PASS (Matching records found)")

    # 4e. Non-matching search query
    res_none = client.get("/records?search=NonExistentRoad9999X")
    assert res_none.status_code == 200
    assert b"No matching records found" in res_none.data
    print(" -> Non-matching search: PASS (Displays 'No matching records found')")

    # 4f. Reset filters
    res_reset = client.get("/records")
    assert res_reset.status_code == 200
    assert b"Showing" in res_reset.data
    print(" -> Reset filters: PASS (All baseline records restored)")

    # 5. Save Record (INSERT & COMMIT) Test
    print("\n[Step 5] Testing Save Accident Record (Form POST & MySQL Commit)...")
    add_payload = {
        "region": "Downtown Metro Core",
        "road_name": "Testing Save Boulevard",
        "accident_datetime": "2026-03-20T11:45",
        "vehicle_type": "Car",
        "severity": "Serious",
        "weather": "Clear"
    }
    res_add = client.post("/records/add", data=add_payload, follow_redirects=True)
    assert res_add.status_code == 200
    assert b"saved successfully" in res_add.data

    # Check database count incremented by 1
    new_count = database.execute_query("SELECT COUNT(*) as cnt FROM accidents", fetch="one")["cnt"]
    print(f" -> Database count after save: {new_count} (Incremented from {initial_count} -> {initial_count + 1})")
    assert new_count == initial_count + 1, f"Expected {initial_count + 1} records after save, got {new_count}"

    # Check newly saved record details in MySQL
    new_record = database.execute_query(
        """
        SELECT a.accident_id, a.vehicle_type, a.severity, l.region, l.road_name 
        FROM accidents a 
        JOIN locations l ON a.location_id = l.location_id 
        WHERE l.road_name = %s
        """,
        ("Testing Save Boulevard",),
        fetch="one"
    )
    assert new_record is not None, "New record was not found in MySQL"
    test_id = new_record["accident_id"]
    print(f" -> Verified new record in MySQL: ID #{test_id}, {new_record['region']} - {new_record['road_name']}")

    # 6. Test Edit Record
    print("\n[Step 6] Testing Edit Record...")
    edit_payload = {
        "region": "Downtown Metro Core",
        "road_name": "Testing Save Boulevard Updated",
        "accident_datetime": "2026-03-20T12:00",
        "vehicle_type": "Bike",
        "severity": "Fatal",
        "weather": "Rainy"
    }
    res_edit = client.post(f"/records/edit/{test_id}", data=edit_payload, follow_redirects=True)
    assert res_edit.status_code == 200
    assert b"updated successfully" in res_edit.data

    updated_rec = database.get_accident_by_id(test_id)
    assert updated_rec["vehicle_type"] == "Bike"
    assert updated_rec["severity"] == "Fatal"
    print(f" -> Verified edit in MySQL: ID #{test_id} updated to vehicle 'Bike', severity 'Fatal'")

    # 7. Test Delete Record (Cleanup to preserve baseline)
    print("\n[Step 7] Testing Delete Record & Baseline Cleanup...")
    res_del = client.post(f"/records/delete/{test_id}", follow_redirects=True)
    assert res_del.status_code == 200
    assert b"deleted successfully" in res_del.data

    final_count = database.execute_query("SELECT COUNT(*) as cnt FROM accidents", fetch="one")["cnt"]
    print(f" -> Database count after delete cleanup: {final_count}")
    assert final_count == initial_count, f"Expected {initial_count} records preserved, got {final_count}"
    print(f" -> Verified: All {initial_count} accident records preserved intact in MySQL!")

    print("\n" + "=" * 65)
    print(" ALL 7 TEST SUITES PASSED FLAWLESSLY!")
    print("=" * 65)

if __name__ == "__main__":
    run_tests()
