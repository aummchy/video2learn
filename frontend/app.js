/* Video2Learn frontend — upload, polling, timeline editor, preview overlay */

const $ = (sel) => document.querySelector(sel);
const api = {
  upload: "/api/videos",
  status: (id) => `/api/videos/${id}`,
  media: (id) => `/api/videos/${id}/media`,
  transcript: (id) => `/api/videos/${id}/transcript`,
  questions: (id) => `/api/videos/${id}/questions`,
  regenerate: (id) => `/api/videos/${id}/regenerate`,
  export: (id) => `/api/videos/${id}/export`,
};

const state = {
  jobId: null,
  status: null,
  questions: [],
  transcript: [],
  editingId: null, // question id or null for new
  answered: new Set(),
  pollTimer: null,
};

const STAGE_ORDER = ["upload", "transcribe", "generate", "ready"];
const STAGE_DETAIL = {
  upload: "Validating video…",
  transcribe: "Extracting audio and transcribing with Whisper… (first run downloads the model)",
  generate: "Asking AI to generate timestamped questions…",
  ready: "Done — review the questions below.",
};

/* ---------- helpers ---------- */

function fmtTime(sec) {
  sec = Math.max(0, Math.round(sec));
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function show(el) {
  el.classList.remove("hidden");
}
function hide(el) {
  el.classList.add("hidden");
}

async function jsonFetch(url, opts = {}) {
  const res = await fetch(url, opts);
  let data = null;
  try {
    data = await res.json();
  } catch (_) {
    /* non-json */
  }
  if (!res.ok) {
    const msg = (data && (data.detail || data.error)) || `request failed (${res.status})`;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return data;
}

/* ---------- upload ---------- */

$("#video-file").addEventListener("change", (e) => {
  const f = e.target.files[0];
  $("#file-name").textContent = f ? `${f.name} (${(f.size / 1024 / 1024).toFixed(1)} MB)` : "Choose an MP4 file…";
});

$("#upload-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const file = $("#video-file").files[0];
  const title = $("#video-title").value.trim();
  const language = $("#video-language").value;
  if (!file || !title) return;

  const errBox = $("#upload-error");
  hide(errBox);
  $("#upload-btn").disabled = true;
  $("#upload-btn").textContent = "Uploading…";

  try {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("title", title);
    fd.append("language", language);
    const data = await jsonFetch(api.upload, { method: "POST", body: fd });
    state.jobId = data.id;
    state.answered = new Set();
    localStorage.setItem("v2l_job", data.id);
    hide($("#upload-panel"));
    show($("#progress-panel"));
    renderStages("upload");
    poll();
  } catch (err) {
    errBox.textContent = err.message;
    show(errBox);
  } finally {
    $("#upload-btn").disabled = false;
    $("#upload-btn").textContent = "Generate interactive video";
  }
});

/* ---------- polling ---------- */

function poll() {
  clearTimeout(state.pollTimer);
  state.pollTimer = setTimeout(async () => {
    try {
      const st = await jsonFetch(api.status(state.jobId));
      state.status = st;
      handleStatus(st);
    } catch (err) {
      $("#stage-detail").textContent = `Connection error: ${err.message}`;
      state.pollTimer = setTimeout(poll, 4000);
    }
  }, 1500);
}

function handleStatus(st) {
  if (st.stage === "ready") {
    renderStages("ready");
    enterEditor();
    return;
  }
  if (st.stage === "error") {
    renderStages("error", st);
    $("#error-msg").textContent = st.error || "Unknown error";
    show($("#pipeline-error"));
    $("#retry-btn").textContent = "Retry";
    return;
  }
  renderStages(st.stage);
  $("#stage-detail").textContent = STAGE_DETAIL[st.stage] || st.stage;
  poll();
}

function renderStages(current, st = null) {
  const items = document.querySelectorAll("#stage-list li");
  const curIdx = STAGE_ORDER.indexOf(current === "error" ? "generate" : current);
  items.forEach((li, i) => {
    li.classList.remove("active", "done", "failed");
    if (current === "error") {
      if (i < 2 && st && st.segments > 0) li.classList.add("done");
      else if (i === 0) li.classList.add("done");
      else if (i === 1 && st && st.segments > 0) li.classList.add("done");
      else if (i === (st && st.segments > 0 ? 2 : 1)) li.classList.add("failed");
    } else if (i < curIdx) {
      li.classList.add("done");
    } else if (i === curIdx) {
      li.classList.add(current === "ready" ? "done" : "active");
    }
  });
}

$("#retry-btn").addEventListener("click", async () => {
  hide($("#pipeline-error"));
  try {
    await jsonFetch(api.regenerate(state.jobId), { method: "POST" });
    renderStages(state.status && state.status.segments > 0 ? "generate" : "transcribe");
    $("#stage-detail").textContent =
      state.status && state.status.segments > 0 ? STAGE_DETAIL.generate : STAGE_DETAIL.transcribe;
    poll();
  } catch (err) {
    $("#error-msg").textContent = err.message;
    show($("#pipeline-error"));
  }
});

/* ---------- editor ---------- */

async function enterEditor() {
  hide($("#progress-panel"));
  show($("#editor-panel"));

  const st = state.status;
  $("#editor-title").textContent = st.title;
  $("#editor-meta").textContent =
    `${fmtTime(st.duration)} · ${st.width}×${st.height} · ${st.segments} transcript segments · ${st.language === "auto" ? "auto language" : st.language}`;
  $("#export-btn").href = api.export(state.jobId);
  $("#preview-video").src = api.media(state.jobId);

  const [t, q] = await Promise.all([
    jsonFetch(api.transcript(state.jobId)),
    jsonFetch(api.questions(state.jobId)),
  ]);
  state.transcript = t.segments || [];
  state.questions = q.questions || [];
  state.answered = new Set();

  $("#segment-count").textContent = state.transcript.length;
  renderTranscript();
  renderQuestions();
}

function renderTranscript() {
  const box = $("#transcript-list");
  box.innerHTML = "";
  state.transcript.forEach((seg) => {
    const row = document.createElement("div");
    row.className = "seg-row";
    const time = document.createElement("button");
    time.type = "button";
    time.className = "seg-time";
    time.textContent = fmtTime(seg.start);
    time.title = "Add a question at this time";
    time.addEventListener("click", () => openModal(null, seg.start));
    const text = document.createElement("span");
    text.textContent = seg.text;
    row.append(time, text);
    box.appendChild(row);
  });
}

function renderQuestions() {
  const body = $("#questions-body");
  body.innerHTML = "";
  const sorted = [...state.questions].sort((a, b) => a.time - b.time);
  $("#q-count").textContent = sorted.length;

  if (!sorted.length) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td colspan="4" class="muted">No questions yet — add one or regenerate.</td>`;
    body.appendChild(tr);
    return;
  }

  sorted.forEach((q) => {
    const tr = document.createElement("tr");
    const tdTime = document.createElement("td");
    tdTime.textContent = fmtTime(q.time);
    const tdType = document.createElement("td");
    tdType.innerHTML = `<span class="badge ${q.type}">${q.type === "tf" ? "T/F" : "MC"}</span>`;
    const tdQ = document.createElement("td");
    tdQ.textContent = q.question;
    const tdA = document.createElement("td");
    tdA.className = "actions-cell";

    const edit = document.createElement("button");
    edit.className = "link-btn";
    edit.textContent = "Edit";
    edit.addEventListener("click", () => openModal(q));

    const del = document.createElement("button");
    del.className = "link-btn danger";
    del.textContent = "Delete";
    del.addEventListener("click", async () => {
      if (!confirm("Delete this question?")) return;
      state.questions = state.questions.filter((x) => x.id !== q.id);
      await persistQuestions();
    });

    tdA.append(edit, del);
    tr.append(tdTime, tdType, tdQ, tdA);
    body.appendChild(tr);
  });
}

async function persistQuestions() {
  const indicator = $("#save-indicator");
  indicator.textContent = "Saving…";
  try {
    await jsonFetch(api.questions(state.jobId), {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ questions: state.questions }),
    });
    indicator.textContent = "Saved ✓";
    renderQuestions();
    setTimeout(() => {
      if (indicator.textContent === "Saved ✓") indicator.textContent = "";
    }, 2500);
  } catch (err) {
    indicator.textContent = `Save failed: ${err.message}`;
  }
}

$("#add-q-btn").addEventListener("click", () => openModal(null));

$("#regenerate-btn").addEventListener("click", async () => {
  if (state.questions.length && !confirm("Regenerate will REPLACE all current questions. Continue?")) return;
  try {
    await jsonFetch(api.regenerate(state.jobId), { method: "POST" });
    hide($("#editor-panel"));
    show($("#progress-panel"));
    renderStages("generate");
    $("#stage-detail").textContent = STAGE_DETAIL.generate;
    poll();
  } catch (err) {
    alert(err.message);
  }
});

/* ---------- edit modal ---------- */

function renderChoiceInputs(choices, correct) {
  const list = $("#choices-list");
  list.innerHTML = "";
  choices.forEach((text, i) => {
    const row = document.createElement("div");
    row.className = "choice-row";
    const radio = document.createElement("input");
    radio.type = "radio";
    radio.name = "correct-choice";
    radio.checked = i === correct;
    radio.dataset.index = i;
    const input = document.createElement("input");
    input.type = "text";
    input.value = text;
    input.placeholder = `Choice ${i + 1}`;
    input.dataset.index = i;
    const rm = document.createElement("button");
    rm.type = "button";
    rm.className = "link-btn danger";
    rm.textContent = "✕";
    rm.title = "Remove choice";
    rm.addEventListener("click", () => {
      if (list.children.length <= 2) return;
      const vals = readChoices();
      const corr = currentCorrect();
      vals.splice(i, 1);
      const nc = corr > i ? corr - 1 : corr === i ? 0 : corr;
      renderChoiceInputs(vals, nc);
    });
    row.append(radio, input, rm);
    list.appendChild(row);
  });
}

function readChoices() {
  return [...document.querySelectorAll("#choices-list input[type=text]")].map((i) => i.value.trim());
}

function currentCorrect() {
  const r = document.querySelector('input[name="correct-choice"]:checked');
  return r ? Number(r.dataset.index) : 0;
}

$("#add-choice-btn").addEventListener("click", () => {
  const vals = readChoices();
  if (vals.length >= 4) return;
  vals.push("");
  renderChoiceInputs(vals, currentCorrect());
});

function syncTypeFields() {
  const isTf = $("#q-type").value === "tf";
  $("#tf-fields").classList.toggle("hidden", !isTf);
  $("#mc-fields").classList.toggle("hidden", isTf);
}

$("#q-type").addEventListener("change", () => {
  syncTypeFields();
  if ($("#q-type").value === "tf" && readChoices().length !== 2) {
    /* tf fixed */
  }
});

function updateTimePreview() {
  const t = parseFloat($("#q-time").value);
  $("#time-preview").textContent = Number.isFinite(t) ? `→ starts at ${fmtTime(t)}` : "";
}
$("#q-time").addEventListener("input", updateTimePreview);

function openModal(question, presetTime) {
  state.editingId = question ? question.id : null;
  $("#modal-title").textContent = question ? "Edit question" : "Add question";
  $("#modal-error").classList.add("hidden");

  const q = question || {
    type: "mc",
    question: "",
    choices: ["", "", "", ""],
    correct: 0,
    explanation: "",
    time: defaultNewTime(presetTime),
    duration: 15,
  };

  $("#q-type").value = q.type;
  $("#q-question").value = q.question;
  $("#q-explanation").value = q.explanation || "";
  $("#q-time").value = q.time;
  $("#q-duration").value = q.duration || 15;

  if (q.type === "tf") {
    document.querySelector(`input[name="tf-correct"][value="${q.correct}"]`).checked = true;
    renderChoiceInputs(["True", "False"], 0);
  } else {
    renderChoiceInputs([...q.choices], q.correct);
  }
  syncTypeFields();
  updateTimePreview();
  show($("#edit-modal"));
  $("#q-question").focus();
}

function defaultNewTime(preset) {
  if (Number.isFinite(preset)) return Math.round(preset);
  const dur = (state.status && state.status.duration) || 60;
  const last = state.questions.reduce((m, q) => Math.max(m, q.time), -15);
  return Math.min(Math.round(last + 15), Math.max(0, Math.round(dur - 10)));
}

$("#modal-cancel").addEventListener("click", () => hide($("#edit-modal")));
$("#edit-modal").addEventListener("click", (e) => {
  if (e.target === $("#edit-modal")) hide($("#edit-modal"));
});

$("#modal-save").addEventListener("click", async () => {
  const errBox = $("#modal-error");
  hide(errBox);

  const type = $("#q-type").value;
  const question = $("#q-question").value.trim();
  const explanation = $("#q-explanation").value.trim();
  const time = parseFloat($("#q-time").value);
  const duration = parseFloat($("#q-duration").value) || 15;

  const fail = (msg) => {
    errBox.textContent = msg;
    show(errBox);
  };

  if (!question) return fail("Question text is required.");
  if (!Number.isFinite(time) || time < 0) return fail("Valid time is required.");
  const dur = (state.status && state.status.duration) || Infinity;
  if (time > dur - 5) return fail(`Time must be at least 5s before the end of the video (${fmtTime(dur)}).`);
  if (duration < 5) return fail("Visibility must be at least 5 seconds.");

  let choices, correct;
  if (type === "tf") {
    choices = ["True", "False"];
    correct = Number(document.querySelector('input[name="tf-correct"]:checked').value);
  } else {
    choices = readChoices();
    if (choices.length < 2 || choices.some((c) => !c)) return fail("All choices need text (2–4 choices).");
    if (new Set(choices).size !== choices.length) return fail("Choices must be unique.");
    correct = currentCorrect();
    if (correct >= choices.length) correct = 0;
  }

  const q = {
    id: state.editingId || `q${Date.now()}`,
    type,
    question,
    choices,
    correct,
    explanation,
    time: Math.round(time * 10) / 10,
    duration,
  };

  const idx = state.questions.findIndex((x) => x.id === q.id);
  if (idx >= 0) state.questions[idx] = q;
  else state.questions.push(q);

  await persistQuestions();
  if (!$("#save-indicator").textContent.startsWith("Save failed")) {
    hide($("#edit-modal"));
  }
});

/* ---------- preview overlay ---------- */

const video = $("#preview-video");
const overlay = $("#question-overlay");
let activeQuestion = null;

video.addEventListener("timeupdate", () => {
  if (activeQuestion || overlay.classList.contains("hidden") === false) return;
  const t = video.currentTime;
  const next = state.questions.find(
    (q) => !state.answered.has(q.id) && t >= q.time && t < q.time + (q.duration || 15)
  );
  if (next) openOverlay(next);
});

function openOverlay(q) {
  activeQuestion = q;
  video.pause();
  $("#ov-type").textContent = q.type === "tf" ? "True or False" : "Multiple choice";
  $("#ov-question").textContent = q.question;
  hide($("#ov-feedback"));
  hide($("#ov-continue"));

  const box = $("#ov-choices");
  box.innerHTML = "";
  q.choices.forEach((text, i) => {
    const btn = document.createElement("button");
    btn.className = "ov-choice";
    btn.textContent = text;
    btn.addEventListener("click", () => answerOverlay(q, i, btn));
    box.appendChild(btn);
  });
  show(overlay);
}

function answerOverlay(q, chosen, btn) {
  const buttons = document.querySelectorAll(".ov-choice");
  buttons.forEach((b) => (b.disabled = true));
  const correct = chosen === q.correct;
  btn.classList.add(correct ? "correct" : "wrong");
  if (!correct) buttons[q.correct].classList.add("correct");

  const fb = $("#ov-feedback");
  fb.textContent = (correct ? "Correct. " : "Incorrect. ") + (q.explanation || "");
  fb.classList.remove("hidden");
  fb.classList.add(correct ? "ok" : "bad");

  const cont = $("#ov-continue");
  cont.textContent = "Continue";
  show(cont);
  cont.onclick = () => {
    state.answered.add(q.id);
    activeQuestion = null;
    hide(overlay);
    fb.classList.remove("ok", "bad");
    video.play().catch(() => {});
  };
}

/* ---------- init ---------- */

async function resumeIfNeeded() {
  const id = localStorage.getItem("v2l_job");
  if (!id) return;
  try {
    const st = await jsonFetch(api.status(id));
    state.jobId = id;
    state.status = st;
    hide($("#upload-panel"));
    show($("#progress-panel"));
    handleStatus(st);
  } catch (_) {
    localStorage.removeItem("v2l_job");
  }
}

document.addEventListener("click", (e) => {
  if (e.target && e.target.id === "start-over-btn") {
    localStorage.removeItem("v2l_job");
    location.reload();
  }
});

renderStages("upload");
resumeIfNeeded();
