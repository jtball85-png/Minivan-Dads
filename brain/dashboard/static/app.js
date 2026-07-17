/* CEO console — read-only view over HQ. All data comes from /api/*;
   nothing is stored client-side. */

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

/* ---------- tabs ---------- */
document.querySelectorAll("nav button").forEach((b) => {
  b.onclick = () => {
    document.querySelectorAll("nav button").forEach((x) => x.classList.remove("on"));
    document.querySelectorAll(".view").forEach((x) => x.classList.remove("on"));
    b.classList.add("on");
    $(b.dataset.v).classList.add("on");
  };
});

/* ---------- dashboard ---------- */
async function loadOverview() {
  const data = await (await fetch("/api/overview")).json();
  const s = data.stats;
  $("headerSub").textContent =
    `${data.week} · last meeting ${s.last_meeting ?? "never"}` +
    (s.days_since_meeting != null ? ` (${s.days_since_meeting}d ago)` : "");

  $("statRow").innerHTML = [
    { n: s.open_escalations, k: "open escalations", cls: s.urgent_escalations ? "coral" : s.open_escalations ? "amber" : "green" },
    { n: `${s.reports_filed}/${s.reports_expected}`, k: "reports filed", cls: s.reports_filed >= s.reports_expected ? "green" : "amber" },
    { n: s.decisions_logged, k: "decisions logged", cls: "" },
    { n: s.stale_directives, k: "stale directives", cls: s.stale_directives ? "coral" : "green" },
  ].map((x) => `<div class="stat"><div class="n ${x.cls}">${esc(x.n)}</div><div class="k">${esc(x.k)}</div></div>`).join("");

  $("escalations").innerHTML = data.escalations.length
    ? (data.escalations.some((e) => e.urgency === "urgent")
        ? `<div class="urgent-banner">▲ urgent items below — no push alerts exist; this surfaced because you opened the console</div>` : "")
      + data.escalations.map((e) =>
        `<div class="row"><span class="${e.urgency === "urgent" ? "urgent" : ""}">${e.urgency === "urgent" ? "▲" : "◦"} ${esc(e.id)} · ${esc(e.summary)}</span><span class="t">${esc(e.raised)}</span></div>`).join("")
    : `<div class="dim">queue is empty</div>`;

  $("decisions").innerHTML = data.recent_decisions.length
    ? data.recent_decisions.map((d) =>
        `<div class="row"><span>${esc(d.date)} · ${esc(d.title)}</span><span class="t ${d.decided_by === "CEO" ? "amb" : "okc"}">${esc(d.decided_by.split(" ")[0])}</span></div>`).join("")
    : `<div class="dim">no decisions logged yet</div>`;

  $("agenda").innerHTML = data.this_week_agenda
    ? `<pre class="doc">${esc(data.this_week_agenda)}</pre>`
    : `<div class="dim">No agenda for ${esc(data.week)} yet — run <code>brain ingest</code>.</div>`;
}

/* ---------- departments ---------- */
const TIER_PILL = (d) => d.status !== "active"
  ? `<span class="pill dorm">DORMANT</span>`
  : `<span class="pill t${d.tier}">TIER ${d.tier}</span>`;

async function loadDepartments() {
  const depts = await (await fetch("/api/departments")).json();
  $("deptGrid").innerHTML = depts.map((d) =>
    `<button class="dept" data-name="${esc(d.name)}">
       <div class="nm">${esc(d.name)}</div>
       <div class="meta">${esc(d.status)}${d.last_report_week ? " · " + esc(d.last_report_week) + " filed" : ""}</div>
       ${TIER_PILL(d)}
     </button>`).join("");
  document.querySelectorAll(".dept").forEach((b) => (b.onclick = () => showDept(b.dataset.name)));
}

async function showDept(name) {
  const d = await (await fetch(`/api/departments/${encodeURIComponent(name)}`)).json();
  $("deptGrid").style.display = "none";
  const det = $("deptDetail");
  det.style.display = "block";
  det.innerHTML = `
    <button class="back">← all departments</button>
    <div class="card">
      <h2>${esc(d.name)} ${TIER_PILL(d)}</h2>
      <div class="kv"><div class="k">standing directive</div>
        ${d.directive ? `<pre class="doc">${esc(d.directive)}</pre>` : `<span class="dim">none on file</span>`}</div>
      <div class="kv"><div class="k">latest report${d.latest_report_week ? " — " + esc(d.latest_report_week) : ""}</div>
        ${d.latest_report ? `<pre class="doc">${esc(d.latest_report)}</pre>` : `<span class="dim">no reports filed</span>`}</div>
      <div class="kv"><div class="k">actions taken</div>
        ${d.actions.length
          ? d.actions.map((a) => `<div class="row"><span>${esc(a.id)} · ${esc(a.action_type)} · ${esc(a.result)}</span><span class="t">${esc(a.mode)}</span></div>`).join("")
          : `<span class="dim">none — no live capabilities yet</span>`}</div>
      <div class="kv"><div class="k">directive history (git)</div>
        ${d.directive_history.length
          ? d.directive_history.map((h) => `<div class="row"><span>${esc(h.message)}</span><span class="t">${esc(h.commit)} · ${esc(h.date)}</span></div>`).join("")
          : `<span class="dim">no history available</span>`}</div>
    </div>`;
  det.querySelector(".back").onclick = () => {
    det.style.display = "none";
    $("deptGrid").style.display = "grid";
  };
}

/* ---------- boardroom (read-only transcripts) ---------- */
async function loadBoardroom() {
  const list = await (await fetch("/api/boardroom")).json();
  $("boardList").innerHTML = list.length
    ? list.map((t) =>
        `<div class="row"><span><a href="#" class="amb" data-file="${esc(t.filename)}">${esc(t.slug)}</a></span><span class="t">${esc(t.week)}</span></div>`).join("")
    : `<div class="dim">no boardroom debates held yet</div>`;
  document.querySelectorAll("[data-file]").forEach((a) => {
    a.onclick = async (ev) => {
      ev.preventDefault();
      const t = await (await fetch(`/api/boardroom/${encodeURIComponent(a.dataset.file)}`)).json();
      $("boardDetail").innerHTML = `<div class="card"><h2>${esc(a.dataset.file)}</h2><pre class="doc">${esc(t.content)}</pre></div>`;
    };
  });
}

/* ---------- commands ---------- */
async function loadCommands() {
  const cmds = await (await fetch("/api/commands")).json();
  $("cmdList").innerHTML = cmds.map((c) =>
    `<div class="cmdrow">
       <code>brain ${esc(c.name)}</code>
       <p>${esc((c.description || "").split("\n")[0])}</p>
       <pre class="doc">${esc(c.full_help)}</pre>
     </div>`).join("");
  document.querySelectorAll(".cmdrow code").forEach((code) => {
    code.onclick = () => code.closest(".cmdrow").classList.toggle("open");
  });
}

/* ---------- shared SSE reader ---------- */
async function readSSE(response, onEvent) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      if (chunk.startsWith("data: ")) onEvent(JSON.parse(chunk.slice(6)));
    }
  }
}

/* ---------- chat message rendering ---------- */
const WHO = {
  ceo:   { label: "You · CEO", av: "CEO", color: "var(--amber)" },
  brain: { label: "Brain · COO", av: "BR", color: "var(--purple)" },
};
function chatMsg(container, who, text) {
  const w = WHO[who] || { label: who, av: who.slice(0, 2).toUpperCase(), color: "var(--blue)" };
  const m = document.createElement("div");
  m.className = "msg" + (who === "ceo" ? " ceoMsg" : "");
  m.innerHTML = `<div class="av" style="color:${w.color}">${esc(w.av)}</div>
    <div class="b"><div class="who" style="color:${w.color}">${esc(w.label)}</div>
    <div class="tx"></div></div>`;
  m.querySelector(".tx").textContent = text;
  container.appendChild(m);
  m.scrollIntoView({ behavior: "smooth", block: "end" });
  return m.querySelector(".tx");
}

/* ---------- ask the brain ---------- */
$("askForm").onsubmit = async (ev) => {
  ev.preventDefault();
  const input = $("askInput");
  const question = input.value.trim();
  if (!question) return;
  input.value = "";
  $("askSend").disabled = true;
  $("askChips").innerHTML = "";

  chatMsg($("askLog"), "ceo", question);
  const tx = chatMsg($("askLog"), "brain", "…");
  tx.textContent = "";

  try {
    const response = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    let record = null;
    await readSSE(response, (e) => {
      if (e.delta) tx.textContent += e.delta;
      if (e.done) record = e.decision_record;
    });
    if (record) offerDecisionLog(record);
  } catch (err) {
    tx.textContent += err.message.includes("404")
      ? "\n[chat isn't loaded on this server — stop the dashboard (Ctrl-C) and run `brain dashboard` again from the project; its startup line should say 'chat enabled'.]"
      : `\n[error: ${err.message}]`;
  } finally {
    $("askSend").disabled = false;
    input.focus();
  }
};

function offerDecisionLog(record) {
  const chips = $("askChips");
  chips.innerHTML = `<span class="hint">the brain drafted a decision record — log it?</span>`;
  const logBtn = document.createElement("button");
  logBtn.className = "primary";
  logBtn.textContent = `Log it: ${record.title}`;
  logBtn.onclick = async () => {
    await fetch("/api/ask/log-decision", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(record),
    });
    chips.innerHTML = `<div class="decis">✓ logged to hq/decisions/log.md</div>`;
    loadOverview();
  };
  const dismissBtn = document.createElement("button");
  dismissBtn.textContent = "Dismiss";
  dismissBtn.onclick = () => (chips.innerHTML = "");
  chips.append(logBtn, dismissBtn);
}

/* ---------- live boardroom ---------- */
const DEPT_COLORS = ["var(--blue)", "var(--coral)", "var(--green)", "var(--amber)", "var(--purple)"];
let brPhase = "closed"; // closed | debating | floor | synthesized
let brDeptColors = {};

function brMsg(speaker, text) {
  const isCeo = speaker === "CEO";
  const isBrain = speaker === "brain";
  const color = isCeo ? "var(--amber)" : isBrain ? "var(--purple)" : (brDeptColors[speaker] || "var(--blue)");
  const label = isCeo ? "You · CEO" : isBrain ? "Brain · COO" : speaker;
  const av = isCeo ? "CEO" : isBrain ? "BR" : speaker.slice(0, 2).toUpperCase();
  const m = document.createElement("div");
  m.className = "msg" + (isCeo ? " ceoMsg" : "");
  m.innerHTML = `<div class="av" style="color:${color}">${esc(av)}</div>
    <div class="b"><div class="who" style="color:${color}">${esc(label)}</div>
    <div class="tx"></div></div>`;
  m.querySelector(".tx").textContent = text;
  $("brLog").appendChild(m);
  m.scrollIntoView({ behavior: "smooth", block: "end" });
  return m.querySelector(".tx");
}
function brSys(text) {
  const s = document.createElement("div");
  s.className = "sysline";
  s.textContent = text;
  $("brLog").appendChild(s);
}
function brSetInput(placeholder, buttonLabel) {
  $("brInput").placeholder = placeholder;
  $("brSend").textContent = buttonLabel;
}

$("brForm").onsubmit = async (ev) => {
  ev.preventDefault();
  const raw = $("brInput").value.trim();
  if (!raw) return;
  $("brInput").value = "";
  $("brSend").disabled = true;
  try {
    if (brPhase === "closed") await brOpen(raw);
    else if (brPhase === "floor") await brFloor(raw);
    else if (brPhase === "synthesized") await brRule(raw, {});
  } catch (err) {
    brSys(`error: ${err.message}`);
  } finally {
    $("brSend").disabled = false;
    $("brInput").focus();
  }
};

async function brOpen(topic) {
  $("brLog").innerHTML = "";
  $("brChips").innerHTML = "";
  brDeptColors = {};
  brSys(`brain boardroom "${topic}" — convening…`);
  const response = await fetch("/api/boardroom/open", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic }),
  });
  if (!response.ok) throw new Error((await response.json()).detail || `HTTP ${response.status}`);
  brPhase = "debating";
  let round = "";
  await readSSE(response, (e) => {
    if (e.participants) {
      e.participants.forEach((p, i) => (brDeptColors[p.department] = DEPT_COLORS[i % DEPT_COLORS.length]));
      brSys("convened: " + e.participants.map((p) => p.department + (p.advisory ? " (advisory)" : "")).join(", "));
    }
    if (e.round && e.round !== round) {
      round = e.round;
      brSys(round === "positions" ? "— opening positions (filed blind) —" : `— ${round} —`);
    }
    if (e.speaker) brMsg(e.speaker, e.text);
    if (e.done && e.declined) { brSys(e.reason); brPhase = "closed"; }
    if (e.done && e.floor_open) {
      brPhase = "floor";
      brSys("the floor is yours");
      brSetInput("@department to question anyone, bare text talks to the brain…", "send");
      brFloorChips();
    }
  });
}

function brFloorChips() {
  $("brChips").innerHTML = `<span class="hint">when you're ready</span>`;
  const b = document.createElement("button");
  b.className = "primary";
  b.textContent = "Move to synthesis";
  b.onclick = brSynthesize;
  $("brChips").appendChild(b);
}

async function brFloor(message) {
  brMsg("CEO", message);
  const response = await fetch("/api/boardroom/floor", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!response.ok) throw new Error((await response.json()).detail || `HTTP ${response.status}`);
  await readSSE(response, (e) => {
    if (e.speaker && e.speaker !== "CEO") brMsg(e.speaker, e.text);
  });
}

async function brSynthesize() {
  $("brChips").innerHTML = "";
  brSys("— synthesis —");
  const tx = brMsg("brain", "");
  const response = await fetch("/api/boardroom/synthesize", { method: "POST" });
  if (!response.ok) { brSys(`error: HTTP ${response.status}`); return; }
  await readSSE(response, (e) => { if (e.delta) tx.textContent += e.delta; });
  brPhase = "synthesized";
  brSetInput("…or type your ruling in your own words", "rule");
  $("brChips").innerHTML = `<span class="hint">your ruling — chips or your own words below</span>`;
  [
    { label: "Adopt the brain's recommendation", ruling: "Adopted the brain's recommendation as synthesized.", primary: true },
    { label: "Reject", ruling: "REJECTED: the recommendation is not adopted." },
  ].forEach((o) => {
    const b = document.createElement("button");
    if (o.primary) b.className = "primary";
    b.textContent = o.label;
    b.onclick = () => brRule(o.ruling, {});
    $("brChips").appendChild(b);
  });
}

async function brRule(ruling, ratifications) {
  brMsg("CEO", ruling);
  $("brChips").innerHTML = "";
  const response = await fetch("/api/boardroom/rule", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ruling, ratifications }),
  });
  if (!response.ok) { brSys(`error: HTTP ${response.status}`); return; }
  const data = await response.json();

  if (data.needs_ratification) {
    const pending = data.needs_ratification[0];
    brSys(`the records include a tier/status change for ${pending.dept} (${pending.change}) — tier changes are explicit board decisions, never silent.`);
    $("brChips").innerHTML = `<span class="hint">ratify ${esc(pending.dept)}: ${esc(pending.change)}?</span>`;
    [
      { label: `Ratify: ${pending.change}`, approve: true, primary: true },
      { label: "Do not ratify (skip that change)", approve: false },
    ].forEach((o) => {
      const b = document.createElement("button");
      if (o.primary) b.className = "primary";
      b.textContent = o.label;
      b.onclick = () => brRule(ruling, { ...ratifications, [pending.dept]: o.approve });
      $("brChips").appendChild(b);
    });
    return;
  }

  const d = document.createElement("div");
  d.className = "decis";
  d.textContent = `✓ ruled · ${data.decisions} decision(s) logged` +
    (data.directives_updated.length ? ` · directives updated: ${data.directives_updated.join(", ")}` : "");
  $("brLog").appendChild(d);
  (data.warnings || []).forEach((w) => brSys(`warning: ${w}`));
  brSys(`transcript: ${data.transcript_path}`);
  brPhase = "closed";
  brSetInput("Type a topic to open the boardroom.", "open");
  loadBoardroom();
  loadOverview();
}

/* ---------- health check: never let chat fail silently ---------- */
async function checkHealth() {
  let problem = null;
  try {
    const response = await fetch("/api/health");
    if (!response.ok) {
      // A server without /api/health predates this build entirely.
      problem = "This server is running an OLD version of the console.";
    } else {
      const h = await response.json();
      if (!h.chat) problem = "Chat failed to start — the console is read-only right now.";
    }
  } catch {
    return; // server unreachable — the page itself won't have loaded anyway
  }
  if (problem) {
    const banner = document.createElement("div");
    banner.className = "card";
    banner.style.borderColor = "var(--coral)";
    banner.innerHTML =
      `<h2 style="color:var(--coral)">restart needed</h2>
       <div style="font-size:12px">${problem} Close the "Minivan Dads HQ" ` +
      `window on your taskbar (or restart your PC), double-click ` +
      `<code>Minivan Dads HQ.bat</code> again, and refresh this page. If it ` +
      `persists, <code>dashboard_startup.log</code> in the project folder ` +
      `says exactly what went wrong — paste it to Claude Code.</div>`;
    document.querySelector(".app").insertBefore(banner, document.querySelector("nav"));
  }
}

/* =====================================================================
   Command bar: #commands, @department consults, plain text = ask.
   Output renders in the "work session" panel above the tabs.
   ===================================================================== */

const work = {
  panel: $("work"), log: $("workLog"), chips: $("workChips"),
  note: $("workNote"), noteInput: $("noteInput"),
};

function workShow() { work.panel.style.display = "block"; }
function workSys(text) {
  workShow();
  const s = document.createElement("div");
  s.className = "sysline";
  s.textContent = text;
  work.log.appendChild(s);
  s.scrollIntoView({ behavior: "smooth", block: "end" });
}
function workMsg(speaker, text) {
  workShow();
  const isCeo = speaker === "CEO";
  const isBrain = speaker === "brain";
  const color = isCeo ? "var(--amber)" : isBrain ? "var(--purple)" : "var(--blue)";
  const label = isCeo ? "You · CEO" : isBrain ? "Brain · COO" : speaker;
  const av = isCeo ? "CEO" : isBrain ? "BR" : speaker.slice(0, 2).toUpperCase();
  const m = document.createElement("div");
  m.className = "msg" + (isCeo ? " ceoMsg" : "");
  m.innerHTML = `<div class="av" style="color:${color}">${esc(av)}</div>
    <div class="b"><div class="who" style="color:${color}">${esc(label)}</div>
    <div class="tx"></div></div>`;
  m.querySelector(".tx").textContent = text;
  work.log.appendChild(m);
  m.scrollIntoView({ behavior: "smooth", block: "end" });
  return m.querySelector(".tx");
}
function workOk(text) {
  workShow();
  const d = document.createElement("div");
  d.className = "decis";
  d.textContent = text;
  work.log.appendChild(d);
  d.scrollIntoView({ behavior: "smooth", block: "end" });
}
function workChipSet(hint, options) {
  work.chips.innerHTML = hint ? `<span class="hint">${esc(hint)}</span>` : "";
  options.forEach((o) => {
    const b = document.createElement("button");
    if (o.primary) b.className = "primary";
    b.textContent = o.label;
    b.onclick = o.go;
    work.chips.appendChild(b);
  });
}
function workNoteAsk(placeholder) {
  return new Promise((resolve) => {
    work.note.style.display = "block";
    work.noteInput.placeholder = placeholder;
    work.noteInput.value = "";
    work.noteInput.focus();
    $("noteForm").onsubmit = (ev) => {
      ev.preventDefault();
      work.note.style.display = "none";
      resolve(work.noteInput.value.trim());
    };
  });
}
$("workClear").onclick = (ev) => {
  ev.preventDefault();
  work.log.innerHTML = "";
  work.chips.innerHTML = "";
  work.panel.style.display = "none";
};

async function postSSE(url, body, onEvent) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try { detail = (await response.json()).detail || detail; } catch {}
    throw new Error(detail);
  }
  await readSSE(response, onEvent);
}

/* ---------- command implementations ---------- */

async function cmdIngest() {
  workSys("#ingest — reading reports, synthesizing the agenda (a minute or two)…");
  await postSSE("/api/command/ingest", {}, (e) => {
    if (e.line) workSys(e.line);
    if (e.done) {
      workOk(`✓ agenda written · ${e.decisions} proposed decision(s)`);
      (e.upgrades || []).forEach((u) =>
        workSys(`governance upgraded to CEO REQUIRED: ${u.title} (${u.reasons.join("; ")})`));
      if (e.agenda) {
        workShow();
        const card = document.createElement("div");
        card.className = "card";
        card.innerHTML = `<h2>this week's agenda — read before #meeting</h2><pre class="doc"></pre>`;
        card.querySelector("pre").textContent = e.agenda;
        work.log.appendChild(card);
        card.scrollIntoView({ behavior: "smooth", block: "end" });
      }
      workSys("when you've read it: #meeting to rule.");
      loadOverview();
    }
  });
}

async function cmdAgent(dept) {
  workSys(`#agent ${dept} — running the research loop (can take a few minutes)…`);
  await postSSE("/api/command/agent", { department: dept }, (e) => {
    if (e.line) workSys(e.line);
    if (e.done) {
      workOk(e.exit_code === 0 ? "✓ agent run complete" : "agent run refused (see lines above)");
      loadOverview(); loadDepartments();
    }
  });
}

async function cmdConsult(dept, message) {
  workMsg("CEO", `@${dept} ${message}`);
  const tx = workMsg(dept, "");
  await postSSE("/api/consult", { department: dept, message }, (e) => {
    if (e.delta) tx.textContent += e.delta;
    if (e.done && e.advisory) workSys(`(${dept} is dormant — advisory answer, charter-only)`);
  });
}

async function cmdAsk(question) {
  workMsg("CEO", question);
  const tx = workMsg("brain", "");
  let record = null;
  await postSSE("/api/ask", { question }, (e) => {
    if (e.delta) tx.textContent += e.delta;
    if (e.done) record = e.decision_record;
  });
  if (record) {
    workChipSet("the brain drafted a decision record — log it?", [
      { label: `Log it: ${record.title}`, primary: true, go: async () => {
          await fetch("/api/ask/log-decision", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify(record),
          });
          workChipSet("", []);
          workOk("✓ logged to the decision log");
          loadOverview();
        } },
      { label: "Dismiss", go: () => workChipSet("", []) },
    ]);
  }
}

async function cmdDirective(dept, changes) {
  workMsg("CEO", `#directive ${dept} — ${changes}`);
  workSys("drafting the revised directive…");
  const response = await fetch("/api/command/directive", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ department: dept, changes }),
  });
  if (!response.ok) {
    workSys(`error: ${(await response.json()).detail || response.status}`);
    return;
  }
  const data = await response.json();
  workMsg("brain", data.response);
  if (data.board_decision_required) {
    workSys("that change includes a tier move — it needs a board decision, not a directive edit. Raise it at #meeting or #boardroom.");
    return;
  }
  if (!data.writable) {
    workSys("no directive block came back — rephrase the ask and try again.");
    return;
  }
  workChipSet(`write this to hq/directives/${dept}.md?`, [
    { label: "Write it", primary: true, go: async () => {
        const r = await fetch("/api/command/directive/confirm", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ department: dept }),
        });
        workChipSet("", []);
        if (r.ok) { workOk("✓ directive written"); loadDepartments(); }
        else workSys(`error: ${(await r.json()).detail || r.status}`);
      } },
    { label: "Discard", go: () => { workChipSet("", []); workSys("discarded — nothing written."); } },
  ]);
}

/* ---------- the meeting, as a guided flow ---------- */

async function cmdMeeting() {
  const response = await fetch("/api/meeting/start", { method: "POST" });
  if (!response.ok) {
    workSys(`#meeting — ${(await response.json()).detail || response.status}`);
    return;
  }
  const data = await response.json();
  workSys(`#meeting — board meeting ${data.week} · ${data.items.length} item(s).`);
  if (data.briefing) {
    workShow();
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `<h2>the brain's briefing — what your departments reported</h2><pre class="doc"></pre>`;
    card.querySelector("pre").textContent = data.briefing;
    work.log.appendChild(card);
    card.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  meetingItems = data.items;
  meetingIndex = 0;
  workChipSet("read the briefing, then take the first item", [
    { label: "Begin rulings", primary: true, go: meetingShowItem },
  ]);
}

let meetingItems = null, meetingIndex = 0;

function meetingShowItem() {
  const item = meetingItems[meetingIndex];
  const tagColor = item.tag === "CEO REQUIRED" ? "var(--amber)" : "var(--green)";
  workShow();
  const card = document.createElement("div");
  card.className = "card";
  card.innerHTML = `<h2>item ${meetingIndex + 1} of ${meetingItems.length} · ` +
    `<span style="color:${tagColor}">[${esc(item.tag || "UNTAGGED")}]</span></h2>` +
    `<pre class="doc"></pre>`;
  card.querySelector("pre").textContent = item.block_text;
  work.log.appendChild(card);
  card.scrollIntoView({ behavior: "smooth", block: "end" });

  const rule = (action) => async () => {
    let note = "";
    if (action === "modify") note = await workNoteAsk("Your modification/ruling…");
    if (action === "reject") note = await workNoteAsk("Why (for the record, optional)…");
    await fetch("/api/meeting/ruling", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ item_id: item.id, action, note }),
    });
    workOk(`✓ ${item.title}: ${action.toUpperCase()}${note ? " — " + note : ""}`);
    meetingIndex++;
    if (meetingIndex < meetingItems.length) meetingShowItem();
    else meetingClose({});
  };

  workChipSet("your ruling — or type below to discuss this item first", [
    { label: "Approve", primary: true, go: rule("approve") },
    { label: "Modify", go: rule("modify") },
    { label: "Reject", go: rule("reject") },
    { label: "Skip", go: rule("skip") },
  ]);
}

async function meetingDiscuss(text) {
  const item = meetingItems[meetingIndex];
  workMsg("CEO", text);
  const tx = workMsg("brain", "…");
  tx.textContent = "";
  await postSSE("/api/meeting/discuss", { item_id: item.id, text }, (e) => {
    if (e.reply) tx.textContent = e.reply;
  });
}

async function meetingClose(ratifications) {
  workSys("meeting over — writing minutes, decisions, and directive updates…");
  workChipSet("", []);
  const response = await fetch("/api/meeting/close", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ratifications }),
  });
  const data = await response.json();

  if (data.needs_ratification) {
    const pending = data.needs_ratification[0];
    workSys(`the records include a tier/status change for ${pending.dept} (${pending.change}) — tier changes are explicit board decisions, never silent.`);
    workChipSet(`ratify ${pending.dept}: ${pending.change}?`, [
      { label: `Ratify: ${pending.change}`, primary: true,
        go: () => meetingClose({ ...ratifications, [pending.dept]: true }) },
      { label: "Do not ratify (skip that change)",
        go: () => meetingClose({ ...ratifications, [pending.dept]: false }) },
    ]);
    return;
  }

  meetingItems = null;
  workOk(`✓ meeting closed · ${data.decisions} decision(s) logged · ` +
         `${data.directives_updated.length} directive(s) updated · ` +
         `${data.escalations_resolved} escalation(s) resolved`);
  (data.warnings || []).forEach((w) => workSys(`warning: ${w}`));
  loadOverview(); loadDepartments();
}

/* ---------- parser + dispatch ---------- */

const COMMANDS = {
  "#help": async () => {
    const help = await (await fetch("/api/command/help")).json();
    workSys("commands:");
    help.forEach((h) => workSys(`  ${h.syntax} — ${h.help}`));
  },
  "#status": async () => {
    document.querySelector('nav button[data-v="home"]').click();
    await loadOverview();
    workSys("#status — refreshed. The stat row and inbox above are current.");
  },
  "#ingest": cmdIngest,
  "#meeting": cmdMeeting,
};

$("cmdBar").onsubmit = async (ev) => {
  ev.preventDefault();
  const raw = $("cmdInput").value.trim();
  if (!raw) return;
  $("cmdInput").value = "";
  $("cmdSend").disabled = true;
  try {
    // Mid-meeting, plain text discusses the current agenda item.
    if (meetingItems && !raw.startsWith("#") && !raw.startsWith("@")) {
      await meetingDiscuss(raw);
      return;
    }
    const [head, ...restParts] = raw.split(/\s+/);
    const rest = restParts.join(" ");
    const headLower = head.toLowerCase();

    if (COMMANDS[headLower]) await COMMANDS[headLower]();
    else if (headLower === "#boardroom") {
      document.querySelector('nav button[data-v="board"]').click();
      if (rest) { $("brInput").value = rest; $("brForm").requestSubmit(); }
      else workSys("#boardroom — type your topic in the Boardroom box.");
    }
    else if (headLower === "#agent") {
      if (!rest) workSys("usage: #agent market_intel");
      else await cmdAgent(rest.split(/\s+/)[0]);
    }
    else if (headLower === "#directive") {
      const [dept, ...changes] = rest.split(/\s+/);
      if (!dept || !changes.length) workSys("usage: #directive market_intel <changes in plain English>");
      else await cmdDirective(dept, changes.join(" "));
    }
    else if (headLower.startsWith("#")) {
      workSys(`unknown command ${head} — try #help`);
    }
    else if (headLower.startsWith("@")) {
      const dept = head.slice(1);
      if (!rest) workSys(`usage: @${dept} <your question>`);
      else await cmdConsult(dept, rest);
    }
    else await cmdAsk(raw);
  } catch (err) {
    workSys(`error: ${err.message}`);
  } finally {
    $("cmdSend").disabled = false;
    $("cmdInput").focus();
  }
};

/* live hint line while typing a command */
$("cmdInput").addEventListener("input", async () => {
  const v = $("cmdInput").value.trim();
  const hint = $("cmdHint");
  if (!v.startsWith("#") && !v.startsWith("@")) { hint.style.display = "none"; return; }
  if (!window._helpCache) {
    try { window._helpCache = await (await fetch("/api/command/help")).json(); }
    catch { return; }
  }
  const matches = window._helpCache.filter((h) =>
    h.command.startsWith(v.split(/\s+/)[0].toLowerCase()) || (v.startsWith("@") && h.command === "@department"));
  hint.textContent = matches.map((h) => `${h.syntax} — ${h.help}`).join("   ·   ");
  hint.style.display = matches.length ? "block" : "none";
});

checkHealth();
loadOverview();
loadDepartments();
loadBoardroom();
loadCommands();
