const $ = (id) => document.getElementById(id);

function num(name) {
  const el = document.querySelector(`#app-form [name="${name}"]`);
  const v = el.value.trim();
  return v === "" ? null : Number(v);
}

$("app-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const application = {
    application_id: fd.get("application_id"),
    applicant_name: fd.get("applicant_name"),
    product: fd.get("product"),
    loan_amount: num("loan_amount"),
    loan_tenure_months: num("loan_tenure_months"),
    monthly_income: num("monthly_income"),
    existing_monthly_obligations: num("existing_monthly_obligations") || 0,
    employment_vintage_months: num("employment_vintage_months"),
    cibil_score: num("cibil_score"),
    collateral_value: num("collateral_value"),
    worst_dpd_24m: num("worst_dpd_24m") || 0,
    has_coapplicant: fd.get("has_coapplicant") === "on",
    documents_provided: [...document.querySelectorAll("#docs input:checked")].map((c) => c.value),
  };
  const res = await fetch("/api/underwrite", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ application }),
  });
  const data = await res.json();
  renderResult(data);
});

function renderResult(d) {
  $("result-card").hidden = false;
  const badge = $("decision-badge");
  if (d.status === "awaiting_info") {
    badge.innerHTML = `<span class="badge refer">AWAITING INFO</span>`;
    $("reasons").innerHTML = d.questions.map((q) => `<li>${q}</li>`).join("");
  } else {
    badge.innerHTML = `<span class="badge ${d.decision}">${d.decision.toUpperCase()}</span>`;
    $("reasons").innerHTML = (d.reasons || []).map((r) => `<li>${r}</li>`).join("");
  }
  const n = d.numbers || {};
  $("numbers").innerHTML = `<div class="kv">
    <div><b>Score</b>${d.score ?? "—"} (${d.risk_band ?? "—"})</div>
    <div><b>EMI</b>${n.emi ? "₹" + Number(n.emi).toLocaleString("en-IN") : "—"}</div>
    <div><b>FOIR</b>${n.foir ?? "—"}</div>
    <div><b>LTV</b>${n.ltv ?? "n/a"}</div>
    <div><b>Offered rate</b>${n.offered_rate ? (n.offered_rate * 100).toFixed(2) + "%" : "—"}</div>
  </div>`;
  $("trace").innerHTML = (d.trace || [])
    .map((t) => `<li><code>${t.from}</code> <span class="arrow">→</span> <code>${t.to}</code><br><span class="note">${t.note}</span></li>`)
    .join("");
  $("conditions").innerHTML = (d.conditions || []).map((c) => `<li>${c}</li>`).join("") || "<li>—</li>";
  $("citations").innerHTML = (d.citations || [])
    .map((c) => `<div class="cite"><div class="src">${c.doc_id} :: ${c.heading}</div><div class="txt">${c.text}</div></div>`)
    .join("") || "<p>—</p>";
  $("memo").textContent = d.memo || "";
  $("result-card").scrollIntoView({ behavior: "smooth" });
}

// ---------------- chat ----------------
let sessionId = null;
const chatLog = $("chat-log");

function addMsg(text, cls) {
  const div = document.createElement("div");
  div.className = "msg " + cls;
  div.textContent = text;
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
}

$("chat-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = $("chat-input");
  const message = input.value.trim();
  if (!message) return;
  addMsg(message, "user");
  input.value = "";
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message }),
  });
  const data = await res.json();
  sessionId = data.session_id;
  addMsg(data.reply.replaceAll("**", ""), "bot");
});
