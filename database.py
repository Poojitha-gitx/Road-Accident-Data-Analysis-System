"""
Database Layer for Road Accident Data Analysis System
Supports MySQL with parameterized queries and seamless SQLite fallback.
"""

import os
import sqlite3
import secrets
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()

# Database Config from Environment Variables
is_render = bool(os.getenv("RENDER"))
tidb_host = os.getenv("TIDB_HOST", "").strip()
db_host_env = os.getenv("DB_HOST", "").strip()
has_remote_db = bool(tidb_host or (db_host_env and db_host_env.lower() not in ("localhost", "127.0.0.1", "")))

use_tidb = (os.getenv("USE_TIDB", "").lower() in ("true", "1", "yes")) or (is_render and bool(tidb_host))

# If running on Render without remote cloud DB credentials, immediately use SQLite mode to prevent hanging on localhost:3306
if is_render and not has_remote_db:
    DB_TYPE = "sqlite"
else:
    DB_TYPE = os.getenv("DB_TYPE", "mysql").lower()

if use_tidb and tidb_host:
    DB_HOST = tidb_host
    DB_PORT = int(os.getenv("TIDB_PORT", 4000))
    DB_USER = os.getenv("TIDB_USER", "root")
    DB_PASSWORD = os.getenv("TIDB_PASSWORD", "")
    DB_NAME = os.getenv("TIDB_DATABASE") or os.getenv("DB_NAME", "accident_analysis_db")
else:
    DB_HOST = db_host_env or tidb_host or "localhost"
    DB_PORT = int(os.getenv("DB_PORT") or os.getenv("TIDB_PORT", 3306))
    DB_USER = os.getenv("DB_USER") or os.getenv("TIDB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD") if os.getenv("DB_PASSWORD") is not None else os.getenv("TIDB_PASSWORD", "")
    DB_NAME = os.getenv("DB_NAME") or os.getenv("TIDB_DATABASE", "accident_analysis_db")

SQLITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "accident_analysis.db")

CURRENT_ACTIVE_DRIVER = None
CONNECTION_MESSAGE = ""
_MYSQL_TESTED = False


def get_mysql_ssl_config():
    """
    Returns SSL parameters for mysql.connector based on environment variables.
    Supports secure, certificate-verified TLS connections for TiDB Cloud / cloud databases
    while preserving standard unencrypted connections for local MySQL.
    """
    ssl_env = (os.getenv("TIDB_ENABLE_SSL") or os.getenv("DB_SSL", "")).strip().lower()
    is_cloud_db = (
        ssl_env in ("true", "1", "yes", "require")
        or DB_PORT == 4000
        or "tidbcloud" in DB_HOST.lower()
    )

    if not is_cloud_db:
        return {}

    ssl_config = {
        "ssl_disabled": False,
    }

    # Custom CA cert or certifi fallback for certificate-verified TLS
    custom_ca = os.getenv("DB_SSL_CA", "").strip()
    if custom_ca and os.path.exists(custom_ca):
        ssl_config["ssl_ca"] = custom_ca
        ssl_config["ssl_verify_cert"] = True
    else:
        try:
            import certifi
            ca_path = certifi.where()
            if os.path.exists(ca_path):
                ssl_config["ssl_ca"] = ca_path
                ssl_config["ssl_verify_cert"] = True
        except ImportError:
            ssl_config["ssl_verify_cert"] = False

    return ssl_config


def check_and_set_driver():
    """
    Tests MySQL connection once. If successful, sets CURRENT_ACTIVE_DRIVER to 'mysql'.
    Supports TiDB Cloud TLS connections and local MySQL instances.
    Otherwise falls back to 'sqlite' with fast failover.
    """
    global CURRENT_ACTIVE_DRIVER, CONNECTION_MESSAGE, _MYSQL_TESTED

    if _MYSQL_TESTED and CURRENT_ACTIVE_DRIVER:
        return CURRENT_ACTIVE_DRIVER

    if DB_TYPE == "mysql":
        try:
            import mysql.connector
            ssl_kwargs = get_mysql_ssl_config()

            # Attempt direct database connection with short 2s timeout
            try:
                test_conn = mysql.connector.connect(
                    host=DB_HOST,
                    port=DB_PORT,
                    user=DB_USER,
                    password=DB_PASSWORD,
                    database=DB_NAME,
                    connection_timeout=2,
                    **ssl_kwargs
                )
                test_conn.close()
            except mysql.connector.Error as err:
                # If error is 1049 (Unknown database) and running on local machine, create it
                if getattr(err, "errno", None) == 1049 and DB_HOST in ("localhost", "127.0.0.1"):
                    test_conn = mysql.connector.connect(
                        host=DB_HOST,
                        port=DB_PORT,
                        user=DB_USER,
                        password=DB_PASSWORD,
                        connection_timeout=2,
                        **ssl_kwargs
                    )
                    cursor = test_conn.cursor()
                    cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
                    cursor.close()
                    test_conn.close()
                else:
                    raise err

            CURRENT_ACTIVE_DRIVER = "mysql"
            ssl_note = " (TLS Verified)" if ssl_kwargs else ""
            CONNECTION_MESSAGE = f"Connected to MySQL on {DB_HOST}:{DB_PORT}{ssl_note} (Database: {DB_NAME})"
        except Exception as e:
            CURRENT_ACTIVE_DRIVER = "sqlite"
            CONNECTION_MESSAGE = f"MySQL notice: {e}. Operating in SQLite mode."
    else:
        CURRENT_ACTIVE_DRIVER = "sqlite"
        CONNECTION_MESSAGE = f"Operating in SQLite mode ({SQLITE_PATH})"

    _MYSQL_TESTED = True
    return CURRENT_ACTIVE_DRIVER


def get_db_connection():
    """
    Returns an active database connection and driver type ('mysql' or 'sqlite').
    Uses the cached active driver with TLS configuration if enabled.
    """
    driver = check_and_set_driver()

    if driver == "mysql":
        try:
            import mysql.connector
            ssl_kwargs = get_mysql_ssl_config()
            conn = mysql.connector.connect(
                host=DB_HOST,
                port=DB_PORT,
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_NAME,
                autocommit=True,
                connection_timeout=3,
                **ssl_kwargs
            )
            return conn, "mysql"
        except Exception:
            # Fall back to sqlite if unexpected runtime disconnect
            return get_sqlite_connection(), "sqlite"
    else:
        return get_sqlite_connection(), "sqlite"


def get_sqlite_connection():
    conn = sqlite3.connect(SQLITE_PATH, timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def get_db_status():
    return {
        "driver": CURRENT_ACTIVE_DRIVER,
        "message": CONNECTION_MESSAGE,
        "db_name": DB_NAME if CURRENT_ACTIVE_DRIVER == "mysql" else "accident_analysis.db",
        "host": DB_HOST if CURRENT_ACTIVE_DRIVER == "mysql" else "Local SQLite File",
        "user": DB_USER if CURRENT_ACTIVE_DRIVER == "mysql" else "Local OS"
    }


def execute_query(sql, params=None, fetch="all"):
    """
    Unified query runner with parameterized safety.
    Always use `%s` in the SQL string; it automatically converts to `?` for SQLite.
    """
    conn, driver = get_db_connection()
    params = params or ()

    is_mutating = sql.strip().upper().startswith(("INSERT", "UPDATE", "DELETE", "REPLACE"))

    if driver == "sqlite":
        # Convert %s placeholder to ? for SQLite parameterization
        sql_converted = sql.replace("%s", "?")
        cursor = conn.cursor()
        try:
            cursor.execute(sql_converted, params)
            if fetch == "all":
                result = [dict(row) for row in cursor.fetchall()]
            elif fetch == "one":
                row = cursor.fetchone()
                result = dict(row) if row else None
            elif fetch == "insert_id":
                result = cursor.lastrowid
                conn.commit()
            else:
                conn.commit()
                result = cursor.rowcount
            if is_mutating:
                conn.commit()
            return result
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            cursor.close()
            conn.close()
    else:
        # MySQL execution
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(sql, params)
            if fetch == "all":
                result = cursor.fetchall()
            elif fetch == "one":
                result = cursor.fetchone()
            elif fetch == "insert_id":
                result = cursor.lastrowid
                if not result:
                    cursor.execute("SELECT LAST_INSERT_ID() AS last_id")
                    last_row = cursor.fetchone()
                    if last_row and last_row.get("last_id"):
                        result = last_row["last_id"]
                conn.commit()
            else:
                conn.commit()
                result = cursor.rowcount
            if is_mutating:
                conn.commit()
            return result
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            cursor.close()
            conn.close()



def init_db():
    """
    Initializes tables for locations and accidents in MySQL or SQLite,
    and creates users and otp_verifications tables for role-based authentication.
    """
    conn, driver = get_db_connection()

    if driver == "mysql":
        cursor = conn.cursor()
        try:
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS locations (
                location_id INT AUTO_INCREMENT PRIMARY KEY,
                region VARCHAR(100) NOT NULL,
                road_name VARCHAR(150) NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_region (region),
                UNIQUE KEY uq_loc (region, road_name)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS accidents (
                accident_id INT AUTO_INCREMENT PRIMARY KEY,
                accident_datetime DATETIME NOT NULL,
                location_id INT NOT NULL,
                vehicle_type ENUM('Bike', 'Car', 'Bus', 'Truck', 'Auto', 'Other') NOT NULL,
                severity ENUM('Minor', 'Serious', 'Fatal') NOT NULL,
                weather ENUM('Clear', 'Rainy', 'Foggy', 'Overcast', 'Windy', 'Other') DEFAULT 'Clear',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES locations(location_id) ON DELETE RESTRICT ON UPDATE CASCADE,
                INDEX idx_datetime (accident_datetime),
                INDEX idx_severity (severity),
                INDEX idx_vehicle (vehicle_type)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INT AUTO_INCREMENT PRIMARY KEY,
                full_name VARCHAR(150) NOT NULL,
                email VARCHAR(191) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(20) NOT NULL DEFAULT 'user',
                is_active TINYINT(1) NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_user_email (email),
                INDEX idx_user_role (role)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS otp_verifications (
                otp_id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(191) NOT NULL,
                otp_hash VARCHAR(255) NOT NULL,
                purpose VARCHAR(50) NOT NULL,
                expires_at DATETIME NOT NULL,
                attempts INT NOT NULL DEFAULT 0,
                max_attempts INT NOT NULL DEFAULT 5,
                is_used TINYINT(1) NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_otp_email_purpose (email, purpose),
                INDEX idx_otp_expires (expires_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
        finally:
            cursor.close()
            conn.close()
    else:
        cursor = conn.cursor()
        try:
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS locations (
                location_id INTEGER PRIMARY KEY AUTOINCREMENT,
                region TEXT NOT NULL,
                road_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(region, road_name)
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS accidents (
                accident_id INTEGER PRIMARY KEY AUTOINCREMENT,
                accident_datetime TEXT NOT NULL,
                location_id INTEGER NOT NULL,
                vehicle_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                weather TEXT DEFAULT 'Clear',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES locations(location_id)
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            cursor.execute("""
            CREATE TABLE IF NOT EXISTS otp_verifications (
                otp_id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                otp_hash TEXT NOT NULL,
                purpose TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 5,
                is_used INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
            conn.commit()
        finally:
            cursor.close()
            conn.close()

    create_initial_admin()

    # Seed baseline records from sample_accidents.csv if database is newly initialized and empty
    try:
        cnt_row = execute_query("SELECT COUNT(*) as cnt FROM accidents", fetch="one")
        if not cnt_row or cnt_row.get("cnt", 0) == 0:
            csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_accidents.csv")
            if os.path.exists(csv_path):
                import csv as _csv
                with open(csv_path, mode="r", encoding="utf-8") as f:
                    reader = _csv.DictReader(f)
                    for row in reader:
                        try:
                            add_accident(
                                accident_datetime_str=row["accident_datetime"].strip(),
                                region=row["region"].strip(),
                                road_name=row.get("road_name", "").strip(),
                                vehicle_type=row["vehicle_type"].strip(),
                                severity=row["severity"].strip(),
                                weather=row.get("weather", "Clear").strip()
                            )
                        except Exception:
                            pass
    except Exception as e:
        print(f"Notice: Baseline data seeding skipped ({e})")


def create_initial_admin():
    """
    Creates the initial administrator account from environment variables if not present.
    Ensures secure credentials, avoids duplicates, and never allows public admin escalation.
    """
    admin_name = os.getenv("ADMIN_NAME", "System Administrator").strip()
    admin_email = os.getenv("ADMIN_EMAIL", "admin@example.com").strip().lower()
    admin_password = os.getenv("ADMIN_PASSWORD", "your_strong_admin_password").strip()

    if not admin_email or not admin_password:
        return

    try:
        existing = execute_query(
            "SELECT user_id, role, is_active FROM users WHERE LOWER(email) = LOWER(%s)",
            (admin_email,),
            fetch="one"
        )

        if not existing:
            pwd_hash = generate_password_hash(admin_password)
            execute_query(
                """
                INSERT INTO users (full_name, email, password_hash, role, is_active)
                VALUES (%s, %s, %s, 'admin', 1)
                """,
                (admin_name, admin_email, pwd_hash),
                fetch="insert_id"
            )
        else:
            if existing.get("role") != "admin" or not existing.get("is_active"):
                execute_query(
                    "UPDATE users SET role = 'admin', is_active = 1 WHERE user_id = %s",
                    (existing["user_id"],),
                    fetch="count"
                )
    except Exception as e:
        print(f"Notice: Initial admin bootstrap deferred ({e})")


# ============================================================
# CRUD Functions
# ============================================================

def get_or_create_location(region, road_name=""):
    """
    Gets existing location_id or inserts a new location record.
    Preserves existing location_id and respects unique constraints.
    """
    region = (region or "").strip()
    road_name = (road_name or "").strip()
    road_name_val = road_name if road_name else None

    # Search for existing with case-insensitive check
    if road_name_val:
        row = execute_query(
            "SELECT location_id FROM locations WHERE LOWER(region) = LOWER(%s) AND LOWER(road_name) = LOWER(%s)",
            (region, road_name_val),
            fetch="one"
        )
    else:
        row = execute_query(
            "SELECT location_id FROM locations WHERE LOWER(region) = LOWER(%s) AND (road_name IS NULL OR road_name = '')",
            (region,),
            fetch="one"
        )

    if row and row.get("location_id"):
        return row["location_id"]

    # Insert new with fallback in case of duplicate key
    try:
        loc_id = execute_query(
            "INSERT INTO locations (region, road_name) VALUES (%s, %s)",
            (region, road_name_val),
            fetch="insert_id"
        )
        if loc_id:
            return loc_id
    except Exception:
        pass

    if road_name_val:
        row = execute_query(
            "SELECT location_id FROM locations WHERE LOWER(region) = LOWER(%s) AND LOWER(road_name) = LOWER(%s)",
            (region, road_name_val),
            fetch="one"
        )
    else:
        row = execute_query(
            "SELECT location_id FROM locations WHERE LOWER(region) = LOWER(%s) AND (road_name IS NULL OR road_name = '')",
            (region,),
            fetch="one"
        )
    if row and row.get("location_id"):
        return row["location_id"]
    raise ValueError(f"Could not resolve or create location for '{region}' / '{road_name}'")


def add_accident(accident_datetime_str, region, road_name, vehicle_type, severity, weather="Clear"):
    loc_id = get_or_create_location(region, road_name)
    accident_id = execute_query(
        """
        INSERT INTO accidents (accident_datetime, location_id, vehicle_type, severity, weather)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (accident_datetime_str, loc_id, vehicle_type, severity, weather),
        fetch="insert_id"
    )
    clear_metadata_cache()
    return accident_id


def update_accident(accident_id, accident_datetime_str, region, road_name, vehicle_type, severity, weather="Clear"):
    loc_id = get_or_create_location(region, road_name)
    count = execute_query(
        """
        UPDATE accidents
        SET accident_datetime = %s, location_id = %s, vehicle_type = %s, severity = %s, weather = %s
        WHERE accident_id = %s
        """,
        (accident_datetime_str, loc_id, vehicle_type, severity, weather, accident_id),
        fetch="count"
    )
    clear_metadata_cache()
    return count > 0


def delete_accident(accident_id):
    count = execute_query(
        "DELETE FROM accidents WHERE accident_id = %s",
        (accident_id,),
        fetch="count"
    )
    clear_metadata_cache()
    return count > 0


def get_accident_by_id(accident_id):
    sql = """
    SELECT 
        a.accident_id,
        a.accident_datetime,
        a.vehicle_type,
        a.severity,
        a.weather,
        l.location_id,
        l.region,
        l.road_name
    FROM accidents a
    JOIN locations l ON a.location_id = l.location_id
    WHERE a.accident_id = %s
    """
    row = execute_query(sql, (accident_id,), fetch="one")
    if row:
        dt = row["accident_datetime"]
        if isinstance(dt, datetime):
            row["accident_datetime_str"] = dt.strftime("%Y-%m-%d %H:%M:%S")
            row["accident_year"] = dt.year
        else:
            row["accident_datetime_str"] = str(dt)
            try:
                row["accident_year"] = datetime.strptime(str(dt)[:19], "%Y-%m-%d %H:%M:%S").year
            except Exception:
                row["accident_year"] = str(dt)[:4]
    return row


def build_filter_conditions(filters, driver=None):
    """
    Builds parameterized SQL WHERE clause and parameter list from filter dict.
    Supports location, year, vehicle type, severity, weather, and keyword search.
    Case-insensitive across all categorical fields.
    """
    filters = filters or {}
    conditions = []
    params = []
    driver = driver or CURRENT_ACTIVE_DRIVER or check_and_set_driver()

    # 1. Year filter from dropdown
    if filters.get("year"):
        yr = str(filters["year"]).strip()
        if yr:
            if driver == "mysql":
                conditions.append("YEAR(a.accident_datetime) = %s")
                try:
                    params.append(int(yr))
                except ValueError:
                    params.append(yr)
            else:
                conditions.append("a.accident_datetime LIKE %s")
                params.append(f"{yr}%")

    # 2. Location Region filter (case-insensitive)
    if filters.get("region"):
        reg = str(filters["region"]).strip()
        if reg:
            conditions.append("LOWER(l.region) = LOWER(%s)")
            params.append(reg)

    # 3. Vehicle type filter (case-insensitive)
    if filters.get("vehicle_type"):
        veh = str(filters["vehicle_type"]).strip()
        if veh:
            conditions.append("LOWER(a.vehicle_type) = LOWER(%s)")
            params.append(veh)

    # 4. Severity filter (case-insensitive)
    if filters.get("severity"):
        sev = str(filters["severity"]).strip()
        if sev:
            conditions.append("LOWER(a.severity) = LOWER(%s)")
            params.append(sev)

    # 5. Weather filter (case-insensitive)
    if filters.get("weather"):
        wea = str(filters["weather"]).strip()
        if wea:
            conditions.append("LOWER(a.weather) = LOWER(%s)")
            params.append(wea)


    # 6. Keyword Search (accident location, year, vehicle type, severity, weather)
    if filters.get("search"):
        term = str(filters["search"]).strip()
        if term:
            search_param = f"%{term}%"
            if driver == "mysql":
                conditions.append("""(
                    l.region LIKE %s
                    OR l.road_name LIKE %s
                    OR a.vehicle_type LIKE %s
                    OR a.severity LIKE %s
                    OR a.weather LIKE %s
                    OR CAST(a.accident_datetime AS CHAR) LIKE %s
                    OR CAST(a.accident_id AS CHAR) LIKE %s
                )""")
            else:
                conditions.append("""(
                    l.region LIKE %s
                    OR l.road_name LIKE %s
                    OR a.vehicle_type LIKE %s
                    OR a.severity LIKE %s
                    OR a.weather LIKE %s
                    OR a.accident_datetime LIKE %s
                    OR CAST(a.accident_id AS TEXT) LIKE %s
                )""")
            params.extend([search_param, search_param, search_param, search_param, search_param, search_param, search_param])

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
    return where_clause, params


def get_accidents(filters=None, page=1, per_page=15, sort_by="accident_datetime", order="DESC"):
    filters = filters or {}
    driver = CURRENT_ACTIVE_DRIVER or check_and_set_driver()
    where_clause, params = build_filter_conditions(filters, driver)

    # Count total matching rows
    count_sql = f"""
    SELECT COUNT(*) as total 
    FROM accidents a 
    JOIN locations l ON a.location_id = l.location_id
    {where_clause}
    """
    count_row = execute_query(count_sql, tuple(params), fetch="one")
    total_count = count_row["total"] if count_row else 0

    # Sanitize order
    order_clean = "DESC" if str(order).upper() == "DESC" else "ASC"
    allowed_sort = {
        "accident_datetime": "a.accident_datetime",
        "accident_id": "a.accident_id",
        "severity": "a.severity",
        "vehicle_type": "a.vehicle_type",
        "region": "l.region"
    }
    sort_column = allowed_sort.get(sort_by, "a.accident_datetime")

    offset = (page - 1) * per_page
    data_sql = f"""
    SELECT 
        a.accident_id,
        a.accident_datetime,
        a.vehicle_type,
        a.severity,
        a.weather,
        l.location_id,
        l.region,
        l.road_name
    FROM accidents a
    JOIN locations l ON a.location_id = l.location_id
    {where_clause}
    ORDER BY {sort_column} {order_clean}
    LIMIT %s OFFSET %s
    """
    data_params = tuple(params + [per_page, offset])
    rows = execute_query(data_sql, data_params, fetch="all")

    for r in rows:
        dt = r["accident_datetime"]
        if isinstance(dt, datetime):
            r["accident_datetime_str"] = dt.strftime("%Y-%m-%d %H:%M")
            r["accident_year"] = dt.year
        else:
            r["accident_datetime_str"] = str(dt)[:16]
            try:
                r["accident_year"] = datetime.strptime(str(dt)[:19], "%Y-%m-%d %H:%M:%S").year
            except Exception:
                r["accident_year"] = str(dt)[:4]

    total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1

    return {
        "records": rows,
        "total_count": total_count,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages
    }


_CACHED_REGIONS = None
_CACHED_YEARS = None


def clear_metadata_cache():
    """Invalidates in-memory metadata caches after mutations."""
    global _CACHED_REGIONS, _CACHED_YEARS
    _CACHED_REGIONS = None
    _CACHED_YEARS = None


def get_all_regions():
    global _CACHED_REGIONS
    if _CACHED_REGIONS is not None:
        return _CACHED_REGIONS
    try:
        rows = execute_query("SELECT DISTINCT region FROM locations ORDER BY region ASC", fetch="all")
        _CACHED_REGIONS = [r["region"] for r in rows if r["region"]]
    except Exception:
        _CACHED_REGIONS = ["Tirupati", "Chittoor", "Madanapalle", "Pileru", "Srikalahasti", "Puttur", "Palamaner"]
    return _CACHED_REGIONS


def get_all_years():
    global _CACHED_YEARS
    if _CACHED_YEARS is not None:
        return _CACHED_YEARS
    try:
        driver = CURRENT_ACTIVE_DRIVER or check_and_set_driver()
        if driver == "mysql":
            rows = execute_query("SELECT DISTINCT YEAR(accident_datetime) as year FROM accidents WHERE accident_datetime IS NOT NULL ORDER BY year DESC", fetch="all")
        else:
            rows = execute_query("SELECT DISTINCT SUBSTR(accident_datetime, 1, 4) as year FROM accidents WHERE accident_datetime IS NOT NULL ORDER BY year DESC", fetch="all")
        _CACHED_YEARS = [str(r["year"]) for r in rows if r.get("year")]
    except Exception:
        _CACHED_YEARS = ["2026", "2025", "2024", "2023", "2022", "2021", "2020"]
    return _CACHED_YEARS


def get_raw_records_for_df(filters=None):
    """
    Pulls complete flat records into dictionaries for Pandas analysis.
    """
    filters = filters or {}
    driver = CURRENT_ACTIVE_DRIVER or check_and_set_driver()
    where_clause, params = build_filter_conditions(filters, driver)

    sql = f"""
    SELECT 
        a.accident_id,
        a.accident_datetime,
        a.vehicle_type,
        a.severity,
        a.weather,
        l.region,
        l.road_name
    FROM accidents a
    JOIN locations l ON a.location_id = l.location_id
    {where_clause}
    ORDER BY a.accident_datetime ASC
    """
    return execute_query(sql, tuple(params), fetch="all")


# ============================================================
# User Authentication & Role Management Layer
# ============================================================

def get_user_by_email(email):
    """Retrieves user record by case-insensitive email."""
    if not email:
        return None
    return execute_query(
        "SELECT * FROM users WHERE LOWER(email) = LOWER(%s)",
        (email.strip(),),
        fetch="one"
    )


def get_user_by_id(user_id):
    """Retrieves user record by user_id."""
    if not user_id:
        return None
    return execute_query(
        "SELECT * FROM users WHERE user_id = %s",
        (user_id,),
        fetch="one"
    )


def create_user(full_name, email, password_hash, role="user", is_active=1):
    """Creates a new registered user in the database."""
    return execute_query(
        """
        INSERT INTO users (full_name, email, password_hash, role, is_active)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (full_name.strip(), email.strip().lower(), password_hash, role, 1 if is_active else 0),
        fetch="insert_id"
    )


def update_user_password(user_id, password_hash):
    """Updates password hash for a given user_id."""
    count = execute_query(
        "UPDATE users SET password_hash = %s, updated_at = CURRENT_TIMESTAMP WHERE user_id = %s",
        (password_hash, user_id),
        fetch="count"
    )
    return count > 0


def update_user_profile(user_id, full_name):
    """Updates display name for user profile."""
    count = execute_query(
        "UPDATE users SET full_name = %s, updated_at = CURRENT_TIMESTAMP WHERE user_id = %s",
        (full_name.strip(), user_id),
        fetch="count"
    )
    return count > 0


def get_all_users():
    """Retrieves all registered users for administration."""
    return execute_query(
        "SELECT user_id, full_name, email, role, is_active, created_at, updated_at FROM users ORDER BY user_id ASC",
        fetch="all"
    )


def set_user_status(user_id, is_active):
    """Activates or deactivates a user account."""
    count = execute_query(
        "UPDATE users SET is_active = %s, updated_at = CURRENT_TIMESTAMP WHERE user_id = %s",
        (1 if is_active else 0, user_id),
        fetch="count"
    )
    return count > 0


def set_user_role(user_id, role):
    """Updates user authorization role ('user' or 'admin')."""
    if role not in ("user", "admin"):
        raise ValueError("Invalid role specified.")
    count = execute_query(
        "UPDATE users SET role = %s, updated_at = CURRENT_TIMESTAMP WHERE user_id = %s",
        (role, user_id),
        fetch="count"
    )
    return count > 0


# ============================================================
# OTP Verification Layer
# ============================================================

def generate_and_store_otp(email, purpose, expires_in_minutes=5):
    """
    Generates a secure 6-digit numeric OTP, hashes it, stores it in otp_verifications,
    and returns the plain OTP string for email dispatch.
    """
    email_clean = email.strip().lower()
    otp_code = f"{secrets.randbelow(900000) + 100000:06d}"
    otp_hash = generate_password_hash(otp_code)

    now_dt = datetime.now()
    now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
    expires_at = now_dt + timedelta(minutes=expires_in_minutes)
    expires_at_str = expires_at.strftime("%Y-%m-%d %H:%M:%S")

    # Invalidate previous unverified OTPs for this email & purpose
    execute_query(
        "UPDATE otp_verifications SET is_used = 1 WHERE LOWER(email) = LOWER(%s) AND purpose = %s AND is_used = 0",
        (email_clean, purpose),
        fetch="count"
    )

    execute_query(
        """
        INSERT INTO otp_verifications (email, otp_hash, purpose, expires_at, created_at, attempts, max_attempts, is_used)
        VALUES (%s, %s, %s, %s, %s, 0, 5, 0)
        """,
        (email_clean, otp_hash, purpose, expires_at_str, now_str),
        fetch="insert_id"
    )
    return otp_code


def check_otp_resend_cooldown(email, purpose, cooldown_seconds=60):
    """
    Checks if enough time has passed since the last OTP generation for this email and purpose.
    Returns (can_resend: bool, remaining_seconds: int).
    """
    email_clean = email.strip().lower()
    latest = execute_query(
        """
        SELECT created_at FROM otp_verifications
        WHERE LOWER(email) = LOWER(%s) AND purpose = %s
        ORDER BY otp_id DESC LIMIT 1
        """,
        (email_clean, purpose),
        fetch="one"
    )
    if not latest or not latest.get("created_at"):
        return True, 0

    c_at = latest["created_at"]
    if isinstance(c_at, str):
        try:
            c_at = datetime.strptime(c_at[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return True, 0

    elapsed = (datetime.now() - c_at).total_seconds()
    if elapsed < cooldown_seconds:
        return False, int(cooldown_seconds - elapsed)
    return True, 0


def verify_otp_attempt(email, entered_otp, purpose):
    """
    Verifies an entered OTP code against the latest active OTP record.
    Returns (success: bool, message: str).
    Handles attempt limiting, expiration, and one-time usage.
    """
    email_clean = email.strip().lower()
    entered_clean = (entered_otp or "").strip()

    latest = execute_query(
        """
        SELECT otp_id, otp_hash, expires_at, attempts, max_attempts, is_used
        FROM otp_verifications
        WHERE LOWER(email) = LOWER(%s) AND purpose = %s AND is_used = 0
        ORDER BY otp_id DESC LIMIT 1
        """,
        (email_clean, purpose),
        fetch="one"
    )

    if not latest:
        return False, "No active verification code found. Please request a new OTP."

    otp_id = latest["otp_id"]
    max_attempts = latest.get("max_attempts", 5)
    current_attempts = latest.get("attempts", 0)

    # Check attempt threshold
    if current_attempts >= max_attempts:
        execute_query(
            "UPDATE otp_verifications SET is_used = 1 WHERE otp_id = %s",
            (otp_id,),
            fetch="count"
        )
        return False, "Maximum incorrect verification attempts reached. Please request a new OTP."

    # Check expiration
    exp = latest["expires_at"]
    if isinstance(exp, str):
        try:
            exp = datetime.strptime(exp[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    if isinstance(exp, datetime) and datetime.now() > exp:
        execute_query(
            "UPDATE otp_verifications SET is_used = 1 WHERE otp_id = %s",
            (otp_id,),
            fetch="count"
        )
        return False, "Verification code has expired (valid for 5 minutes). Please request a new code."

    # Validate OTP code hash
    if check_password_hash(latest["otp_hash"], entered_clean):
        execute_query(
            "UPDATE otp_verifications SET is_used = 1 WHERE otp_id = %s",
            (otp_id,),
            fetch="count"
        )
        return True, "Verification successful."
    else:
        new_attempts = current_attempts + 1
        rem = max_attempts - new_attempts
        if rem <= 0:
            execute_query(
                "UPDATE otp_verifications SET attempts = %s, is_used = 1 WHERE otp_id = %s",
                (new_attempts, otp_id),
                fetch="count"
            )
            return False, "Incorrect verification code. Maximum attempts reached. Please request a new code."
        else:
            execute_query(
                "UPDATE otp_verifications SET attempts = %s WHERE otp_id = %s",
                (new_attempts, otp_id),
                fetch="count"
            )
            return False, f"Incorrect verification code. You have {rem} attempt(s) remaining."
