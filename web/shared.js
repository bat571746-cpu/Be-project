/* =========================================================================
   shared.js
   Runs on every page. Handles:
     - the backend connection indicator (the LED in the header)
     - applying the saved theme (dark/light) before paint
     - auth-aware navigation (Login/Register vs account/Settings/Logout)
   Kept separate from page-specific scripts (encrypt.js, decrypt.js, ...)
   so every page gets this behaviour for free just by including the file.
   ========================================================================= */

// ---- theme (applied immediately so there's no flash of the wrong theme) ----
(function applyStoredTheme() {
  const saved = localStorage.getItem("qaes-theme");
  if (saved === "light") {
    document.documentElement.setAttribute("data-theme", "light");
  }
})();

// ---- connection status LED ----
(function () {
  const connLed = document.getElementById("connLed");
  const connLabel = document.getElementById("connLabel");

  if (!connLed || !connLabel) return; // page doesn't have a status LED

  async function checkConnection() {
    try {
      const res = await fetch("/api/qrng/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ num_bits: 8 }),
      });
      if (res.ok) {
        connLed.classList.add("online");
        connLabel.textContent = "ONLINE";
      } else {
        throw new Error();
      }
    } catch {
      connLed.classList.remove("online");
      connLabel.textContent = "OFFLINE";
    }
  }

  checkConnection();
})();

// ---- auth-aware navigation ----
(function () {
  const navLogin = document.getElementById("navLoginLink");
  const navRegister = document.getElementById("navRegisterLink");
  const navAccount = document.getElementById("navAccountLink");
  const navLogout = document.getElementById("navLogoutLink");

  if (!navLogin && !navAccount) return; // page doesn't render the account cluster

  async function refreshAuthNav() {
    try {
      const res = await fetch("/api/me");
      const data = await res.json();

      const loggedIn = !!data.logged_in;

      if (navLogin) navLogin.hidden = loggedIn;
      if (navRegister) navRegister.hidden = loggedIn;
      if (navAccount) {
        navAccount.hidden = !loggedIn;
        if (loggedIn && data.user) {
          navAccount.textContent = data.user.username.toUpperCase();
        }
      }
      if (navLogout) navLogout.hidden = !loggedIn;
    } catch {
      /* backend not reachable yet -- leave nav in its default (logged-out) state */
    }
  }

  if (navLogout) {
    navLogout.addEventListener("click", async (e) => {
      e.preventDefault();
      try {
        await fetch("/api/logout", { method: "POST" });
      } catch {
        /* ignore -- redirect home regardless */
      }
      window.location.href = "index.html";
    });
  }

  refreshAuthNav();
})();
