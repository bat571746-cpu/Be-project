"""
app_window.py
=============
Tkinter desktop GUI for the Quantum-Assisted AES Encryptor.

Two tabs:
    - Text tab: type/paste text, encrypt to a Base64 blob (or decrypt one back)
    - File tab: pick any file, encrypt it to a .qaes file (or decrypt one back)

The GUI is intentionally thin: all crypto logic lives in core/crypto_engine.py.
This file only handles user interaction, validation, and feedback messages.
"""

from __future__ import annotations

import base64
import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

from cryptography.exceptions import InvalidTag

from core.crypto_engine import CryptoEngine

# ---- Visual tokens (kept consistent across the whole app) ----
BG = "#10151c"            # deep near-black ink background
PANEL = "#171f29"         # slightly lifted panel
ACCENT = "#5ee0c8"        # quantum teal accent
ACCENT_DIM = "#2c7c6c"
TEXT_PRIMARY = "#e8edf2"
TEXT_MUTED = "#7e8b99"
DANGER = "#e0615e"
FONT_HEAD = ("Segoe UI Semibold", 16)
FONT_BODY = ("Segoe UI", 10)
FONT_MONO = ("Consolas", 10)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Quantum-Assisted AES Encryptor")
        self.geometry("760x560")
        self.minsize(680, 480)
        self.configure(bg=BG)

        self.engine = CryptoEngine()

        self._build_style()
        self._build_layout()

    # ------------------------------------------------------------------
    def _build_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=TEXT_PRIMARY, font=FONT_BODY)
        style.configure("Muted.TLabel", background=BG, foreground=TEXT_MUTED, font=FONT_BODY)
        style.configure("Header.TLabel", background=BG, foreground=TEXT_PRIMARY, font=FONT_HEAD)
        style.configure("Status.TLabel", background=BG, foreground=ACCENT, font=FONT_BODY)

        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=PANEL, foreground=TEXT_MUTED,
                         padding=(16, 8), font=FONT_BODY)
        style.map("TNotebook.Tab",
                  background=[("selected", ACCENT_DIM)],
                  foreground=[("selected", TEXT_PRIMARY)])

        style.configure("Accent.TButton", background=ACCENT, foreground="#0a0f14",
                         font=("Segoe UI Semibold", 10), padding=(14, 8), borderwidth=0)
        style.map("Accent.TButton", background=[("active", "#7be8d4")])

        style.configure("Ghost.TButton", background=PANEL, foreground=TEXT_PRIMARY,
                         font=FONT_BODY, padding=(14, 8), borderwidth=1)
        style.map("Ghost.TButton", background=[("active", "#202b38")])

        style.configure("TEntry", fieldbackground=PANEL, foreground=TEXT_PRIMARY,
                         insertcolor=TEXT_PRIMARY, borderwidth=0, padding=8)

    # ------------------------------------------------------------------
    def _build_layout(self):
        header = ttk.Frame(self, style="TFrame", padding=(20, 18, 20, 8))
        header.pack(fill="x")
        ttk.Label(header, text="Quantum-Assisted AES Encryptor",
                  style="Header.TLabel").pack(anchor="w")
        ttk.Label(header,
                  text="Layer 1: Qiskit quantum RNG  →  Layer 2: AES-256-GCM",
                  style="Muted.TLabel").pack(anchor="w", pady=(2, 0))

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=20, pady=12)

        text_tab = ttk.Frame(notebook, style="TFrame", padding=16)
        file_tab = ttk.Frame(notebook, style="TFrame", padding=16)
        notebook.add(text_tab, text="  Text  ")
        notebook.add(file_tab, text="  File  ")

        self._build_text_tab(text_tab)
        self._build_file_tab(file_tab)

        self.status_var = tk.StringVar(value="Ready.")
        status_bar = ttk.Frame(self, style="TFrame", padding=(20, 4, 20, 14))
        status_bar.pack(fill="x")
        ttk.Label(status_bar, textvariable=self.status_var, style="Status.TLabel").pack(anchor="w")

    # ------------------------------------------------------------------
    # TEXT TAB
    # ------------------------------------------------------------------
    def _build_text_tab(self, parent):
        ttk.Label(parent, text="Password", style="TLabel").pack(anchor="w")
        self.text_password = ttk.Entry(parent, show="•")
        self.text_password.pack(fill="x", pady=(4, 12))

        ttk.Label(parent, text="Text", style="TLabel").pack(anchor="w")
        self.text_input = scrolledtext.ScrolledText(
            parent, height=8, bg=PANEL, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
            font=FONT_MONO, borderwidth=0, wrap="word"
        )
        self.text_input.pack(fill="both", expand=True, pady=(4, 12))

        btn_row = ttk.Frame(parent, style="TFrame")
        btn_row.pack(fill="x", pady=(0, 12))
        ttk.Button(btn_row, text="Encrypt", style="Accent.TButton",
                   command=self._on_encrypt_text).pack(side="left")
        ttk.Button(btn_row, text="Decrypt", style="Ghost.TButton",
                   command=self._on_decrypt_text).pack(side="left", padx=(10, 0))
        ttk.Button(btn_row, text="Copy Output", style="Ghost.TButton",
                   command=self._on_copy_text_output).pack(side="left", padx=(10, 0))
        ttk.Button(btn_row, text="Clear", style="Ghost.TButton",
                   command=self._on_clear_text).pack(side="right")

        ttk.Label(parent, text="Output", style="TLabel").pack(anchor="w")
        self.text_output = scrolledtext.ScrolledText(
            parent, height=6, bg=PANEL, fg=ACCENT, insertbackground=TEXT_PRIMARY,
            font=FONT_MONO, borderwidth=0, wrap="word"
        )
        self.text_output.pack(fill="both", expand=True, pady=(4, 0))

    def _on_encrypt_text(self):
        password = self.text_password.get()
        plaintext = self.text_input.get("1.0", "end-1c")

        if not password:
            messagebox.showwarning("Missing password", "Please enter a password.")
            return
        if not plaintext:
            messagebox.showwarning("Missing text", "Please enter text to encrypt.")
            return

        self._set_status("Generating quantum randomness and encrypting…")

        def work():
            try:
                blob = self.engine.encrypt_text(plaintext, password)
                encoded = base64.b64encode(blob).decode("ascii")
                self._set_output(self.text_output, encoded)
                self._set_status("Encrypted successfully.")
            except Exception as e:
                self._set_status("Encryption failed.")
                messagebox.showerror("Encryption error", str(e))

        threading.Thread(target=work, daemon=True).start()

    def _on_decrypt_text(self):
        password = self.text_password.get()
        encoded = self.text_input.get("1.0", "end-1c").strip()

        if not password:
            messagebox.showwarning("Missing password", "Please enter a password.")
            return
        if not encoded:
            messagebox.showwarning("Missing text", "Please paste encrypted Base64 text to decrypt.")
            return

        self._set_status("Decrypting…")

        def work():
            try:
                blob = base64.b64decode(encoded)
                plaintext = self.engine.decrypt_text(blob, password)
                self._set_output(self.text_output, plaintext)
                self._set_status("Decrypted successfully.")
            except InvalidTag:
                self._set_status("Decryption failed.")
                messagebox.showerror("Decryption error",
                                      "Wrong password, or the data was corrupted/tampered with.")
            except Exception as e:
                self._set_status("Decryption failed.")
                messagebox.showerror("Decryption error", str(e))

        threading.Thread(target=work, daemon=True).start()

    def _on_copy_text_output(self):
        content = self.text_output.get("1.0", "end-1c")
        if content:
            self.clipboard_clear()
            self.clipboard_append(content)
            self._set_status("Output copied to clipboard.")

    def _on_clear_text(self):
        self.text_input.delete("1.0", "end")
        self.text_output.delete("1.0", "end")
        self.text_password.delete(0, "end")
        self._set_status("Cleared.")

    # ------------------------------------------------------------------
    # FILE TAB
    # ------------------------------------------------------------------
    def _build_file_tab(self, parent):
        ttk.Label(parent, text="Password", style="TLabel").pack(anchor="w")
        self.file_password = ttk.Entry(parent, show="•")
        self.file_password.pack(fill="x", pady=(4, 16))

        file_row = ttk.Frame(parent, style="TFrame")
        file_row.pack(fill="x", pady=(0, 16))
        ttk.Label(file_row, text="Selected file:", style="TLabel").pack(side="left")
        self.file_path_var = tk.StringVar(value="No file selected")
        ttk.Label(file_row, textvariable=self.file_path_var, style="Muted.TLabel").pack(
            side="left", padx=(8, 0))

        ttk.Button(parent, text="Choose File…", style="Ghost.TButton",
                   command=self._on_choose_file).pack(anchor="w", pady=(0, 20))

        btn_row = ttk.Frame(parent, style="TFrame")
        btn_row.pack(fill="x", pady=(0, 16))
        ttk.Button(btn_row, text="Encrypt File", style="Accent.TButton",
                   command=self._on_encrypt_file).pack(side="left")
        ttk.Button(btn_row, text="Decrypt File", style="Ghost.TButton",
                   command=self._on_decrypt_file).pack(side="left", padx=(10, 0))

        ttk.Label(parent, text="Activity log", style="TLabel").pack(anchor="w")
        self.file_log = scrolledtext.ScrolledText(
            parent, height=12, bg=PANEL, fg=TEXT_PRIMARY, insertbackground=TEXT_PRIMARY,
            font=FONT_MONO, borderwidth=0, wrap="word", state="disabled"
        )
        self.file_log.pack(fill="both", expand=True, pady=(4, 0))

        self.selected_file_path = None

    def _on_choose_file(self):
        path = filedialog.askopenfilename(title="Select a file")
        if path:
            self.selected_file_path = path
            self.file_path_var.set(os.path.basename(path))
            self._log_file(f"Selected: {path}")

    def _on_encrypt_file(self):
        password = self.file_password.get()
        if not password:
            messagebox.showwarning("Missing password", "Please enter a password.")
            return
        if not self.selected_file_path:
            messagebox.showwarning("No file", "Please choose a file first.")
            return

        default_name = os.path.basename(self.selected_file_path) + ".qaes"
        output_path = filedialog.asksaveasfilename(
            title="Save encrypted file as",
            initialfile=default_name,
            defaultextension=".qaes",
            filetypes=[("Quantum-AES encrypted file", "*.qaes"), ("All files", "*.*")],
        )
        if not output_path:
            return

        self._set_status("Generating quantum randomness and encrypting file…")
        self._log_file(f"Encrypting {self.selected_file_path} …")

        def work():
            try:
                self.engine.encrypt_file(self.selected_file_path, output_path, password)
                self._log_file(f"Done. Saved encrypted file to: {output_path}")
                self._set_status("File encrypted successfully.")
            except Exception as e:
                self._log_file(f"ERROR: {e}")
                self._set_status("Encryption failed.")
                messagebox.showerror("Encryption error", str(e))

        threading.Thread(target=work, daemon=True).start()

    def _on_decrypt_file(self):
        password = self.file_password.get()
        if not password:
            messagebox.showwarning("Missing password", "Please enter a password.")
            return
        if not self.selected_file_path:
            messagebox.showwarning("No file", "Please choose a .qaes file first.")
            return

        default_name = os.path.basename(self.selected_file_path).replace(".qaes", "")
        output_path = filedialog.asksaveasfilename(
            title="Save decrypted file as",
            initialfile=default_name,
        )
        if not output_path:
            return

        self._set_status("Decrypting file…")
        self._log_file(f"Decrypting {self.selected_file_path} …")

        def work():
            try:
                self.engine.decrypt_file(self.selected_file_path, output_path, password)
                self._log_file(f"Done. Saved decrypted file to: {output_path}")
                self._set_status("File decrypted successfully.")
            except InvalidTag:
                self._log_file("ERROR: wrong password or corrupted/tampered file.")
                self._set_status("Decryption failed.")
                messagebox.showerror("Decryption error",
                                      "Wrong password, or the file was corrupted/tampered with.")
            except Exception as e:
                self._log_file(f"ERROR: {e}")
                self._set_status("Decryption failed.")
                messagebox.showerror("Decryption error", str(e))

        threading.Thread(target=work, daemon=True).start()

    def _log_file(self, message: str):
        self.file_log.configure(state="normal")
        self.file_log.insert("end", message + "\n")
        self.file_log.see("end")
        self.file_log.configure(state="disabled")

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------
    def _set_status(self, message: str):
        self.status_var.set(message)

    def _set_output(self, widget, text: str):
        widget.delete("1.0", "end")
        widget.insert("1.0", text)


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
