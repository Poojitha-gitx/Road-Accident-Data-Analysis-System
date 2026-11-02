/**
 * Authentication Client Script
 * Road Accident Data Analysis System
 *
 * Implements:
 * - Password visibility controls (eye toggle)
 * - Password strength meter and match validation
 * - Form submission loading indicators
 * - Client-side validation messaging
 */

document.addEventListener("DOMContentLoaded", function () {
  // 1. Password Visibility Toggle
  const toggleButtons = document.querySelectorAll(".password-toggle-btn");
  toggleButtons.forEach(function (btn) {
    btn.addEventListener("click", function (e) {
      e.preventDefault();
      const targetId = btn.getAttribute("data-target");
      const input = document.getElementById(targetId);
      if (!input) return;

      const isPassword = input.type === "password";
      input.type = isPassword ? "text" : "password";

      const showIcon = btn.querySelector(".icon-show");
      const hideIcon = btn.querySelector(".icon-hide");

      if (showIcon && hideIcon) {
        showIcon.style.display = isPassword ? "none" : "block";
        hideIcon.style.display = isPassword ? "block" : "none";
      }
      btn.setAttribute("aria-label", isPassword ? "Hide password" : "Show password");
    });
  });

  // 2. Password Strength Calculation
  const pwdInput = document.getElementById("password");
  const strengthFill = document.getElementById("strengthFill");
  const strengthText = document.getElementById("strengthText");

  if (pwdInput && strengthFill && strengthText) {
    pwdInput.addEventListener("input", function () {
      const val = pwdInput.value;
      if (!val) {
        strengthFill.style.width = "0%";
        strengthFill.style.backgroundColor = "transparent";
        strengthText.textContent = "Strength: None";
        return;
      }

      let score = 0;
      if (val.length >= 6) score += 1;
      if (val.length >= 10) score += 1;
      if (/[A-Z]/.test(val) && /[a-z]/.test(val)) score += 1;
      if (/[0-9]/.test(val)) score += 1;
      if (/[^A-Za-z0-9]/.test(val)) score += 1;

      let label = "Weak";
      let color = "#a04b45";
      let pct = "25%";

      if (score <= 1) {
        label = "Weak";
        color = "#a04b45";
        pct = "25%";
      } else if (score === 2) {
        label = "Fair";
        color = "#98733a";
        pct = "50%";
      } else if (score === 3 || score === 4) {
        label = "Good";
        color = "#347b74";
        pct = "75%";
      } else {
        label = "Strong";
        color = "#244459";
        pct = "100%";
      }

      strengthFill.style.width = pct;
      strengthFill.style.backgroundColor = color;
      strengthText.textContent = "Strength: " + label;
    });
  }

  // 3. Password Match Validation (Signup & Reset)
  const confirmPwdInput = document.getElementById("confirm_password");
  const pwdMatchError = document.getElementById("pwdMatchError");

  function validatePasswordMatch() {
    if (!pwdInput || !confirmPwdInput) return true;
    if (confirmPwdInput.value && pwdInput.value !== confirmPwdInput.value) {
      if (pwdMatchError) {
        pwdMatchError.textContent = "Passwords do not match";
        pwdMatchError.style.display = "block";
      }
      return false;
    } else {
      if (pwdMatchError) {
        pwdMatchError.style.display = "none";
      }
      return true;
    }
  }

  if (confirmPwdInput) {
    confirmPwdInput.addEventListener("input", validatePasswordMatch);
    if (pwdInput) {
      pwdInput.addEventListener("input", validatePasswordMatch);
    }
  }

  // 4. Form Submit Loading Indicator
  const forms = document.querySelectorAll("form.auth-form");
  forms.forEach(function (form) {
    form.addEventListener("submit", function (e) {
      // Validate password match if present
      if (confirmPwdInput && !validatePasswordMatch()) {
        e.preventDefault();
        confirmPwdInput.focus();
        return;
      }

      const submitBtn = form.querySelector("button[type='submit']");
      if (submitBtn) {
        submitBtn.classList.add("is-loading");
        submitBtn.disabled = true;
        // submit the form programmatically to ensure it posts even with disabled button
        setTimeout(function () {
          form.submit();
        }, 10);
      }
    });
  });
});
