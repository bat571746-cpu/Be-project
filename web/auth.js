/* =========================================================================
   auth.js
   Handles both login.html and register.html — whichever form is present
   on the page determines which branch runs. Talks to /api/login and
   /api/register (server.py), which set a session cookie on success.
   ========================================================================= */

const authError = document.getElementById("authError");
const submitBtn = document.getElementById("submitBtn");
const submitLabel = document.getElementById("submitLabel");

function showAuthError(message) {
  authError.textContent = message;
  authError.hidden = false;
}
function clearAuthError() {
  authError.hidden = true;
  authError.textContent = "";
}

function paramFromQuery(name) {
  return new URLSearchParams(window.location.search).get(name);
}

// ---- LOGIN ----
const loginForm = document.getElementById("loginForm");
if (loginForm) {
  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearAuthError();

    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value;

    submitBtn.disabled = true;
    submitBtn.classList.add("busy");
    submitLabel.textContent = "LOGGING IN…";

    try {
      const res = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || "Login failed.");
      }

      const next = paramFromQuery("next") || "index.html";
      window.location.href = next.startsWith("/") ? next.slice(1) || "index.html" : next;
    } catch (err) {
      showAuthError(err.message || "Something went wrong.");
    } finally {
      submitBtn.disabled = false;
      submitBtn.classList.remove("busy");
      submitLabel.textContent = "LOG IN";
    }
  });
}

// ---- REGISTER ----
const registerForm = document.getElementById("registerForm");
if (registerForm) {
  registerForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearAuthError();

    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value;
    const confirmPassword = document.getElementById("confirmPassword").value;

    if (password !== confirmPassword) {
      showAuthError("Passwords do not match.");
      return;
    }

    submitBtn.disabled = true;
    submitBtn.classList.add("busy");
    submitLabel.textContent = "CREATING…";

    try {
      const res = await fetch("/api/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || "Registration failed.");
      }

      window.location.href = "index.html";
    } catch (err) {
      showAuthError(err.message || "Something went wrong.");
    } finally {
      submitBtn.disabled = false;
      submitBtn.classList.remove("busy");
      submitLabel.textContent = "CREATE ACCOUNT";
    }
  });
}
