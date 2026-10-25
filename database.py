"""
Database Layer for Road Accident Data Analysis System
Supports MySQL with parameterized queries and seamless SQLite fallback.
"""

import os
import sqlite3
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Database Config from Environment Variables
use_tidb = (os.getenv("USE_TIDB", "").lower() in ("true", "1", "yes")) or (bool(os.getenv("RENDER")) and bool(os.getenv("TIDB_HOST")))

DB_TYPE = os.getenv("DB_TYPE", "mysql").lower()
if use_tidb and os.getenv("TIDB_HOST"):
    DB_HOST = os.getenv("TIDB_HOST")
    DB_PORT = int(os.getenv("TIDB_PORT", 4000))
    DB_USER = os.getenv("TIDB_USER", "root")
    DB_PASSWORD = os.getenv("TIDB_PASSWORD", "")
    DB_NAME = os.getenv("TIDB_DATABASE") or os.getenv("DB_NAME", "accident_analysis_db")
else:
    DB_HOST = os.getenv("DB_HOST") or os.getenv("TIDB_HOST", "localhost")
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
    Otherwise falls back to 'sqlite'.
    """
    global CURRENT_ACTIVE_DRIVER, CONNECTION_MESSAGE, _MYSQL_TESTED

    if _MYSQL_TESTED and CURRENT_ACTIVE_DRIVER:
        return CURRENT_ACTIVE_DRIVER

    if DB_TYPE == "mysql":
        try:
            import mysql.connector
            ssl_kwargs = get_mysql_ssl_config()

            # Attempt direct database connection first (works for TiDB Cloud and existing MySQL)
            try:
                test_conn = mysql.connector.connect(
                    host=DB_HOST,
                    port=DB_PORT,
                    user=DB_USER,
                    password=DB_PASSWORD,
                    database=DB_NAME,
                    connection_timeout=4,
                    **ssl_kwargs
                )
                test_conn.close()
            except Exception:
                # If database does not exist yet (local MySQL setup), connect to server and create it
                test_conn = mysql.connector.connect(
                    host=DB_HOST,
                    port=DB_PORT,
                    user=DB_USER,
                    password=DB_PASSWORD,
                    connection_timeout=4,
                    **ssl_kwargs
                )
                cursor = test_conn.cursor()
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
                cursor.close()
                test_conn.close()

            CURRENT_ACTIVE_DRIVER = "mysql"
            ssl_note = " (TLS Verified)" if ssl_kwargs else ""
            CONNECTION_MESSAGE = f"Connected to MySQL on {DB_HOST}:{DB_PORT}{ssl_note} (Database: {DB_NAME})"
        except Exception as e:
            CURRENT_ACTIVE_DRIVER = "sqlite"
            CONNECTION_MESSAGE = f"MySQL connection notice: {e}. Operating in SQLite fallback mode."
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
                autocommit=False,
                connection_timeout=5,
                **ssl_kwargs
            )
            return conn, "mysql"
        except Exception:
            # Fall back to sqlite if unexpected runtime disconnect
            return get_sqlite_connection(), "sqlite"
    else:
        return get_sqlite_connection(), "sqlite"


def get_sqlite_connection():
    conn = sqlite3.connect(SQLITE_PATH)
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
    Initializes tables for locations and accidents in MySQL or SQLite.
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
            conn.commit()
        finally:
            cursor.close()
            conn.close()


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
    return count > 0


def delete_accident(accident_id):
    count = execute_query(
        "DELETE FROM accidents WHERE accident_id = %s",
        (accident_id,),
        fetch="count"
    )
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


def get_all_regions():
    rows = execute_query("SELECT DISTINCT region FROM locations ORDER BY region ASC", fetch="all")
    return [r["region"] for r in rows if r["region"]]


def get_all_years():
    driver = CURRENT_ACTIVE_DRIVER or check_and_set_driver()
    if driver == "mysql":
        rows = execute_query("SELECT DISTINCT YEAR(accident_datetime) as year FROM accidents WHERE accident_datetime IS NOT NULL ORDER BY year DESC", fetch="all")
    else:
        rows = execute_query("SELECT DISTINCT SUBSTR(accident_datetime, 1, 4) as year FROM accidents WHERE accident_datetime IS NOT NULL ORDER BY year DESC", fetch="all")
    return [str(r["year"]) for r in rows if r.get("year")]


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
