"""
Road Accident Data Analysis System
Main Flask Application Server
"""

import os
import io
import csv
import secrets
from datetime import datetime, timedelta
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, jsonify, send_file, Response,
    session, abort
)
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

import database
import analysis
import auth_utils
from auth_utils import (
    login_required, admin_required,
    generate_csrf_token, validate_csrf, is_rate_limited
)

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "road_accident_mini_project_secret_key_2026")
# Disable debug mode by default in production; enable only if FLASK_DEBUG is explicitly set to 'True' or '1'
app.config["DEBUG"] = os.getenv("FLASK_DEBUG", "False").lower() in ("true", "1", "yes")

# Secure Session Configuration
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)

# Valid enumerated domain values
VALID_VEHICLES = ["Bike", "Car", "Bus", "Truck", "Auto", "Other"]
VALID_SEVERITIES = ["Minor", "Serious", "Fatal"]
VALID_WEATHERS = ["Clear", "Rainy", "Foggy", "Overcast", "Windy", "Other"]

# Initialize database schema and default admin on startup
with app.app_context():
    database.init_db()


@app.before_request
def csrf_protect():
    """Validates CSRF token on mutating requests."""
    if not validate_csrf():
        abort(400, "CSRF token missing or invalid. Please reload and try again.")


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
    user = auth_utils.get_current_user()
    return {
        "current_user": user,
        "csrf_token": generate_csrf_token,
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
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
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


@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    filters = extract_filters(request.args)
    stats = analysis.get_summary_statistics(filters)
    details = analysis.get_detailed_analysis(filters)

    return render_template(
        "dashboard.html",
        active_page="dashboard",
        filters=filters,
        stats=stats,
        details=details,
        is_admin_view=True
    )


@app.route("/records")
@login_required
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
@admin_required
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
@login_required
def get_record_api(accident_id):
    rec = database.get_accident_by_id(accident_id)
    if not rec:
        return jsonify({"error": "Record not found"}), 404
    return jsonify(rec)


@app.route("/records/edit/<int:accident_id>", methods=["POST"])
@admin_required
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
@admin_required
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
@admin_required
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
@admin_required
def seed_demo():
    from seed_data import seed_sample_accidents
    try:
        inserted = seed_sample_accidents("sample_accidents.csv", wipe_first=False)
        flash(f"Seeded {inserted} synthetic demonstration records successfully!", "success")
    except Exception as e:
        flash(f"Seeding failed: {str(e)}", "danger")
    return redirect(url_for("records"))


@app.route("/analysis")
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
def download_sample_csv():
    """Serves the template sample CSV for users to download and inspect."""
    sample_path = os.path.join(os.path.dirname(__file__), "sample_accidents.csv")
    if os.path.exists(sample_path):
        return send_file(sample_path, as_attachment=True, download_name="sample_accidents_template.csv")
    return "Sample CSV not found", 404


# ============================================================
# Authentication & Access Control Routes
# ============================================================

@app.route("/signup", methods=["GET", "POST"])
def signup():
    """Handles new user registration with secure hashing and automatic user role assignment."""
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        ip = request.remote_addr or "127.0.0.1"
        limited, wait_sec = is_rate_limited(ip, "signup", max_attempts=5, window_seconds=300)
        if limited:
            flash(f"Too many registration attempts. Please wait {wait_sec} seconds before trying again.", "warning")
            return render_template("signup.html", full_name=full_name, email=email)

        errors = []
        if not full_name:
            errors.append("Full Name is required.")
        if not email or "@" not in email or "." not in email:
            errors.append("A valid email address is required.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters long.")
        if password != confirm_password:
            errors.append("Passwords do not match.")

        if errors:
            for err in errors:
                flash(err, "danger")
            return render_template("signup.html", full_name=full_name, email=email)

        existing_user = database.get_user_by_email(email)
        if existing_user:
            flash("An account with this email address already exists. Please sign in.", "warning")
            return redirect(url_for("login"))

        # Create user with securely hashed password and automatic 'user' role
        pwd_hash = generate_password_hash(password)
        database.create_user(
            full_name=full_name,
            email=email,
            password_hash=pwd_hash,
            role="user",
            is_active=1
        )

        flash("Account created successfully! Please sign in with your email and password.", "success")
        return redirect(url_for("login"))

    return render_template("signup.html")


@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    """Validates 6-digit OTP code for signup registration or password recovery."""
    purpose = request.args.get("purpose") or request.form.get("purpose") or "signup"
    email = request.args.get("email") or request.form.get("email") or ""
    email = email.strip().lower()

    if not email:
        if purpose == "signup" and session.get("pending_signup"):
            email = session["pending_signup"].get("email", "")
        elif purpose == "forgot_password" and session.get("reset_email"):
            email = session.get("reset_email", "")

    if not email:
        flash("Invalid verification request session. Please restart the process.", "warning")
        return redirect(url_for("signup" if purpose == "signup" else "forgot_password"))

    can_resend, remaining_cd = database.check_otp_resend_cooldown(email, purpose, cooldown_seconds=60)

    if request.method == "POST":
        otp_code = request.form.get("otp_code", "").strip()
        if not otp_code or len(otp_code) != 6 or not otp_code.isdigit():
            flash("Please enter a valid 6-digit numeric verification code.", "danger")
            return render_template("verify_otp.html", email=email, purpose=purpose, remaining_cooldown=remaining_cd)

        is_valid, msg = database.verify_otp_attempt(email, otp_code, purpose)
        if not is_valid:
            flash(msg, "danger")
            return render_template("verify_otp.html", email=email, purpose=purpose, remaining_cooldown=remaining_cd)

        if purpose == "signup":
            pending = session.get("pending_signup")
            if not pending or pending.get("email") != email:
                flash("Signup registration session expired. Please sign up again.", "warning")
                return redirect(url_for("signup"))

            # Create user in database with automatically assigned 'user' role
            database.create_user(
                full_name=pending["full_name"],
                email=pending["email"],
                password_hash=pending["password_hash"],
                role="user",
                is_active=1
            )
            session.pop("pending_signup", None)
            flash("Account successfully created and verified! You can now log in.", "success")
            return redirect(url_for("login"))

        elif purpose == "forgot_password":
            session["can_reset_password"] = email
            flash("Security code verified successfully. Please choose a new password.", "success")
            return redirect(url_for("reset_password"))

    return render_template(
        "verify_otp.html",
        email=email,
        purpose=purpose,
        remaining_cooldown=remaining_cd
    )


@app.route("/resend-otp", methods=["POST"])
def resend_otp():
    """Resends a new OTP code if the cooldown period has elapsed."""
    purpose = request.form.get("purpose", "signup")
    email = request.form.get("email", "").strip().lower()

    if not email:
        flash("Email address required to resend verification code.", "danger")
        return redirect(url_for("login"))

    can_resend, rem = database.check_otp_resend_cooldown(email, purpose, cooldown_seconds=60)
    if not can_resend:
        flash(f"Please wait {rem} seconds before requesting a new verification code.", "warning")
        return redirect(url_for("verify_otp", purpose=purpose, email=email))

    otp_code = database.generate_and_store_otp(email, purpose=purpose, expires_in_minutes=5)
    auth_utils.send_otp_email(email, otp_code, purpose=purpose)

    flash("A fresh 6-digit verification code has been dispatched to your email address.", "info")
    return redirect(url_for("verify_otp", purpose=purpose, email=email))


@app.route("/login", methods=["GET", "POST"])
def login():
    """Authenticates users via email and password."""
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    next_url = request.args.get("next", "")

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        remember_me = bool(request.form.get("remember_me"))

        ip = request.remote_addr or "127.0.0.1"
        limited, wait_sec = is_rate_limited(ip, "login", max_attempts=10, window_seconds=60)
        if limited:
            flash(f"Too many login attempts. Please wait {wait_sec} seconds before trying again.", "warning")
            return render_template("login.html", email=email)

        user = database.get_user_by_email(email)
        if not user or not check_password_hash(user["password_hash"], password):
            flash("Invalid email address or password.", "danger")
            return render_template("login.html", email=email)

        if not user.get("is_active"):
            flash("This account has been deactivated. Please contact an administrator.", "danger")
            return render_template("login.html", email=email)

        # Authenticate session
        session.clear()
        session["user_id"] = user["user_id"]
        session["user_role"] = user["role"]
        session["user_name"] = user["full_name"]
        session.permanent = remember_me

        flash(f"Welcome back, {user['full_name']}!", "success")

        if next_url and next_url.startswith("/") and not next_url.startswith("//"):
            return redirect(next_url)

        # Redirect administrators to the Admin Dashboard; normal users to the User Dashboard
        if user.get("role") == "admin":
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    """Terminates active session and clears auth cookies."""
    session.clear()
    flash("You have been signed out successfully.", "info")
    return redirect(url_for("login"))


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """Initiates password recovery with secure recovery link and verification code."""
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()

        ip = request.remote_addr or "127.0.0.1"
        limited, wait_sec = is_rate_limited(ip, "forgot_password", max_attempts=5, window_seconds=300)
        if limited:
            flash(f"Too many password reset requests. Please wait {wait_sec} seconds.", "warning")
            return render_template("forgot_password.html", email=email)

        if not email or "@" not in email:
            flash("Please enter a valid email address.", "danger")
            return render_template("forgot_password.html", email=email)

        user = database.get_user_by_email(email)
        token = secrets.token_urlsafe(32)

        if user and user.get("is_active"):
            otp_code = database.generate_and_store_otp(email, purpose="forgot_password", expires_in_minutes=15)
            auth_utils.store_reset_token(email, token, expires_in_minutes=15)
            reset_url = url_for("reset_password", token=token, email=email, _external=True)
            auth_utils.send_password_reset_email(email, reset_url=reset_url, otp_code=otp_code)

        session["reset_email"] = email
        session["reset_token"] = token
        flash("If an account with that email exists, password recovery instructions have been dispatched.", "info")
        return redirect(url_for("reset_password", token=token, email=email))

    return render_template("forgot_password.html")


@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    """Finalizes password update after token, OTP, or session authorization."""
    token = request.args.get("token") or request.form.get("token") or session.get("reset_token")
    email = request.args.get("email") or request.form.get("email") or session.get("reset_email") or session.get("can_reset_password")

    is_authorized = False
    if email:
        if session.get("can_reset_password") == email:
            is_authorized = True
        elif token and auth_utils.verify_reset_token(email, token):
            is_authorized = True

    if not is_authorized:
        flash("Password reset authorization has expired or is invalid. Please request a new recovery link.", "warning")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        errors = []
        if len(password) < 6:
            errors.append("New password must be at least 6 characters long.")
        if password != confirm_password:
            errors.append("Passwords do not match.")

        if errors:
            for err in errors:
                flash(err, "danger")
            return render_template("reset_password.html", token=token, email=email)

        user = database.get_user_by_email(email)
        if not user:
            flash("User record could not be found.", "danger")
            return redirect(url_for("login"))

        new_hash = generate_password_hash(password)
        database.update_user_password(user["user_id"], new_hash)

        auth_utils.consume_reset_token(email)
        session.pop("can_reset_password", None)
        session.pop("reset_email", None)
        session.pop("reset_token", None)

        flash("Your password has been successfully updated! Please sign in with your new password.", "success")
        return redirect(url_for("login"))

    return render_template("reset_password.html", token=token, email=email)

    return render_template("reset_password.html")


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    """Allows authenticated users to view profile details and update display name."""
    user = database.get_user_by_id(session["user_id"])
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        if not full_name:
            flash("Full Name cannot be empty.", "danger")
        else:
            database.update_user_profile(user["user_id"], full_name)
            session["user_name"] = full_name
            flash("Profile updated successfully.", "success")
        return redirect(url_for("profile"))

    return render_template("profile.html", active_page="profile")


@app.route("/profile/change-password", methods=["POST"])
@login_required
def change_password():
    """Allows authenticated users to change their own password."""
    user = database.get_user_by_id(session["user_id"])
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not check_password_hash(user["password_hash"], current_password):
        flash("Your current password is incorrect.", "danger")
        return redirect(url_for("profile"))

    if len(new_password) < 6:
        flash("New password must be at least 6 characters long.", "danger")
        return redirect(url_for("profile"))

    if new_password != confirm_password:
        flash("New password and confirmation do not match.", "danger")
        return redirect(url_for("profile"))

    new_hash = generate_password_hash(new_password)
    database.update_user_password(user["user_id"], new_hash)
    flash("Password updated successfully.", "success")
    return redirect(url_for("profile"))


@app.route("/admin/users")
@admin_required
def admin_users():
    """Lists registered users for administrative management."""
    users = database.get_all_users()
    return render_template("admin_users.html", active_page="admin_users", users=users)


@app.route("/admin/users/<int:user_id>/toggle-status", methods=["POST"])
@admin_required
def admin_toggle_user_status(user_id):
    """Toggles account active/inactive state (prevents self-deactivation)."""
    if user_id == session.get("user_id"):
        flash("Administrative protection: You cannot deactivate your own active account.", "warning")
        return redirect(url_for("admin_users"))

    target_user = database.get_user_by_id(user_id)
    if not target_user:
        flash("User record not found.", "danger")
        return redirect(url_for("admin_users"))

    new_status = 0 if target_user.get("is_active") else 1
    database.set_user_status(user_id, new_status)
    status_label = "activated" if new_status else "deactivated"
    flash(f"User account '{target_user['email']}' has been successfully {status_label}.", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/<int:user_id>/change-role", methods=["POST"])
@admin_required
def admin_change_user_role(user_id):
    """Changes user authorization role (prevents self-demotion)."""
    if user_id == session.get("user_id"):
        flash("Administrative protection: You cannot alter your own administrative role.", "warning")
        return redirect(url_for("admin_users"))

    new_role = request.form.get("new_role", "user")
    if new_role not in ("user", "admin"):
        flash("Invalid role specified.", "danger")
        return redirect(url_for("admin_users"))

    database.set_user_role(user_id, new_role)
    flash(f"Authorization role for user #{user_id} updated to '{new_role}'.", "success")
    return redirect(url_for("admin_users"))


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = app.config.get("DEBUG", False)
    print(f"Starting Road Accident Data Analysis System on http://localhost:{port} (Debug: {debug})")
    app.run(host="0.0.0.0", port=port, debug=debug)
