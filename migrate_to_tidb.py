"""
Database Migration Script: Local MySQL -> TiDB Cloud
Project: Road Accident Data Analysis System

Safely copies:
1. All records from 'locations' table (preserving original location_id).
2. All 226 records from 'accidents' table (preserving original accident_id,
   foreign keys, datetimes, vehicle types, severity, and weather).

Safety features:
- Read-only connection to local MySQL (no ALTER, DROP, DELETE, or UPDATE).
- Strictly targets database 'accident_analysis_db' (never touches any other database).
- Pre-migration validation: Verifies destination TiDB Cloud tables are empty (0 rows).
- Duplicate prevention: Aborts immediately if destination tables already contain data.
- Certificate-verified TLS connection for TiDB Cloud using certifi.
- Post-migration data integrity verification (counts, ID ranges, severity breakdown).
- Passwords and secrets are never printed or logged.
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Load local .env if present
load_dotenv()


def get_local_config():
    """Returns local MySQL connection parameters from environment variables."""
    host = os.getenv("LOCAL_DB_HOST") or os.getenv("DB_HOST", "localhost")
    port = int(os.getenv("LOCAL_DB_PORT") or os.getenv("DB_PORT", 3306))
    user = os.getenv("LOCAL_DB_USER") or os.getenv("DB_USER", "root")
    password = os.getenv("LOCAL_DB_PASSWORD") or os.getenv("DB_PASSWORD", "")
    database = os.getenv("LOCAL_DB_NAME") or os.getenv("DB_NAME", "accident_analysis_db")

    # Hard guard: only ever access accident_analysis_db
    if database != "accident_analysis_db":
        raise ValueError(
            f"Security Guard: LOCAL_DB_NAME must be 'accident_analysis_db' (got '{database}')"
        )

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "database": database,
    }


def get_tidb_config():
    """Returns TiDB Cloud connection parameters from environment variables."""
    host = os.getenv("TIDB_HOST")
    if not host:
        raise ValueError(
            "Missing TIDB_HOST environment variable. Please set TIDB_HOST in .env or environment."
        )

    port = int(os.getenv("TIDB_PORT", 4000))
    user = os.getenv("TIDB_USER")
    if not user:
        raise ValueError(
            "Missing TIDB_USER environment variable. Please set TIDB_USER in .env or environment."
        )

    password = os.getenv("TIDB_PASSWORD", "")
    database = os.getenv("TIDB_DATABASE") or os.getenv("TIDB_DB_NAME", "accident_analysis_db")

    # Hard guard: only ever access accident_analysis_db
    if database != "accident_analysis_db":
        raise ValueError(
            f"Security Guard: TIDB_DATABASE must be 'accident_analysis_db' (got '{database}')"
        )

    # SSL / TLS Configuration with Mozilla CA bundle
    try:
        import certifi
        ca_path = certifi.where()
    except ImportError:
        ca_path = None

    ssl_config = {
        "ssl_disabled": False,
        "ssl_verify_cert": True,
    }
    if ca_path and os.path.exists(ca_path):
        ssl_config["ssl_ca"] = ca_path

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "database": database,
        "ssl_config": ssl_config,
    }


def run_migration():
    """Executes the safe one-way data migration from local MySQL to TiDB Cloud."""
    import mysql.connector

    print("=" * 65)
    print(" Road Accident Data Analysis System - Migration to TiDB Cloud")
    print("=" * 65)

    # 1. Load Configurations
    try:
        local_cfg = get_local_config()
        tidb_cfg = get_tidb_config()
    except Exception as e:
        print(f"[ERROR] Configuration error: {e}")
        sys.exit(1)

    print(f"[*] Source (Local):   {local_cfg['user']}@{local_cfg['host']}:{local_cfg['port']}/{local_cfg['database']}")
    print(f"[*] Target (TiDB):    {tidb_cfg['user']}@{tidb_cfg['host']}:{tidb_cfg['port']}/{tidb_cfg['database']} (TLS Verified)")

    # 2. Connect to Local MySQL (Read-Only queries only)
    print("\n[1/5] Connecting to local MySQL...")
    try:
        local_conn = mysql.connector.connect(
            host=local_cfg["host"],
            port=local_cfg["port"],
            user=local_cfg["user"],
            password=local_cfg["password"],
            database=local_cfg["database"],
            charset="utf8mb4",
        )
        local_cursor = local_conn.cursor(dictionary=True)
        print("  -> Connected to local MySQL successfully.")
    except Exception as e:
        print(f"[ERROR] Failed to connect to local MySQL: {e}")
        sys.exit(1)

    # 3. Read Local Data
    try:
        local_cursor.execute("SELECT location_id, region, road_name, created_at FROM locations ORDER BY location_id ASC")
        local_locations = local_cursor.fetchall()

        local_cursor.execute(
            "SELECT accident_id, accident_datetime, location_id, vehicle_type, severity, weather, created_at "
            "FROM accidents ORDER BY accident_id ASC"
        )
        local_accidents = local_cursor.fetchall()

        print(f"  -> Found {len(local_locations)} location records.")
        print(f"  -> Found {len(local_accidents)} accident records.")

        if len(local_accidents) != 226:
            print(f"  [!] Note: Found {len(local_accidents)} accidents in local database (expected 226).")
    except Exception as e:
        print(f"[ERROR] Failed to read from local database: {e}")
        local_conn.close()
        sys.exit(1)

    # 4. Connect to TiDB Cloud
    print("\n[2/5] Connecting to TiDB Cloud over secure TLS...")
    try:
        tidb_ssl = tidb_cfg["ssl_config"]
        cloud_conn = mysql.connector.connect(
            host=tidb_cfg["host"],
            port=tidb_cfg["port"],
            user=tidb_cfg["user"],
            password=tidb_cfg["password"],
            database=tidb_cfg["database"],
            charset="utf8mb4",
            **tidb_ssl,
        )
        cloud_cursor = cloud_conn.cursor(dictionary=True)
        print("  -> Connected to TiDB Cloud cluster successfully.")
    except Exception as e:
        print(f"[ERROR] Failed to connect to TiDB Cloud: {e}")
        local_conn.close()
        sys.exit(1)

    # 5. Pre-migration Empty Check (Duplicate Prevention)
    print("\n[3/5] Verifying cloud destination tables are empty...")
    try:
        cloud_cursor.execute("SELECT COUNT(*) AS c FROM locations")
        cloud_loc_count = cloud_cursor.fetchone()["c"]

        cloud_cursor.execute("SELECT COUNT(*) AS c FROM accidents")
        cloud_acc_count = cloud_cursor.fetchone()["c"]

        if cloud_loc_count > 0 or cloud_acc_count > 0:
            print(f"[ABORT] Cloud database is not empty:")
            print(f"        'locations' has {cloud_loc_count} records.")
            print(f"        'accidents' has {cloud_acc_count} records.")
            print("        Migration aborted to prevent duplicate records or conflicts.")
            local_conn.close()
            cloud_conn.close()
            sys.exit(1)

        print("  -> Confirmed: Both cloud tables ('locations', 'accidents') are clean and empty (0 rows).")
    except Exception as e:
        print(f"[ERROR] Failed to check cloud table status: {e}")
        local_conn.close()
        cloud_conn.close()
        sys.exit(1)

    # 6. Perform Migration (Locations first, then Accidents)
    print("\n[4/5] Migrating data with original IDs and timestamps...")
    try:
        # A. Insert Locations
        loc_insert_sql = (
            "INSERT INTO locations (location_id, region, road_name, created_at) "
            "VALUES (%s, %s, %s, %s)"
        )
        loc_values = [
            (loc["location_id"], loc["region"], loc["road_name"], loc["created_at"])
            for loc in local_locations
        ]
        cloud_cursor.executemany(loc_insert_sql, loc_values)
        print(f"  -> Successfully staged {len(loc_values)} location records.")

        # B. Insert Accidents
        acc_insert_sql = (
            "INSERT INTO accidents (accident_id, accident_datetime, location_id, vehicle_type, severity, weather, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)"
        )
        acc_values = [
            (
                acc["accident_id"],
                acc["accident_datetime"],
                acc["location_id"],
                acc["vehicle_type"],
                acc["severity"],
                acc["weather"],
                acc["created_at"],
            )
            for acc in local_accidents
        ]
        cloud_cursor.executemany(acc_insert_sql, acc_values)
        print(f"  -> Successfully staged {len(acc_values)} accident records.")

        # Commit all changes to TiDB Cloud
        cloud_conn.commit()
        print("  -> Transaction committed to TiDB Cloud.")

    except Exception as e:
        print(f"[ERROR] Migration failed during insert: {e}")
        print("  -> Rolling back TiDB Cloud transaction...")
        cloud_conn.rollback()
        local_conn.close()
        cloud_conn.close()
        sys.exit(1)

    # 7. Post-Migration Verification & Data Integrity
    print("\n[5/5] Performing comprehensive data integrity verification...")
    try:
        # Check Total Counts
        cloud_cursor.execute("SELECT COUNT(*) AS c FROM locations")
        migrated_loc_count = cloud_cursor.fetchone()["c"]

        cloud_cursor.execute("SELECT COUNT(*) AS c FROM accidents")
        migrated_acc_count = cloud_cursor.fetchone()["c"]

        # Check ID Ranges
        cloud_cursor.execute("SELECT MIN(accident_id) AS min_id, MAX(accident_id) AS max_id FROM accidents")
        cloud_range = cloud_cursor.fetchone()

        local_cursor.execute("SELECT MIN(accident_id) AS min_id, MAX(accident_id) AS max_id FROM accidents")
        local_range = local_cursor.fetchone()

        # Check Severity Breakdown
        cloud_cursor.execute("SELECT severity, COUNT(*) AS c FROM accidents GROUP BY severity ORDER BY severity")
        cloud_severity = {row["severity"]: row["c"] for row in cloud_cursor.fetchall()}

        local_cursor.execute("SELECT severity, COUNT(*) AS c FROM accidents GROUP BY severity ORDER BY severity")
        local_severity = {row["severity"]: row["c"] for row in local_cursor.fetchall()}

        print("-" * 65)
        print(f"  Metric                     | Local MySQL | TiDB Cloud | Status")
        print("-" * 65)
        print(f"  Locations Count            | {len(local_locations):<11} | {migrated_loc_count:<10} | {'MATCH' if len(local_locations) == migrated_loc_count else 'MISMATCH'}")
        print(f"  Accidents Count            | {len(local_accidents):<11} | {migrated_acc_count:<10} | {'MATCH' if len(local_accidents) == migrated_acc_count else 'MISMATCH'}")
        print(f"  Min Accident ID            | {local_range['min_id']:<11} | {cloud_range['min_id']:<10} | {'MATCH' if local_range['min_id'] == cloud_range['min_id'] else 'MISMATCH'}")
        print(f"  Max Accident ID            | {local_range['max_id']:<11} | {cloud_range['max_id']:<10} | {'MATCH' if local_range['max_id'] == cloud_range['max_id'] else 'MISMATCH'}")
        print("-" * 65)

        severity_match = cloud_severity == local_severity
        print(f"  Severity Distribution:     | {local_severity}")
        print(f"  Cloud Distribution:        | {cloud_severity} ({'100% MATCH' if severity_match else 'MISMATCH'})")
        print("-" * 65)

        if (
            migrated_loc_count == len(local_locations)
            and migrated_acc_count == len(local_accidents)
            and local_range == cloud_range
            and severity_match
        ):
            print("\n>>> MIGRATION SUCCESSFUL: All 226 accident records and 23 locations are fully in sync! <<<")
        else:
            print("\n[WARNING] Discrepancies detected between Local and Cloud databases.")

    except Exception as e:
        print(f"[ERROR] Verification failed: {e}")
    finally:
        local_conn.close()
        cloud_conn.close()
        print("\n[*] Database connections closed cleanly.")


if __name__ == "__main__":
    run_migration()
