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
    tx.textContent += `\n[error: ${err.message} — is the API key set? Chat needs it; the rest of the console doesn't.]`;
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

loadOverview();
loadDepartments();
loadBoardroom();
loadCommands();
