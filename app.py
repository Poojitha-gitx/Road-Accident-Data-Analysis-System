"""
Road Accident Data Analysis System
Main Flask Application Server
"""

import os
import io
import csv
from datetime import datetime
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, jsonify, send_file, Response
)
from dotenv import load_dotenv

import database
import analysis

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "road_accident_mini_project_secret_key_2026")
# Disable debug mode by default in production; enable only if FLASK_DEBUG is explicitly set to 'True' or '1'
app.config["DEBUG"] = os.getenv("FLASK_DEBUG", "False").lower() in ("true", "1", "yes")

# Valid enumerated domain values
VALID_VEHICLES = ["Bike", "Car", "Bus", "Truck", "Auto", "Other"]
VALID_SEVERITIES = ["Minor", "Serious", "Fatal"]
VALID_WEATHERS = ["Clear", "Rainy", "Foggy", "Overcast", "Windy", "Other"]

# Initialize database schema on startup
with app.app_context():
    database.init_db()


def extract_filters(req_args):
    """Extracts common filter parameters from request query args."""
    return {
        "year": req_args.get("year", "").strip(),
        "region": req_args.get("region", "").strip(),
        "vehicle_type": req_args.get("vehicle_type", "").strip(),
        "severity": req_args.get("severity", "").strip(),
        "weather": req_args.get("weather", "").strip(),
        "search": req_args.get("search", "").strip()
    }


@app.context_processor
def inject_global_context():
    """Injects common context variables across all Jinja templates."""
    return {
        "db_status": database.get_db_status(),
        "all_regions": database.get_all_regions(),
        "all_years": database.get_all_years(),
        "valid_vehicles": VALID_VEHICLES,
        "valid_severities": VALID_SEVERITIES,
        "valid_weathers": VALID_WEATHERS,
        "current_year": datetime.now().year
    }


# ============================================================
# Routes
# ============================================================

@app.route("/")
def index():
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
def dashboard():
    filters = extract_filters(request.args)
    stats = analysis.get_summary_statistics(filters)
    details = analysis.get_detailed_analysis(filters)

    return render_template(
        "dashboard.html",
        active_page="dashboard",
        filters=filters,
        stats=stats,
        details=details
    )


@app.route("/records")
def records():
    filters = extract_filters(request.args)
    page = int(request.args.get("page", 1))
    sort_by = request.args.get("sort_by", "accident_datetime")
    order = request.args.get("order", "DESC")

    records_data = database.get_accidents(
        filters=filters,
        page=page,
        per_page=12,
        sort_by=sort_by,
        order=order
    )

    return render_template(
        "records.html",
        active_page="records",
        filters=filters,
        data=records_data,
        sort_by=sort_by,
        order=order
    )


@app.route("/records/add", methods=["POST"])
def add_record():
    region = request.form.get("region", "").strip()
    road_name = request.form.get("road_name", "").strip()
    accident_datetime = request.form.get("accident_datetime", "").strip()
    vehicle_type = request.form.get("vehicle_type", "").strip()
    severity = request.form.get("severity", "").strip()
    weather = request.form.get("weather", "Clear").strip()

    # Form Validation
    errors = []
    if not region:
        errors.append("Geographic Region is required.")
    if not accident_datetime:
        errors.append("Accident Date and Time is required.")
    else:
        # Validate datetime format
        try:
            dt_clean = accident_datetime.replace("T", " ").strip()
            if len(dt_clean) == 10:
                dt_clean += " 00:00:00"
            elif len(dt_clean) == 16:
                dt_clean += ":00"
            elif len(dt_clean) > 19:
                dt_clean = dt_clean[:19]
            datetime.strptime(dt_clean, "%Y-%m-%d %H:%M:%S")
            accident_datetime = dt_clean
        except ValueError:
            errors.append(f"Invalid date-time '{accident_datetime}'. Please use YYYY-MM-DD HH:MM format.")

    if vehicle_type not in VALID_VEHICLES:
        errors.append(f"Invalid vehicle type '{vehicle_type}'. Allowed types: {', '.join(VALID_VEHICLES)}.")
    if severity not in VALID_SEVERITIES:
        errors.append(f"Invalid severity level '{severity}'. Allowed levels: {', '.join(VALID_SEVERITIES)}.")
    if weather and weather not in VALID_WEATHERS:
        errors.append(f"Invalid weather condition '{weather}'. Allowed: {', '.join(VALID_WEATHERS)}.")

    if errors:
        for err in errors:
            flash(err, "danger")
        return redirect(url_for("records"))

    try:
        new_id = database.add_accident(
            accident_datetime_str=accident_datetime,
            region=region,
            road_name=road_name,
            vehicle_type=vehicle_type,
            severity=severity,
            weather=weather or "Clear"
        )
        flash(f"Accident record #{new_id} saved successfully! Total count updated.", "success")
    except Exception as e:
        flash(f"Failed to save accident record: {str(e)}. Please check your database connection and try again.", "danger")

    return redirect(url_for("records"))


@app.route("/api/record/<int:accident_id>")
def get_record_api(accident_id):
    rec = database.get_accident_by_id(accident_id)
    if not rec:
        return jsonify({"error": "Record not found"}), 404
    return jsonify(rec)


@app.route("/records/edit/<int:accident_id>", methods=["POST"])
def edit_record(accident_id):
    region = request.form.get("region", "").strip()
    road_name = request.form.get("road_name", "").strip()
    accident_datetime = request.form.get("accident_datetime", "").strip()
    vehicle_type = request.form.get("vehicle_type", "").strip()
    severity = request.form.get("severity", "").strip()
    weather = request.form.get("weather", "Clear").strip()

    errors = []
    if not region:
        errors.append("Geographic Region is required.")
    if not accident_datetime:
        errors.append("Accident Date and Time is required.")
    else:
        try:
            dt_clean = accident_datetime.replace("T", " ").strip()
            if len(dt_clean) == 10:
                dt_clean += " 00:00:00"
            elif len(dt_clean) == 16:
                dt_clean += ":00"
            elif len(dt_clean) > 19:
                dt_clean = dt_clean[:19]
            datetime.strptime(dt_clean, "%Y-%m-%d %H:%M:%S")
            accident_datetime = dt_clean
        except ValueError:
            errors.append("Invalid date-time format. Please use YYYY-MM-DD HH:MM.")

    if vehicle_type not in VALID_VEHICLES:
        errors.append("Invalid vehicle type selected.")
    if severity not in VALID_SEVERITIES:
        errors.append("Invalid severity level selected.")

    if errors:
        for err in errors:
            flash(err, "danger")
        return redirect(url_for("records"))

    try:
        success = database.update_accident(
            accident_id=accident_id,
            accident_datetime_str=accident_datetime,
            region=region,
            road_name=road_name,
            vehicle_type=vehicle_type,
            severity=severity,
            weather=weather or "Clear"
        )
        if success:
            flash(f"Accident record #{accident_id} updated successfully!", "success")
        else:
            flash("Record not found or no changes were made.", "warning")
    except Exception as e:
        flash(f"Error updating record #{accident_id}: {str(e)}", "danger")

    return redirect(url_for("records"))


@app.route("/records/delete/<int:accident_id>", methods=["POST"])
def delete_record(accident_id):
    try:
        success = database.delete_accident(accident_id)
        if success:
            flash(f"Accident record #{accident_id} deleted successfully.", "success")
        else:
            flash("Record could not be found.", "warning")
    except Exception as e:
        flash(f"Error deleting record: {str(e)}", "danger")
    return redirect(url_for("records"))


@app.route("/records/import-csv", methods=["POST"])
def import_csv():
    if "csv_file" not in request.files:
        flash("No file was uploaded.", "danger")
        return redirect(url_for("records"))

    file = request.files["csv_file"]
    if file.filename == "":
        flash("Please select a valid CSV file.", "warning")
        return redirect(url_for("records"))

    if not file.filename.lower().endswith(".csv"):
        flash("Only .csv files are supported for import.", "danger")
        return redirect(url_for("records"))

    try:
        content = file.stream.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(content))
        
        required_cols = {"region", "accident_datetime", "vehicle_type", "severity"}
        fieldnames = set(reader.fieldnames or [])
        if not required_cols.issubset(fieldnames):
            missing = required_cols - fieldnames
            flash(f"CSV is missing mandatory header columns: {', '.join(missing)}", "danger")
            return redirect(url_for("records"))

        inserted_count = 0
        invalid_rows = []

        for row_num, row in enumerate(reader, start=2):  # row 2 is first data line
            region = (row.get("region") or "").strip()
            road_name = (row.get("road_name") or "").strip()
            dt_raw = (row.get("accident_datetime") or "").strip()
            veh = (row.get("vehicle_type") or "").strip()
            sev = (row.get("severity") or "").strip()
            weather = (row.get("weather") or "Clear").strip()

            row_errors = []
            if not region:
                row_errors.append("missing region")
            if not dt_raw:
                row_errors.append("missing datetime")
            else:
                try:
                    dt_clean = dt_raw.replace("T", " ")
                    if len(dt_clean) == 16:
                        dt_clean += ":00"
                    datetime.strptime(dt_clean[:19], "%Y-%m-%d %H:%M:%S")
                    dt_raw = dt_clean[:19]
                except ValueError:
                    row_errors.append(f"invalid datetime '{dt_raw}'")

            if veh not in VALID_VEHICLES:
                row_errors.append(f"invalid vehicle '{veh}'")
            if sev not in VALID_SEVERITIES:
                row_errors.append(f"invalid severity '{sev}'")

            if row_errors:
                invalid_rows.append(f"Row {row_num}: {', '.join(row_errors)}")
                continue

            try:
                database.add_accident(
                    accident_datetime_str=dt_raw,
                    region=region,
                    road_name=road_name,
                    vehicle_type=veh,
                    severity=sev,
                    weather=weather or "Clear"
                )
                inserted_count += 1
            except Exception as e:
                invalid_rows.append(f"Row {row_num}: DB error ({str(e)})")

        if inserted_count > 0:
            flash(f"Successfully imported {inserted_count} accident records from CSV!", "success")
        if invalid_rows:
            sample_errors = invalid_rows[:5]
            err_msg = f"{len(invalid_rows)} row(s) had errors and were rejected: " + " | ".join(sample_errors)
            if len(invalid_rows) > 5:
                err_msg += f" ... (+{len(invalid_rows)-5} more)"
            flash(err_msg, "warning")

    except Exception as e:
        flash(f"Failed to process CSV file: {str(e)}", "danger")

    return redirect(url_for("records"))


@app.route("/records/seed-demo", methods=["POST"])
def seed_demo():
    from seed_data import seed_sample_accidents
    try:
        inserted = seed_sample_accidents("sample_accidents.csv", wipe_first=False)
        flash(f"Seeded {inserted} synthetic demonstration records successfully!", "success")
    except Exception as e:
        flash(f"Seeding failed: {str(e)}", "danger")
    return redirect(url_for("records"))


@app.route("/analysis")
def accident_analysis():
    filters = extract_filters(request.args)
    stats = analysis.get_summary_statistics(filters)
    details = analysis.get_detailed_analysis(filters)

    return render_template(
        "analysis.html",
        active_page="analysis",
        filters=filters,
        stats=stats,
        details=details
    )


@app.route("/reports")
def reports():
    filters = extract_filters(request.args)
    stats = analysis.get_summary_statistics(filters)
    details = analysis.get_detailed_analysis(filters)

    return render_template(
        "reports.html",
        active_page="reports",
        filters=filters,
        stats=stats,
        details=details
    )


@app.route("/chart/<chart_type>")
def serve_chart(chart_type):
    filters = extract_filters(request.args)
    as_download = request.args.get("download", "false").lower() == "true"
    
    img_bytes = analysis.generate_chart_bytes(chart_type, filters)
    filename = f"accident_{chart_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"

    return send_file(
        io.BytesIO(img_bytes),
        mimetype="image/png",
        as_attachment=as_download,
        download_name=filename
    )


@app.route("/reports/export-csv")
def export_csv_report():
    filters = extract_filters(request.args)
    df = analysis.load_dataframe(filters)

    output = io.StringIO()
    df.to_csv(output, index=False)
    csv_bytes = output.getvalue().encode("utf-8")

    filename = f"road_accident_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        csv_bytes,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.route("/reports/export-summary")
def export_summary_report():
    filters = extract_filters(request.args)
    text_content = analysis.generate_text_summary_report(filters)

    filename = f"accident_summary_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    return Response(
        text_content.encode("utf-8"),
        mimetype="text/plain",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.route("/sample-csv")
def download_sample_csv():
    """Serves the template sample CSV for users to download and inspect."""
    sample_path = os.path.join(os.path.dirname(__file__), "sample_accidents.csv")
    if os.path.exists(sample_path):
        return send_file(sample_path, as_attachment=True, download_name="sample_accidents_template.csv")
    return "Sample CSV not found", 404


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = app.config.get("DEBUG", False)
    print(f"Starting Road Accident Data Analysis System on http://localhost:{port} (Debug: {debug})")
    app.run(host="0.0.0.0", port=port, debug=debug)
