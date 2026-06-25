"""
server.py
=========
Local Flask backend for the web UI. Wraps the existing CryptoEngine
(core/crypto_engine.py) with a small HTTP API so the browser-based
frontend (web/) can drive file encryption/decryption, plus a minimal
local account system (core/auth_db.py) and request rate limiting
(core/rate_limit.py).

The frontend is a real multi-page site (not a single-page app):
    web/index.html     -> Home / landing (FAQ included)
    web/login.html      -> Login
    web/register.html   -> Create account
    web/encrypt.html     -> Encrypt page          (login required)
    web/decrypt.html     -> Decrypt page          (login required)
    web/settings.html    -> Account settings      (login required)
    web/about.html       -> About / how it works

Flask serves these directly by filename (static_url_path=""), and this
file also adds clean extension-less aliases (/encrypt, /decrypt, /login,
etc.) for nicer URLs and so the in-app navigation behaves like a normal
website.

Accounts:
    A single local SQLite database (data/users.db) stores ONLY a login id
    and a salted password hash per account -- see core/auth_db.py for the
    full rationale. There is no email, profile, or personal data anywhere
    in this system.

Rate limiting:
    core/rate_limit.py implements a small in-memory sliding-window limiter.
    It's applied to:
        - login attempts            (per IP+username, brute-force guard)
        - registration attempts     (per IP)
        - encrypt/decrypt API calls (per logged-in session)

This server is meant to run LOCALLY only (127.0.0.1), launched by the
user from a terminal. It is not hardened for exposure to the internet.

Run with:
    python server.py
Then open:
    http://127.0.0.1:5000
"""

from __future__ import annotations

import io
import os
import secrets
import traceback
from functools import wraps

from flask import (
    Flask, request, jsonify, send_file, send_from_directory,
    session, redirect, url_for,
)
from cryptography.exceptions import InvalidTag

from core.crypto_engine import CryptoEngine
from core.qrng import QuantumRandomGenerator
from core.rate_limit import RateLimiter
from core import auth_db
from core.auth_db import UsernameTakenError, InvalidCredentialsError

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(APP_ROOT, "web")
DATA_DIR = os.path.join(APP_ROOT, "data")
SECRET_KEY_PATH = os.path.join(DATA_DIR, "secret.key")

app = Flask(__name__, static_folder=WEB_DIR, static_url_path="")


def _load_or_create_secret_key() -> str:
    """
    Flask session cookies need a stable secret key, or every restart
    invalidates every logged-in session. We generate one on first run
    and persist it locally (it never leaves this machine, same as
    everything else in this app).
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(SECRET_KEY_PATH):
        with open(SECRET_KEY_PATH, "r") as f:
            key = f.read().strip()
            if key:
                return key
    key = secrets.token_hex(32)
    with open(SECRET_KEY_PATH, "w") as f:
        f.write(key)
    return key


app.secret_key = _load_or_create_secret_key()
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)

auth_db.init_db()

engine = CryptoEngine()
qrng_preview = QuantumRandomGenerator()
limiter = RateLimiter()


# ----------------------------------------------------------------------
# Auth helpers
# ----------------------------------------------------------------------
def current_username() -> str | None:
    return session.get("username")


def login_required_page(fn):
    """For HTML page routes: redirect to /login if not authenticated."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_username():
            return redirect(url_for("login_page", next=request.path))
        return fn(*args, **kwargs)
    return wrapper


def login_required_api(fn):
    """For JSON API routes: return 401 JSON if not authenticated."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_username():
            return jsonify({"error": "Not logged in."}), 401
        return fn(*args, **kwargs)
    return wrapper


def rate_limited(key_fn, max_hits: int, window_seconds: int):
    """
    Decorator factory for API routes. key_fn(request) -> str builds the
    bucket key (e.g. IP, or IP+username) so different callers don't share
    a limit.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            key = key_fn(request)
            allowed, retry_after = limiter.hit(key, max_hits, window_seconds)
            if not allowed:
                return jsonify({
                    "error": f"Too many requests. Try again in {retry_after}s."
                }), 429
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def client_ip() -> str:
    return request.headers.get("X-Forwarded-For", request.remote_addr or "unknown")


# ----------------------------------------------------------------------
# Static frontend — multi-page site
# ----------------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory(WEB_DIR, "index.html")


@app.route("/encrypt")
@login_required_page
def encrypt_page():
    return send_from_directory(WEB_DIR, "encrypt.html")


@app.route("/decrypt")
@login_required_page
def decrypt_page():
    return send_from_directory(WEB_DIR, "decrypt.html")


@app.route("/about")
def about_page():
    return send_from_directory(WEB_DIR, "about.html")


@app.route("/login")
def login_page():
    if current_username():
        return redirect(url_for("index"))
    return send_from_directory(WEB_DIR, "login.html")


@app.route("/register")
def register_page():
    if current_username():
        return redirect(url_for("index"))
    return send_from_directory(WEB_DIR, "register.html")


@app.route("/settings")
@login_required_page
def settings_page():
    return send_from_directory(WEB_DIR, "settings.html")


# ----------------------------------------------------------------------
# Auth API
# ----------------------------------------------------------------------
@app.route("/api/me")
def api_me():
    username = current_username()
    if not username:
        return jsonify({"logged_in": False})
    user = auth_db.get_user(username)
    if not user:
        # session referenced an account that no longer exists
        session.clear()
        return jsonify({"logged_in": False})
    return jsonify({"logged_in": True, "user": user})


@app.route("/api/register", methods=["POST"])
@rate_limited(lambda r: f"register:{client_ip()}", max_hits=8, window_seconds=300)
def api_register():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if len(username) < 3:
        return jsonify({"error": "Login id must be at least 3 characters."}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400

    try:
        auth_db.create_user(username, password)
    except UsernameTakenError as e:
        return jsonify({"error": str(e)}), 409
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    session.clear()
    session["username"] = username
    return jsonify({"ok": True, "username": username})


@app.route("/api/login", methods=["POST"])
@rate_limited(lambda r: f"login:{client_ip()}", max_hits=5, window_seconds=60)
def api_login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    # also rate-limit per attempted username, so an attacker can't just
    # round-robin source IPs against one account without limit
    allowed, retry_after = limiter.hit(f"login-user:{username.lower()}", 5, 60)
    if not allowed:
        return jsonify({
            "error": f"Too many attempts for this login id. Try again in {retry_after}s."
        }), 429

    try:
        user = auth_db.verify_user(username, password)
    except InvalidCredentialsError as e:
        return jsonify({"error": str(e)}), 401

    session.clear()
    session["username"] = user["username"]
    return jsonify({"ok": True, "username": user["username"]})


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/settings/change-password", methods=["POST"])
@login_required_api
@rate_limited(lambda r: f"changepw:{client_ip()}", max_hits=5, window_seconds=300)
def api_change_password():
    data = request.get_json(silent=True) or {}
    old_password = data.get("old_password") or ""
    new_password = data.get("new_password") or ""

    if len(new_password) < 8:
        return jsonify({"error": "New password must be at least 8 characters."}), 400

    try:
        auth_db.change_password(current_username(), old_password, new_password)
    except InvalidCredentialsError:
        return jsonify({"error": "Current password is incorrect."}), 401
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify({"ok": True})


# ----------------------------------------------------------------------
# Quantum stage preview (for the live UI animation)
# ----------------------------------------------------------------------
@app.route("/api/qrng/preview", methods=["POST"])
def qrng_preview_endpoint():
    """
    Generates a short burst of real quantum-measured bits so the frontend
    can display genuine quantum randomness ticking by during the
    "quantum stage" of the pipeline -- not a fake/simulated animation.
    Left public (no login) so the header status LED works on every page,
    including the login/register screens.
    """
    try:
        num_bits = int(request.json.get("num_bits", 64)) if request.is_json else 64
        num_bits = max(8, min(num_bits, 256))  # keep requests small & fast
        bits = qrng_preview.get_random_bits(num_bits)
        return jsonify({"bits": bits})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ----------------------------------------------------------------------
# Encrypt
# ----------------------------------------------------------------------
@app.route("/api/encrypt", methods=["POST"])
@login_required_api
@rate_limited(lambda r: f"encrypt:{current_username() or client_ip()}", max_hits=20, window_seconds=60)
def encrypt_endpoint():
    uploaded = request.files.get("file")
    password = request.form.get("password", "")

    if not uploaded or uploaded.filename == "":
        return jsonify({"error": "No file was provided."}), 400
    if not password:
        return jsonify({"error": "Password is required."}), 400

    try:
        data = uploaded.read()
        blob = engine.encrypt_bytes(data, password)

        output_name = uploaded.filename + ".qaes"
        return send_file(
            io.BytesIO(blob),
            as_attachment=True,
            download_name=output_name,
            mimetype="application/octet-stream",
        )
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Encryption failed: {e}"}), 500


# ----------------------------------------------------------------------
# Decrypt
# ----------------------------------------------------------------------
@app.route("/api/decrypt", methods=["POST"])
@login_required_api
@rate_limited(lambda r: f"decrypt:{current_username() or client_ip()}", max_hits=20, window_seconds=60)
def decrypt_endpoint():
    uploaded = request.files.get("file")
    password = request.form.get("password", "")

    if not uploaded or uploaded.filename == "":
        return jsonify({"error": "No file was provided."}), 400
    if not password:
        return jsonify({"error": "Password is required."}), 400

    try:
        blob = uploaded.read()
        plaintext = engine.decrypt_bytes(blob, password)

        output_name = uploaded.filename
        if output_name.endswith(".qaes"):
            output_name = output_name[:-len(".qaes")]
        else:
            output_name = "decrypted_" + output_name

        return send_file(
            io.BytesIO(plaintext),
            as_attachment=True,
            download_name=output_name,
            mimetype="application/octet-stream",
        )
    except InvalidTag:
        return jsonify({"error": "Wrong password, or the file was corrupted or tampered with."}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Decryption failed: {e}"}), 500


if __name__ == "__main__":
    print("Quantum-Assisted AES Encryptor running at http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)
