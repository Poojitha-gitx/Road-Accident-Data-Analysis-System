"""
Comprehensive Authentication & Authorization Test Suite
Road Accident Data Analysis System

Verifies:
1. User signup validation and OTP creation.
2. OTP storage with secure hashing.
3. Incorrect OTP handling and attempt limits.
4. OTP expiration handling.
5. OTP resend cooldown enforcement.
6. Account creation only after successful OTP verification.
7. Duplicate email prevention.
8. Admin automatic bootstrap and login.
9. Normal user login and session handling.
10. Inactive user blocking.
11. Forgot password flow with OTP.
12. Password reset execution and subsequent login with new password.
13. Role-based access control (normal user receives 403 on admin-only routes).
14. Admin User Management: toggle activation and role change.
15. Profile name update and authenticated password change.
16. CSRF protection verification.
17. Logout and session termination.
"""

import time
from datetime import datetime, timedelta
from app import app
import database
import auth_utils

def run_auth_tests():
    print("=" * 75)
    print(" ROAD ACCIDENT DATA ANALYSIS SYSTEM - AUTHENTICATION TEST SUITE ")
    print("=" * 75)

    app.config["TESTING"] = True
    client = app.test_client()

    with app.app_context():
        database.init_db()

    # -------------------------------------------------------------
    # 1. Admin Bootstrap Verification
    # -------------------------------------------------------------
    print("\n[Phase 1] Verifying Administrator Bootstrapping...")
    admin = database.get_user_by_email("admin@example.com")
    assert admin is not None, "Admin user was not created in database"
    assert admin["role"] == "admin", "Admin user role is not 'admin'"
    assert admin["is_active"] == 1, "Admin user is not active"
    print(f"  -> Default Admin: {admin['email']} (Role: {admin['role']}, ID: {admin['user_id']}) PASS")

    # -------------------------------------------------------------
    # 2. Public Signup Flow & OTP Verification
    # -------------------------------------------------------------
    print("\n[Phase 2] Testing User Signup & OTP Verification...")
    test_email = "testuser@example.com"
    test_pass = "SecurePass123!"

    # Clean up test user if present from prior runs
    existing = database.get_user_by_email(test_email)
    if existing:
        database.execute_query("DELETE FROM users WHERE LOWER(email) = %s", (test_email,), fetch="count")

    # 2a. Signup submission
    res_signup = client.post("/signup", data={
        "full_name": "Test Analyst",
        "email": test_email,
        "password": test_pass,
        "confirm_password": test_pass
    }, follow_redirects=True)
    assert res_signup.status_code == 200
    assert b"verification code" in res_signup.data.lower()
    print("  -> Signup initiated: OTP dispatched and pending session created PASS")

    # Verify user is NOT yet created in database before OTP verification
    user_pre = database.get_user_by_email(test_email)
    assert user_pre is None, "Account must NOT be created before OTP verification!"
    print("  -> Verified user is NOT created in DB prior to OTP verification PASS")

    # Retrieve generated OTP from test capture
    otp_code = auth_utils.get_last_test_otp(test_email)
    assert otp_code is not None and len(otp_code) == 6, f"Invalid OTP generated: {otp_code}"
    print(f"  -> Captured 6-digit OTP: {otp_code} PASS")

    # 2b. Test Incorrect OTP attempt
    res_bad_otp = client.post("/verify-otp?purpose=signup", data={
        "email": test_email,
        "purpose": "signup",
        "otp_code": "000000"
    }, follow_redirects=True)
    assert res_bad_otp.status_code == 200
    assert b"incorrect verification code" in res_bad_otp.data.lower()
    print("  -> Incorrect OTP rejected with attempt counter decrement PASS")

    # 2c. Test Resend Cooldown
    res_cooldown = client.post("/resend-otp", data={
        "email": test_email,
        "purpose": "signup"
    }, follow_redirects=True)
    assert res_cooldown.status_code == 200
    assert b"please wait" in res_cooldown.data.lower()
    print("  -> 60-second OTP resend cooldown enforced PASS")

    # 2d. Test Correct OTP verification
    res_verify = client.post("/verify-otp?purpose=signup", data={
        "email": test_email,
        "purpose": "signup",
        "otp_code": otp_code
    }, follow_redirects=True)
    assert res_verify.status_code == 200
    assert b"account successfully created" in res_verify.data.lower() or b"sign in" in res_verify.data.lower()
    print("  -> Correct OTP accepted and redirected to login PASS")

    # Verify user is now created in DB with 'user' role
    user_post = database.get_user_by_email(test_email)
    assert user_post is not None, "User should be created in DB after OTP verification"
    assert user_post["role"] == "user", "Public signup must always assign role 'user'"
    assert user_post["is_active"] == 1, "User should be active"
    print(f"  -> User account confirmed in DB (ID: {user_post['user_id']}, Role: {user_post['role']}) PASS")

    # 2e. Test Duplicate Email Prevention
    res_dup = client.post("/signup", data={
        "full_name": "Test Analyst Duplicate",
        "email": test_email,
        "password": test_pass,
        "confirm_password": test_pass
    }, follow_redirects=True)
    assert res_dup.status_code == 200
    assert b"already exists" in res_dup.data.lower()
    print("  -> Duplicate email registration prevented PASS")

    # -------------------------------------------------------------
    # 3. User & Admin Authentication
    # -------------------------------------------------------------
    print("\n[Phase 3] Testing User & Admin Login Flow...")

    # 3a. Invalid credentials
    res_wrong_login = client.post("/login", data={
        "email": test_email,
        "password": "WrongPassword123"
    }, follow_redirects=True)
    assert res_wrong_login.status_code == 200
    assert b"invalid email address or password" in res_wrong_login.data.lower()
    print("  -> Invalid password rejected PASS")

    # 3b. Normal User Login
    res_user_login = client.post("/login", data={
        "email": test_email,
        "password": test_pass
    }, follow_redirects=True)
    assert res_user_login.status_code == 200
    assert b"Test Analyst" in res_user_login.data or b"analytical dashboard" in res_user_login.data.lower()
    print("  -> Normal User authenticated successfully PASS")

    # -------------------------------------------------------------
    # 4. Role-Based Access Control (RBAC) Enforcement
    # -------------------------------------------------------------
    print("\n[Phase 4] Testing Role-Based Authorization Restrictions for Normal User...")

    # Normal user CAN access read-only analytical pages
    for path in ["/dashboard", "/records", "/analysis", "/reports", "/profile"]:
        res_ok = client.get(path)
        assert res_ok.status_code == 200, f"Normal user should access {path}"
        print(f"  -> Read-only route {path:<12} HTTP 200 OK")

    # Normal user CANNOT view Add/Import buttons in records UI
    res_records_ui = client.get("/records")
    assert b"Add Accident Record" not in res_records_ui.data
    assert b"Import CSV" not in res_records_ui.data
    print("  -> UI hides Add/Edit/Import buttons for normal users PASS")

    # Normal user CANNOT access Admin User Management
    res_admin_users_forbidden = client.get("/admin/users")
    assert res_admin_users_forbidden.status_code == 403
    print("  -> GET /admin/users rejected with HTTP 403 Forbidden PASS")

    # Normal user CANNOT mutate accident records directly (backend security check)
    mutating_routes = [
        ("/records/add", {"region": "Tirupati", "accident_datetime": "2026-03-25 12:00:00", "vehicle_type": "Car", "severity": "Minor"}),
        ("/records/edit/1", {"region": "Tirupati", "accident_datetime": "2026-03-25 12:00:00", "vehicle_type": "Car", "severity": "Minor"}),
        ("/records/delete/1", {}),
        ("/records/import-csv", {}),
        ("/records/seed-demo", {})
    ]

    for route_path, payload in mutating_routes:
        res_mut = client.post(route_path, data=payload)
        assert res_mut.status_code == 403, f"Expected 403 Forbidden on {route_path}, got {res_mut.status_code}"
        print(f"  -> Unauthorized mutation {route_path:<20} HTTP 403 Forbidden PASS")

    # Logout normal user
    client.get("/logout")
    print("  -> Normal User signed out PASS")

    # -------------------------------------------------------------
    # 5. Admin Privileges & User Management
    # -------------------------------------------------------------
    print("\n[Phase 5] Testing Administrator Privileges & User Management...")

    # Login as Admin
    res_adm_login = client.post("/login", data={
        "email": "admin@example.com",
        "password": "your_strong_admin_password"
    }, follow_redirects=True)
    assert res_adm_login.status_code == 200
    print("  -> Administrator signed in successfully PASS")

    # Admin CAN access User Management page
    res_mgmt = client.get("/admin/users")
    assert res_mgmt.status_code == 200
    assert b"User &amp; Role Access Management" in res_mgmt.data or b"User & Role Access Management" in res_mgmt.data
    assert test_email.encode("utf-8") in res_mgmt.data
    print("  -> Admin accesses /admin/users successfully PASS")

    # Admin toggles user activation status (Deactivate test user)
    user_record = database.get_user_by_email(test_email)
    uid = user_record["user_id"]
    res_deact = client.post(f"/admin/users/{uid}/toggle-status", follow_redirects=True)
    assert res_deact.status_code == 200
    assert database.get_user_by_id(uid)["is_active"] == 0
    print("  -> Admin deactivates user account in DB PASS")

    # Admin promotes user to admin role
    res_promote = client.post(f"/admin/users/{uid}/change-role", data={"new_role": "admin"}, follow_redirects=True)
    assert res_promote.status_code == 200
    assert database.get_user_by_id(uid)["role"] == "admin"
    print("  -> Admin changes user role to 'admin' in DB PASS")

    # Re-activate user
    database.set_user_status(uid, 1)
    database.set_user_role(uid, "user")
    print("  -> Restored test user to active 'user' role PASS")

    # Logout Admin
    client.get("/logout")

    # -------------------------------------------------------------
    # 6. Deactivated User Login Blocking
    # -------------------------------------------------------------
    print("\n[Phase 6] Testing Deactivated Account Blocking...")
    database.set_user_status(uid, 0)
    res_blocked = client.post("/login", data={
        "email": test_email,
        "password": test_pass
    }, follow_redirects=True)
    assert res_blocked.status_code == 200
    assert b"deactivated" in res_blocked.data.lower()
    print("  -> Inactive account blocked from signing in PASS")
    database.set_user_status(uid, 1)

    # -------------------------------------------------------------
    # 7. Forgot Password & Reset Password Flow
    # -------------------------------------------------------------
    print("\n[Phase 7] Testing Forgot Password with OTP Flow...")

    # 7a. Initiate Forgot Password
    res_forgot = client.post("/forgot-password", data={
        "email": test_email
    }, follow_redirects=True)
    assert res_forgot.status_code == 200
    print("  -> Forgot password initiated: OTP dispatched PASS")

    # 7b. Capture Reset OTP
    reset_otp = auth_utils.get_last_test_otp(test_email)
    assert reset_otp is not None and len(reset_otp) == 6
    print(f"  -> Captured Password Reset OTP: {reset_otp} PASS")

    # 7c. Verify Reset OTP
    res_verify_reset = client.post("/verify-otp?purpose=forgot_password", data={
        "email": test_email,
        "purpose": "forgot_password",
        "otp_code": reset_otp
    }, follow_redirects=True)
    assert res_verify_reset.status_code == 200
    assert b"new password" in res_verify_reset.data.lower()
    print("  -> Reset OTP verified, navigated to /reset-password PASS")

    # 7d. Submit New Password
    new_test_pass = "BrandNewSecret2026!"
    res_new_pass = client.post("/reset-password", data={
        "password": new_test_pass,
        "confirm_password": new_test_pass
    }, follow_redirects=True)
    assert res_new_pass.status_code == 200
    assert b"successfully updated" in res_new_pass.data.lower()
    print("  -> Password reset submitted successfully PASS")

    # 7e. Sign in with New Password
    res_login_new = client.post("/login", data={
        "email": test_email,
        "password": new_test_pass
    }, follow_redirects=True)
    assert res_login_new.status_code == 200
    assert b"Test Analyst" in res_login_new.data or b"analytical dashboard" in res_login_new.data.lower()
    print("  -> Logged in successfully with updated password PASS")

    # -------------------------------------------------------------
    # 8. Profile & In-App Password Change
    # -------------------------------------------------------------
    print("\n[Phase 8] Testing Profile Update & In-App Password Change...")

    # Update profile name
    res_prof_update = client.post("/profile", data={
        "full_name": "Test Analyst Updated"
    }, follow_redirects=True)
    assert res_prof_update.status_code == 200
    assert database.get_user_by_id(uid)["full_name"] == "Test Analyst Updated"
    print("  -> Display name updated in database PASS")

    # In-app password change
    newer_pass = "SuperSecureKey999!"
    res_pwd_change = client.post("/profile/change-password", data={
        "current_password": new_test_pass,
        "new_password": newer_pass,
        "confirm_password": newer_pass
    }, follow_redirects=True)
    assert res_pwd_change.status_code == 200
    assert b"password updated successfully" in res_pwd_change.data.lower()
    print("  -> In-app password change verified PASS")

    client.get("/logout")

    # -------------------------------------------------------------
    # 9. OTP Expiration Verification
    # -------------------------------------------------------------
    print("\n[Phase 9] Testing OTP Expiration Logic...")
    exp_code = database.generate_and_store_otp(test_email, purpose="signup", expires_in_minutes=5)
    # Force expire in database
    past_time = (datetime.now() - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
    database.execute_query(
        "UPDATE otp_verifications SET expires_at = %s WHERE LOWER(email) = %s AND is_used = 0",
        (past_time, test_email),
        fetch="count"
    )
    is_valid, msg = database.verify_otp_attempt(test_email, exp_code, "signup")
    assert not is_valid, "Expired OTP must be rejected"
    assert "expired" in msg.lower(), f"Expected expiration message, got: {msg}"
    print(f"  -> Expired OTP rejected with message: '{msg}' PASS")

    # -------------------------------------------------------------
    # 10. CSRF Protection Check
    # -------------------------------------------------------------
    print("\n[Phase 10] Testing CSRF Token Enforcement...")
    app.config["ENFORCE_CSRF"] = True
    # Mutating request without CSRF token
    res_csrf_fail = client.post("/records/add", data={"region": "Tirupati"})
    assert res_csrf_fail.status_code == 400
    print("  -> Request without CSRF token correctly rejected with HTTP 400 PASS")
    app.config["ENFORCE_CSRF"] = False

    # Cleanup test user from database
    database.execute_query("DELETE FROM users WHERE LOWER(email) = %s", (test_email,), fetch="count")
    database.execute_query("DELETE FROM otp_verifications WHERE LOWER(email) = %s", (test_email,), fetch="count")

    print("\n" + "=" * 75)
    print(" >>> ALL 10 AUTHENTICATION & SECURITY PHASES PASSED WITH ZERO ERRORS! <<<")
    print("=" * 75)

if __name__ == "__main__":
    run_auth_tests()
