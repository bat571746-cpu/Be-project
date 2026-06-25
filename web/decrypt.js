/* =========================================================================
   decrypt.js
   Logic for the dedicated Decrypt page. Talks to the local Flask backend
   (server.py -> /api/decrypt) which runs core/crypto_engine.py to reverse
   the quantum-seed + AES-256-GCM pipeline using the seed stored in the
   file's header (no new quantum randomness is generated on decrypt).
   ========================================================================= */

const state = { file: null };

// ---- element refs ----
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const dropzoneText = document.getElementById("dropzoneText");
const dropzoneMeta = document.getElementById("dropzoneMeta");

const passwordInput = document.getElementById("passwordInput");
const togglePassword = document.getElementById("togglePassword");

const runBtn = document.getElementById("runBtn");
const runBtnLabel = document.getElementById("runBtnLabel");

const resultBox = document.getElementById("resultBox");
const resultText = document.getElementById("resultText");
const downloadLink = document.getElementById("downloadLink");

const stageFile = document.getElementById("stageFile");
const stageQuantum = document.getElementById("stageQuantum");
const stageAes = document.getElementById("stageAes");
const stageOutput = document.getElementById("stageOutput");
const trace1 = document.getElementById("trace1");
const trace2 = document.getElementById("trace2");
const trace3 = document.getElementById("trace3");
const bitstream = document.getElementById("bitstream");
const fileStageMeta = document.getElementById("fileStageMeta");
const outputStageMeta = document.getElementById("outputStageMeta");

// ---- file selection ----
dropzone.addEventListener("click", () => fileInput.click());
dropzone.addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    fileInput.click();
  }
});
fileInput.addEventListener("change", () => {
  if (fileInput.files.length) setFile(fileInput.files[0]);
});

["dragenter", "dragover"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.add("drag-over");
  })
);
["dragleave", "drop"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.remove("drag-over");
  })
);
dropzone.addEventListener("drop", (e) => {
  const f = e.dataTransfer.files[0];
  if (f) setFile(f);
});

function setFile(file) {
  state.file = file;
  dropzone.classList.add("has-file");
  dropzoneText.textContent = file.name;
  dropzoneMeta.textContent = formatBytes(file.size);
  fileStageMeta.textContent = formatBytes(file.size);
  updateRunButton();
}

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(2) + " MB";
}

// ---- password visibility ----
togglePassword.addEventListener("click", () => {
  const isHidden = passwordInput.type === "password";
  passwordInput.type = isHidden ? "text" : "password";
});

// ---- run button enable/disable ----
function updateRunButton() {
  runBtn.disabled = !(state.file && passwordInput.value.length > 0);
}
passwordInput.addEventListener("input", updateRunButton);

// ---- pipeline visual state ----
function resetPipeline() {
  [stageFile, stageQuantum, stageAes, stageOutput].forEach((s) => {
    s.classList.remove("active", "done");
  });
  [trace1, trace2, trace3].forEach((t) => t.classList.remove("active"));
  bitstream.classList.remove("visible");
  bitstream.textContent = "";
  outputStageMeta.textContent = "—";
  resultBox.hidden = true;
  downloadLink.hidden = true;
}

function setStage(el, status) {
  el.classList.remove("active", "done");
  if (status) el.classList.add(status);
}

// ---- main run action ----
runBtn.addEventListener("click", async () => {
  if (!state.file || !passwordInput.value) return;

  resetPipeline();
  downloadLink.hidden = true;
  downloadLink.removeAttribute("href");
  runBtn.disabled = true;
  runBtn.classList.add("busy");
  runBtnLabel.textContent = "DECRYPTING…";

  // Stage 1: encrypted file
  setStage(stageFile, "done");
  trace1.classList.add("active");
  await wait(250);

  // Stage 2: key derivation (reading stored seed + re-deriving key)
  setStage(stageQuantum, "active");
  bitstream.classList.add("visible");
  bitstream.textContent = "reading stored quantum seed from file header…";
  await wait(700);

  const formData = new FormData();
  formData.append("file", state.file);
  formData.append("password", passwordInput.value);

  try {
    const res = await fetch("/api/decrypt", { method: "POST", body: formData });

    setStage(stageQuantum, "done");
    bitstream.classList.remove("visible");
    trace2.classList.add("active");
    await wait(200);

    if (!res.ok) {
      const errData = await res.json().catch(() => ({ error: "Unknown error." }));
      throw new Error(errData.error || "Decryption failed.");
    }

    // Stage 3: aes (only reached once the backend confirms success)
    setStage(stageAes, "active");
    await wait(500);

    const blob = await res.blob();
    const disposition = res.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename="?([^"]+)"?/);
    const outName = match ? match[1] : "decrypted_output";

    setStage(stageAes, "done");
    trace3.classList.add("active");
    await wait(200);

    // Stage 4: output
    setStage(stageOutput, "done");
    outputStageMeta.textContent = formatBytes(blob.size);

    const url = URL.createObjectURL(blob);
    downloadLink.href = url;
    downloadLink.download = outName;
    downloadLink.hidden = false;
    downloadLink.textContent = `↓ download ${outName}`;

    resultBox.hidden = false;
    resultBox.classList.remove("error");
    resultText.textContent = "Decryption complete. Integrity verified.";

  } catch (err) {
    bitstream.classList.remove("visible");
    [stageQuantum, stageAes].forEach((s) => s.classList.remove("active"));
    resultBox.hidden = false;
    resultBox.classList.add("error");
    resultText.textContent = err.message || "Something went wrong.";
    downloadLink.hidden = true;
  } finally {
    runBtn.disabled = false;
    runBtn.classList.remove("busy");
    runBtnLabel.textContent = "DECRYPT FILE";
    updateRunButton();
  }
});

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
