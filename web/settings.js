/* =========================================================================
   settings.js
   Logic for the Settings page: account info, theme toggle, password
   change, logout. Theme preference is stored in localStorage (this is a
   real local web app served by Flask, not a Claude artifact, so
   browser storage is appropriate here).
   ========================================================================= */

// ---- load account info ----
(async function loadAccount() {
  try {
    const res = await fetch("/api/me");
    const data = await res.json();
    if (!data.logged_in) {
      window.location.href = "login.html?next=/settings";
      return;
    }
    document.getElementById("statUsername").textContent = data.user.username;
    document.getElementById("statCreated").textContent = formatTimestamp(data.user.created_at);
    document.getElementById("statLastLogin").textContent = formatTimestamp(data.user.last_login);
  } catch {
    /* leave placeholders if the backend is unreachable */
  }
})();

function formatTimestamp(iso) {
  if (!iso) return "this session";
  try {
    const d = new Date(iso);
    return d.toLocaleString();
  } catch {
    return iso;
  }
}

// ---- theme toggle ----
const themeToggle = document.getElementById("themeToggle");
const isLight = document.documentElement.getAttribute("data-theme") === "light";
themeToggle.checked = isLight;

themeToggle.addEventListener("change", () => {
  if (themeToggle.checked) {
    document.documentElement.setAttribute("data-theme", "light");
    localStorage.setItem("qaes-theme", "light");
  } else {
    document.documentElement.removeAttribute("data-theme");
    localStorage.setItem("qaes-theme", "dark");
  }
});

// ---- change password ----
const changePasswordForm = document.getElementById("changePasswordForm");
const passwordFeedback = document.getElementById("passwordFeedback");
const changePasswordBtn = document.getElementById("changePasswordBtn");

function showFeedback(message, isError) {
  passwordFeedback.textContent = message;
  passwordFeedback.hidden = false;
  passwordFeedback.classList.toggle("error", isError);
  passwordFeedback.classList.toggle("ok", !isError);
}

changePasswordForm.addEventListener("submit", async (e) => {
  e.preventDefault();

  const oldPassword = document.getElementById("oldPassword").value;
  const newPassword = document.getElementById("newPassword").value;
  const confirmNewPassword = document.getElementById("confirmNewPassword").value;

  if (newPassword !== confirmNewPassword) {
    showFeedback("New passwords do not match.", true);
    return;
  }

  changePasswordBtn.disabled = true;
  changePasswordBtn.textContent = "UPDATING…";

  try {
    const res = await fetch("/api/settings/change-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
    });
    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.error || "Could not update password.");
    }

    showFeedback("Password updated.", false);
    changePasswordForm.reset();
  } catch (err) {
    showFeedback(err.message || "Something went wrong.", true);
  } finally {
    changePasswordBtn.disabled = false;
    changePasswordBtn.textContent = "UPDATE PASSWORD";
  }
});

// ---- logout ----
document.getElementById("settingsLogoutBtn").addEventListener("click", async () => {
  try {
    await fetch("/api/logout", { method: "POST" });
  } catch {
    /* ignore -- redirect regardless */
  }
  window.location.href = "index.html";
});
