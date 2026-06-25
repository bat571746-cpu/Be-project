# Quantum-Assisted AES Encryptor

A desktop encryption tool that combines **quantum random number generation
(QRNG)** via Qiskit with **AES-256-GCM** encryption. This is a hybrid
"double encryption" scheme: the AES key is derived from BOTH your password
AND a quantum-generated random seed, so security depends on two independent
secrets.

The project now ships with **two interchangeable frontends** on top of the
same crypto core:

| Frontend | Tech | Run with |
|---|---|---|
| **Web Console** (recommended) | HTML/CSS/JS + local Flask backend | `python server.py` |
| Desktop GUI | Tkinter | `python main.py` |

Both call the exact same `core/crypto_engine.py` — neither reimplements any
crypto logic, so results from one are fully compatible with the other (a
file encrypted in the web console can be decrypted in the Tkinter app, and
vice versa).

## Architecture

```
quantum_aes_encryptor/
├── main.py                  # Entry point - launches the Tkinter desktop GUI
├── server.py                 # Entry point - launches the Flask web backend
├── requirements.txt
├── core/
│   ├── qrng.py               # Qiskit quantum random number generator
│   ├── aes_cipher.py         # AES-256-GCM encryption/decryption
│   ├── crypto_engine.py      # Combines password + quantum seed -> AES key (PBKDF2)
│   ├── auth_db.py            # Local SQLite account store (login id + password hash only)
│   └── rate_limit.py         # In-memory sliding-window rate limiter
├── data/                      # Created automatically at runtime
│   ├── users.db                # SQLite database of accounts (login id + hash only)
│   └── secret.key              # Flask session signing key (generated on first run)
├── web/                       # Web Console frontend (served by server.py)
│   ├── index.html             # Home: hero, pipeline preview, features, FAQ
│   ├── encrypt.html / encrypt.js     # Encrypt page (login required)
│   ├── decrypt.html / decrypt.js     # Decrypt page (login required)
│   ├── login.html / register.html    # Auth pages
│   ├── settings.html / settings.js   # Account info, theme toggle, change password
│   ├── about.html             # Technical deep-dive + its own FAQ
│   ├── auth.js                 # Shared login/register form logic
│   ├── faq.js                   # Homepage FAQ accordion behaviour
│   ├── shared.js                # Connection LED, theme bootstrap, auth-aware nav
│   └── style.css                # "Lab instrument panel" visual design
├── gui/
│   └── app_window.py         # Tkinter desktop GUI (Text tab + File tab)
└── tests/
    └── test_crypto_engine.py # Round-trip, tamper-detection, QRNG sanity tests
```

**How "double encryption" works here:**
1. `qrng.py` generates a random seed using a real quantum circuit (Hadamard
   gate + measurement) run on Qiskit's Aer simulator.
2. `crypto_engine.py` combines your password + the quantum seed through
   PBKDF2-HMAC-SHA256 (390,000 iterations) to derive the actual AES-256 key.
3. `aes_cipher.py` uses that key to encrypt your data with AES-256-GCM
   (authenticated encryption — detects tampering).

---

## Setup on Windows (PowerShell / Command Prompt)

### 1. Install Python
Make sure you have **Python 3.10+** installed. Check with:
```powershell
python --version
```
If not installed, get it from https://www.python.org/downloads/ (tick "Add
Python to PATH" during install).

### 2. Get the project onto your machine
Copy the `quantum_aes_encryptor` folder to your PC, then open a terminal
(PowerShell or Command Prompt) inside it:
```powershell
cd path\to\quantum_aes_encryptor
```

### 3. Create a virtual environment (recommended)
```powershell
python -m venv venv
venv\Scripts\activate
```
You should see `(venv)` appear at the start of your prompt.

### 4. Install dependencies
```powershell
python -m pip install -r requirements.txt
```
This installs `qiskit`, `qiskit-aer`, `cryptography`, and `flask`. It may
take a couple of minutes the first time.

### 5. Run the tests (optional but recommended)
```powershell
python tests\test_crypto_engine.py
```
You should see 5 `[PASS]` lines and "All tests passed."

### 6. Launch the app

**Web Console (recommended — the new custom UI):**
```powershell
python server.py
```
Then open **http://127.0.0.1:5000** in your browser.

**Desktop GUI (Tkinter, still available):**
```powershell
python main.py
```

---

## Usage — Web Console

The Web Console shows the encryption pipeline as a literal signal path:
**FILE → QUANTUM STAGE → AES STAGE → OUTPUT**. Each stage lights up amber
while active and turns green once complete. The Quantum Stage panel streams
*real* measured qubit bits live from the backend while the seed is generated
— this is not a fake animation, it's the actual randomness being pulled
over the API in real time.

1. Click **ENCRYPT** or **DECRYPT** at the top to choose mode.
2. Drop a file onto the dropzone, or click it to browse.
3. Enter a passphrase.
4. Click **ENCRYPT FILE** / **DECRYPT FILE** and watch the pipeline run.
5. Click the **download** link that appears once it completes.

Encrypted files are saved with a `.qaes` extension. Decrypting a `.qaes`
file restores the original filename automatically.

## Accounts, rate limiting & settings

The Encrypt and Decrypt pages now require a local account:

- **Register** (`/register`) with a login id (3+ chars) and a password
  (8+ chars). **Nothing else is collected or stored** — no email, no name.
  Only the login id and a salted password hash go into `data/users.db`.
- **Log in** (`/login`) to start a session (a signed cookie, valid until
  you log out or the server's secret key changes).
- **Settings** (`/settings`, once logged in) shows your account info
  (login id, created date, last login), lets you toggle a **light/dark
  theme** (saved in your browser), change your password, and log out.
- **Rate limiting** is enforced server-side (`core/rate_limit.py`):
  login attempts are capped per IP and per login id (5 per 60s),
  registration is capped per IP (8 per 5 min), and encrypt/decrypt calls
  are capped per session (20 per 60s) — all to blunt brute-force guessing
  and runaway requests. Hitting a limit returns a `429` with a
  "try again in Ns" message shown directly in the UI.

The homepage also has a dedicated **FAQ** section (separate from the more
technical FAQ on the About page) covering accounts, data storage, and
rate limiting, presented as an accordion.



### Text tab
1. Enter a password.
2. Type/paste text into the "Text" box.
3. Click **Encrypt** — a Base64-encoded encrypted blob appears in "Output".
4. To decrypt: paste that Base64 blob back into the "Text" box, enter the
   same password, click **Decrypt**.

### File tab
1. Enter a password.
2. Click **Choose File…** and select any file.
3. Click **Encrypt File** — choose where to save the `.qaes` output file.
4. To decrypt: select the `.qaes` file, enter the same password, click
   **Decrypt File**, choose where to save the recovered original file.

---

## Notes for your project report / viva

- **Why PBKDF2 with both password and quantum seed?** This is the "hybrid"
  design: an attacker needs both the password (something you know) and the
  quantum seed (stored alongside the ciphertext, like a salt) to derive the
  key. Neither alone is sufficient — but more importantly, the quantum seed
  ensures every encryption uses fresh, high-entropy randomness even if a
  weak password is reused.
- **Why AES-GCM and not CBC?** GCM is authenticated encryption — it detects
  tampering automatically (try the `test_tampered_ciphertext_detected` test).
  CBC alone has no integrity check.
- **Why simulate the quantum circuit instead of using real quantum hardware?**
  Real IBM Quantum hardware requires an account and has queue wait times,
  which isn't practical for a responsive desktop app. The Aer simulator
  runs the exact same circuit logic locally. `core/qrng.py` has comments
  showing how to swap in real hardware via `qiskit_ibm_runtime` if you want
  to demonstrate that as a stretch goal.
- **Where's the "from scratch" part?** The quantum random number generation
  pipeline (circuit design, bit extraction, byte packing, rejection sampling
  for unbiased integers) is built from scratch on top of Qiskit's primitives.
  AES itself uses the audited `cryptography` library rather than a hand-rolled
  implementation, which is standard practice — real-world systems never
  reimplement AES's S-boxes/round logic themselves either.
- **Why a Flask backend instead of doing crypto in the browser?** Qiskit is
  a Python library with no JavaScript equivalent, so the quantum circuit
  simulation must run server-side. The browser only handles file
  upload/download and the visual pipeline; all cryptography happens in
  `core/`, identically to the desktop app.

## Troubleshooting

- **`ModuleNotFoundError: No module named 'qiskit'` (or 'flask')** — you
  forgot to activate the venv or run `python -m pip install -r requirements.txt`.
- **`pip` not recognized** — use `python -m pip install -r requirements.txt`
  instead of `pip install ...` (this routes through Python directly,
  sidestepping PATH issues).
- **Web Console shows "OFFLINE" in the top right** — the page loaded but
  can't reach the backend. Make sure `server.py` is still running in your
  terminal and that you opened `http://127.0.0.1:5000` (not a `file://` path).
- **App window doesn't appear (Tkinter)** — Tkinter ships with Python on
  Windows by default, but if missing, reinstall Python and ensure "tcl/tk
  and IDLE" is checked during setup.
- **Decryption says "wrong password"** — double check you're using the exact
  same password used to encrypt; there's no password recovery by design.

#   B e - p r o j e c t  
 