"""
Authentication Utilities & Security Layer
Road Accident Data Analysis System

Handles:
1. Gmail SMTP email dispatch for 6-digit OTP verification.
2. In-memory and session rate limiting.
3. Cryptographic CSRF token generation and validation.
4. Login and Administrator authorization decorators.
5. In-session OTP test capture fallback.
"""

import os
import smtplib
import ssl
import time
import secrets
import hmac
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from functools import wraps
from flask import session, request, redirect, url_for, flash, abort, jsonify, render_template

import database

# In-memory rate limiting store: { (key, action): [timestamps] }
_RATE_LIMITS = {}

# Test OTP capture store for testing/development when real SMTP is unconfigured or offline
_LAST_TEST_OTPS = {}


def get_smtp_config():
    """Reads Gmail SMTP settings from environment variables."""
    return {
        "server": os.getenv("MAIL_SERVER", "smtp.gmail.com").strip(),
        "port": int(os.getenv("MAIL_PORT", 587)),
        "use_tls": os.getenv("MAIL_USE_TLS", "True").lower() in ("true", "1", "yes"),
        "username": os.getenv("MAIL_USERNAME", "").strip(),
        "password": os.getenv("MAIL_PASSWORD", "").strip()
    }


def send_otp_email(recipient_email, otp_code, purpose="signup"):
    """
    Dispatches a 6-digit OTP to the user's email address via Gmail SMTP.
    Falls back gracefully and records code in debug mode if SMTP is unconfigured.
    """
    recipient_email = recipient_email.strip().lower()
    config = get_smtp_config()

    # Capture in test store for reliable test automation and fallback
    _LAST_TEST_OTPS[recipient_email] = {
        "otp": otp_code,
        "purpose": purpose,
        "time": time.time()
    }

    if purpose == "forgot_password":
        subject = "AccidentRadar - Password Reset Verification Code"
        action_desc = "reset your password"
    else:
        subject = "AccidentRadar - Account Verification Code"
        action_desc = "complete your account registration"

    text_body = f"""Hello,

Your verification code to {action_desc} is:

    {otp_code}

This code will expire in 5 minutes.
For your security, never share this code with anyone.

If you did not request this code, please ignore this email.

— AccidentRadar Safety Analytics Team
"""

    html_body = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #0a0e17; color: #f8fafc; margin: 0; padding: 24px; }}
    .card {{ max-width: 480px; margin: 0 auto; background-color: #111827; border: 1px solid #2a3449; border-radius: 12px; padding: 32px; box-shadow: 0 8px 24px rgba(0,0,0,0.5); }}
    .header {{ text-align: center; margin-bottom: 24px; }}
    .brand {{ font-size: 20px; font-weight: 800; color: #3b82f6; letter-spacing: -0.5px; }}
    .brand span {{ color: #94a3b8; font-size: 13px; font-weight: 400; }}
    .title {{ font-size: 18px; font-weight: 600; color: #f8fafc; margin: 16px 0 8px; }}
    .otp-box {{ background: linear-gradient(135deg, rgba(59, 130, 246, 0.15), rgba(139, 92, 246, 0.15)); border: 1px solid rgba(59, 130, 246, 0.4); border-radius: 8px; padding: 18px; text-align: center; margin: 24px 0; font-family: monospace; font-size: 32px; font-weight: 700; letter-spacing: 8px; color: #60a5fa; }}
    .footer {{ font-size: 12px; color: #64748b; margin-top: 24px; line-height: 1.5; border-top: 1px solid #1a2234; padding-top: 16px; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <div class="brand">AccidentRadar<br><span>College Mini Project</span></div>
      <div class="title">Email Verification Code</div>
    </div>
    <p style="color: #94a3b8; font-size: 14px; margin-bottom: 12px;">Use the verification code below to {action_desc}:</p>
    <div class="otp-box">{otp_code}</div>
    <p style="color: #f59e0b; font-size: 13px; margin: 12px 0;"><strong>Expires in 5 minutes.</strong> Do not share this OTP with anyone.</p>
    <div class="footer">
      If you did not initiate this request, no action is required and you can safely ignore this message.<br>
      Road Accident Data Analysis System &copy; {time.strftime('%Y')}
    </div>
  </div>
</body>
</html>
"""

    # Check if real Gmail credentials are provided
    if not config["username"] or not config["password"] or "example.com" in config["username"] or "yourgmail" in config["username"]:
        print(f"[AUTH OTP NOTIFICATION] Gmail SMTP unconfigured. Code for {recipient_email}: [{otp_code}] (Expires in 5 min)")
        return True, None

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"AccidentRadar System <{config['username']}>"
        msg["To"] = recipient_email

        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        context = ssl.create_default_context()
        if config["port"] == 465:
            with smtplib.SMTP_SSL(config["server"], config["port"], context=context, timeout=10) as server:
                server.login(config["username"], config["password"])
                server.send_message(msg)
        else:
            with smtplib.SMTP(config["server"], config["port"], timeout=10) as server:
                if config["use_tls"]:
                    server.starttls(context=context)
                server.login(config["username"], config["password"])
                server.send_message(msg)

        return True, None
    except Exception as e:
        err_msg = f"Failed to send email via Gmail SMTP: {str(e)}"
        print(f"[AUTH OTP ERROR] {err_msg} | Fallback code for {recipient_email}: [{otp_code}]")
        return False, err_msg


def get_last_test_otp(recipient_email):
    """Retrieves the last generated OTP for testing verification."""
    item = _LAST_TEST_OTPS.get(recipient_email.strip().lower())
    return item["otp"] if item else None


# ============================================================
# Rate Limiting & Cooldowns
# ============================================================

def is_rate_limited(key, action, max_attempts=5, window_seconds=60):
    """
    Sliding window rate limiter for auth operations.
    Returns (is_limited: bool, wait_seconds: int).
    """
    now = time.time()
    store_key = (str(key), str(action))
    timestamps = _RATE_LIMITS.get(store_key, [])

    # Prune outdated timestamps
    valid_stamps = [t for t in timestamps if now - t < window_seconds]

    if len(valid_stamps) >= max_attempts:
        wait_sec = int(window_seconds - (now - valid_stamps[0])) + 1
        _RATE_LIMITS[store_key] = valid_stamps
        return True, max(1, wait_sec)

    valid_stamps.append(now)
    _RATE_LIMITS[store_key] = valid_stamps
    return False, 0


# ============================================================
# CSRF Protection
# ============================================================

def generate_csrf_token():
    """Generates or retrieves the active session CSRF token."""
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(32)
    return session["_csrf_token"]


def validate_csrf():
    """
    Validates CSRF token on mutating HTTP requests.
    Inspects form field 'csrf_token' or HTTP header 'X-CSRFToken' / 'X-CSRF-Token'.
    """
    # Skip safe read-only methods
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return True

    # Allow exemption for testing if explicitly disabled
    from flask import current_app
    if current_app.config.get("TESTING") and not current_app.config.get("ENFORCE_CSRF", False):
        return True

    expected = session.get("_csrf_token")
    if not expected:
        return False

    received = (
        request.form.get("csrf_token")
        or request.headers.get("X-CSRFToken")
        or request.headers.get("X-CSRF-Token")
    )

    if not received or not hmac.compare_digest(str(expected), str(received)):
        return False

    return True


# ============================================================
# Authorization Decorators
# ============================================================

def get_current_user():
    """Returns the authenticated user record from DB or None."""
    uid = session.get("user_id")
    if not uid:
        return None
    user = database.get_user_by_id(uid)
    if not user or not user.get("is_active"):
        return None
    return user


def login_required(f):
    """Requires the user to have an active authenticated session."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in to access this page.", "warning")
            return redirect(url_for("login", next=request.path))

        user = database.get_user_by_id(session["user_id"])
        if not user or not user.get("is_active"):
            session.clear()
            flash("Your account has been deactivated or not found. Please log in again.", "danger")
            return redirect(url_for("login"))

        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """
    Requires the authenticated user to hold the 'admin' role.
    Rejects unauthorized access with HTTP 403 error.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in as an administrator to access this resource.", "warning")
            return redirect(url_for("login", next=request.path))

        user = database.get_user_by_id(session["user_id"])
        if not user or not user.get("is_active"):
            session.clear()
            flash("Your account has been deactivated. Please sign in again.", "danger")
            return redirect(url_for("login"))

        if user.get("role") != "admin":
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"error": "Forbidden: Administrator privileges required."}), 403
            flash("Access denied: Administrator privileges required.", "danger")
            return render_template(
                "base.html",
                error_title="403 Forbidden - Access Denied",
                error_message="Access denied: Administrator privileges are required to perform this action."
            ), 403

        return f(*args, **kwargs)
    return decorated_function
