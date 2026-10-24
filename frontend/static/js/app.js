
const API = "/api/v1";

const state = {
  cases: [],
  selectedCase: null,
  documents: [],
  evidence: [],
  assessment: null,
  toastTimer: null,
};

const $ = (selector) => document.querySelector(selector);

function escapeHTML(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;",
    '"': "&quot;", "'": "&#39;",
  })[char]);
}

function displayDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "—"
    : date.toLocaleDateString(undefined, {
        day: "2-digit", month: "short", year: "numeric",
      });
}

function displayMoney(value, currency = "INR") {
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(number);
}

function readable(value) {
  return String(value ?? "unknown")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function showToast(message, type = "info") {
  const toast = $("#toast");
  toast.textContent = message;
  toast.className = `toast ${type}`;
  toast.hidden = false;
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => {
    toast.hidden = true;
  }, 5000);
}

async function api(path, options = {}) {
  const response = await fetch(`${API}${path}`, options);
  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const detail = body && typeof body === "object"
      ? body.detail || body.message
      : body;
    throw new Error(detail || `Request failed (${response.status})`);
  }
  return body;
}

function setButtonLoading(button, loading, loadingText = "Working…") {
  if (loading) {
    button.dataset.originalText = button.textContent;
    button.textContent = loadingText;
    button.disabled = true;
  } else {
    button.textContent = button.dataset.originalText || button.textContent;
    button.disabled = false;
  }
}

function setView(view) {
  const titles = {
    dashboard: "Overview",
    investigations: "Investigations",
    reports: "Risk reports",
    case: "Investigation workspace",
  };

  document.querySelectorAll(".view").forEach((section) => {
    section.hidden = section.id !== `view-${view}`;
  });

  document.querySelectorAll(".nav-item").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === view);
  });

  $("#page-title").textContent = titles[view] || "Finlytics";
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function openCaseModal() {
  $("#case-form").reset();
  $("#case-form-error").hidden = true;
  $("#case-modal").hidden = false;
  setTimeout(() => $('#case-form [name="business_name"]').focus(), 20);
}

function closeCaseModal() {
  $("#case-modal").hidden = true;
}

function statusPill(value) {
  const status = String(value || "unknown").toLowerCase();
  return `<span class="status-pill ${escapeHTML(status)}">${escapeHTML(readable(status))}</span>`;
}

function renderCaseRows(cases, target, columns = "full") {
  const body = $(target);
  if (!cases.length) {
    body.innerHTML = `<tr><td colspan="${columns === "full" ? 6 : 5}" class="empty-cell">
      No investigations yet. Create your first case to get started.
    </td></tr>`;
    return;
  }

  body.innerHTML = cases.map((item) => {
    const business = escapeHTML(item.business_name);
    const id = escapeHTML(item.id);
    const amount = displayMoney(item.loan_amount, item.currency || "INR");

    if (columns === "recent") {
      return `<tr>
        <td><span class="business-cell">${business}</span><small>${escapeHTML(item.id)}</small></td>
        <td>${escapeHTML(amount)}</td>
        <td>${statusPill(item.status)}</td>
        <td>${displayDate(item.created_at)}</td>
        <td><button class="row-action" data-open-case="${id}">Open →</button></td>
      </tr>`;
    }

    return `<tr>
      <td><span class="business-cell">${business}</span><small>${escapeHTML(item.id)}</small></td>
      <td>${escapeHTML(item.business_type || "—")}</td>
      <td>${escapeHTML(amount)}</td>
      <td>${statusPill(item.status)}</td>
      <td>${displayDate(item.created_at)}</td>
      <td><button class="row-action" data-open-case="${id}">Open →</button></td>
    </tr>`;
  }).join("");
}

async function loadCases() {
  const result = await api("/cases?limit=100&offset=0");
  state.cases = Array.isArray(result.items) ? result.items : [];

  $("#stat-total").textContent = result.total ?? state.cases.length;
  $("#stat-active").textContent = state.cases.filter(
    (item) => !["completed", "cancelled"].includes(item.status),
  ).length;

  renderCaseRows(state.cases.slice(0, 6), "#recent-cases", "recent");
  renderCaseRows(state.cases, "#all-cases");

  // Aggregate counts only from cases the API returned.
  $("#stat-documents").textContent = "—";
  $("#stat-evidence").textContent = "—";

  if (!state.cases.length) {
    $("#stat-documents").textContent = "0";
    $("#stat-evidence").textContent = "0";
    return;
  }

  // Fetch counts in parallel; individual failures don't break the dashboard.
  const summaries = await Promise.all(state.cases.map(async (item) => {
    try {
      const [docs, evidence] = await Promise.all([
        api(`/cases/${encodeURIComponent(item.id)}/documents`),
        api(`/cases/${encodeURIComponent(item.id)}/evidence`),
      ]);
      return {
        documents: docs.total ?? docs.items?.length ?? 0,
        evidence: evidence.total ?? evidence.items?.length ?? 0,
      };
    } catch {
      return { documents: 0, evidence: 0 };
    }
  }));

  $("#stat-documents").textContent = summaries.reduce((sum, item) => sum + item.documents, 0);
  $("#stat-evidence").textContent = summaries.reduce((sum, item) => sum + item.evidence, 0);
}

async function checkAPI() {
  const label = $("#api-status");
  const dot = $(".system-status .status-dot");

  try {
    await fetch("/ready").then((response) => {
      if (!response.ok) throw new Error("Backend unavailable");
    });
    label.textContent = "Connected";
    dot.classList.add("online");
    dot.classList.remove("offline");
  } catch {
    label.textContent = "Connection unavailable";
    dot.classList.add("offline");
    dot.classList.remove("online");
  }
}

function renderDocuments() {
  const container = $("#documents-list");
  if (!state.documents.length) {
    container.innerHTML = '<p class="muted">No documents uploaded yet.</p>';
    return;
  }

  container.innerHTML = state.documents.map((doc) => `
    <div class="record-item">
      <div>
        <strong>${escapeHTML(doc.original_filename)}</strong>
        <small>${escapeHTML(doc.document_type || "Document")} · ${escapeHTML(doc.file_size ?? "—")} bytes</small>
        <small>SHA-256: ${escapeHTML(doc.sha256 || "Unavailable")}</small>
      </div>
      <div class="record-side">${statusPill(doc.status)}</div>
    </div>
  `).join("");
}

function renderEvidence() {
  const container = $("#evidence-list");
  if (!state.evidence.length) {
    container.innerHTML = '<p class="muted">No external evidence saved for this case.</p>';
    return;
  }

  container.innerHTML = state.evidence.map((item) => {
    const url = String(item.source_url || "");
    const safeURL = /^https:\/\//i.test(url) ? escapeHTML(url) : "";
    return `<div class="record-item">
      <div>
        <strong>${escapeHTML(item.source_name || "External source")}</strong>
        <small>${escapeHTML(item.claim || "No claim supplied")}</small>
        ${safeURL ? `<small><a href="${safeURL}" target="_blank" rel="noopener noreferrer">Open source ↗</a></small>` : ""}
        ${item.validation_reason ? `<small>${escapeHTML(item.validation_reason)}</small>` : ""}
        <small>Retrieved: ${displayDate(item.retrieved_at)}</small>
      </div>
      <div class="record-side">${statusPill(item.validation_status)}</div>
    </div>`;
  }).join("");
}

function renderProfile(item) {
  const fields = [
    ["Business type", item.business_type || "Not specified"],
    ["Loan amount", displayMoney(item.loan_amount, item.currency || "INR")],
    ["Purpose", item.loan_purpose || "—"],
    ["Created", displayDate(item.created_at)],
    ["Case ID", item.id],
  ];

  $("#case-profile").innerHTML = fields.map(([label, value]) => `
    <div class="profile-row">
      <span>${escapeHTML(label)}</span>
      <strong>${escapeHTML(value)}</strong>
    </div>
  `).join("");
}

async function openCase(caseId) {
  try {
    const item = await api(`/cases/${encodeURIComponent(caseId)}`);
    state.selectedCase = item;
    state.assessment = null;
    state.documents = [];
    state.evidence = [];

    $("#case-name").textContent = item.business_name;
    $("#case-subtitle").textContent =
      `${item.business_type || "Business"} · Case ${item.id}`;
    $("#case-status").className = `status-pill ${escapeHTML(item.status)}`;
    $("#case-status").textContent = readable(item.status);
    $("#evidence-entity").value = item.business_name;
    renderProfile(item);

    $("#assessment-results").hidden = true;
    $("#current-period").value = "";
    $("#previous-period").value = "";
    $("#document-file").value = "";
    $("#file-name").textContent = "No file selected";

    $("#documents-list").innerHTML = '<p class="muted">Loading documents…</p>';
    $("#evidence-list").innerHTML = '<p class="muted">Loading evidence…</p>';

    setView("case");

    const [docs, evidence] = await Promise.all([
      api(`/cases/${encodeURIComponent(caseId)}/documents`),
      api(`/cases/${encodeURIComponent(caseId)}/evidence`),
    ]);

    state.documents = docs.items || [];
    state.evidence = evidence.items || [];
    renderDocuments();
    renderEvidence();
  } catch (error) {
    showToast(`Unable to open investigation: ${error.message}`, "error");
  }
}

async function createCase(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const button = $("#create-case-button");
  const data = new FormData(form);
  const payload = {
    business_name: data.get("business_name").trim(),
    business_type: data.get("business_type").trim() || null,
    loan_amount: Number(data.get("loan_amount")),
    loan_purpose: data.get("loan_purpose").trim(),
    currency: "INR",
    notes: data.get("notes").trim() || null,
  };

  setButtonLoading(button, true, "Creating…");
  $("#case-form-error").hidden = true;

  try {
    const item = await api("/cases", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    closeCaseModal();
    await loadCases();
    showToast("Investigation created successfully.", "success");
    await openCase(item.id);
  } catch (error) {
    $("#case-form-error").textContent = error.message;
    $("#case-form-error").hidden = false;
  } finally {
    setButtonLoading(button, false);
  }
}

async function uploadDocument(event) {
  event.preventDefault();
  if (!state.selectedCase) return;

  const fileInput = $("#document-file");
  const file = fileInput.files[0];
  if (!file) {
    showToast("Choose a document first.", "error");
    return;
  }

  const button = $("#upload-button");
  const data = new FormData();
  data.append("file", file);

  setButtonLoading(button, true, "Uploading…");
  try {
    await api(`/cases/${encodeURIComponent(state.selectedCase.id)}/documents`, {
      method: "POST",
      body: data,
    });
    showToast("Document uploaded and processed.", "success");
    state.documents = (await api(
      `/cases/${encodeURIComponent(state.selectedCase.id)}/documents`,
    )).items || [];
    renderDocuments();
    fileInput.value = "";
    $("#file-name").textContent = "No file selected";
    await loadCases();
  } catch (error) {
    showToast(`Upload failed: ${error.message}`, "error");
  } finally {
    setButtonLoading(button, false);
  }
}

async function collectEvidence(event) {
  event.preventDefault();
  if (!state.selectedCase) return;

  const button = $("#collect-button");
  const payload = {
    query: $("#evidence-query").value.trim(),
    expected_entity: $("#evidence-entity").value.trim(),
    max_results: Number($("#evidence-limit").value),
  };

  setButtonLoading(button, true, "Collecting…");
  try {
    const result = await api(
      `/cases/${encodeURIComponent(state.selectedCase.id)}/evidence/collect`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      },
    );

    state.evidence = (await api(
      `/cases/${encodeURIComponent(state.selectedCase.id)}/evidence`,
    )).items || [];
    renderEvidence();
    await loadCases();

    const saved = result.saved_count ?? result.created_count;
    showToast(
      saved === undefined
        ? "Evidence collection finished. Review the saved source list."
        : `Evidence collection finished. ${saved} record(s) saved.`,
      "success",
    );
  } catch (error) {
    showToast(`Evidence collection failed: ${error.message}`, "error");
  } finally {
    setButtonLoading(button, false);
  }
}

function formatMetricValue(metric) {
  if (metric.value === null || metric.value === undefined) return "Unavailable";
  const value = Number(metric.value);
  if (!Number.isFinite(value)) return String(metric.value);
  const unit = String(metric.unit || "").toLowerCase();

  if (unit.includes("%") || unit.includes("percent")) return `${value.toFixed(2)}%`;
  if (unit.includes("ratio") || unit === "x") return `${value.toFixed(2)}×`;
  return `${value.toLocaleString("en-IN", { maximumFractionDigits: 2 })}${metric.unit ? ` ${metric.unit}` : ""}`;
}

function renderAssessment(assessment) {
  state.assessment = assessment;
  $("#assessment-results").hidden = false;

  const risk = assessment.risk_assessment || {};
  const analysis = assessment.financial_analysis || {};
  const metrics = Array.isArray(analysis.metrics) ? analysis.metrics : [];
  const findings = Array.isArray(risk.findings) ? risk.findings : [];

  $("#assessment-summary").innerHTML = [
    ["Overall status", readable(risk.overall_status || "Needs review"), "green"],
    ["Documents analyzed", assessment.documents_analyzed ?? 0, "violet"],
    ["Evidence records", assessment.external_evidence_count ?? 0, "blue"],
    ["Risk findings", risk.finding_count ?? findings.length, "amber"],
  ].map(([label, value, color]) => `
    <article class="stat-card">
      <div class="stat-top">${escapeHTML(label)}<span class="stat-icon ${color}">•</span></div>
      <div class="stat-value" style="font-size:22px">${escapeHTML(value)}</div>
    </article>
  `).join("");

  $("#financial-metrics").innerHTML = metrics.length
    ? metrics.map((metric) => `
        <div class="metric-row">
          <span>${escapeHTML(readable(metric.name || metric.metric || "Metric"))}</span>
          <strong>${escapeHTML(formatMetricValue(metric))}</strong>
        </div>
      `).join("")
    : '<p class="muted">No financial metrics could be calculated. Check the extracted values and reporting periods.</p>';

  $("#risk-findings").innerHTML = findings.length
    ? findings.map((finding) => {
        const severity = String(finding.severity || finding.level || "neutral").toLowerCase();
        return `<div class="finding ${escapeHTML(severity)}">
          <h4>${escapeHTML(readable(finding.title || finding.name || finding.code || "Finding"))}</h4>
          <p>${escapeHTML(finding.description || finding.reason || finding.message || "Review this finding in context.")}</p>
        </div>`;
      }).join("")
    : '<p class="muted">No risk findings were returned. This does not itself establish that the business is low risk.</p>';

  const limitations = [
    ...(Array.isArray(assessment.limitations) ? assessment.limitations : []),
    ...(Array.isArray(analysis.limitations) ? analysis.limitations : []),
    ...(Array.isArray(risk.limitations) ? risk.limitations : []),
    ...(risk.disclaimer ? [risk.disclaimer] : []),
  ];

  $("#limitations-list").innerHTML = limitations.length
    ? [...new Set(limitations)].map((item) => `<li>${escapeHTML(item)}</li>`).join("")
    : "<li>Manually verify source documents, financial figures, and external claims before relying on this assessment.</li>";

  $("#assessment-results").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function runAssessment() {
  if (!state.selectedCase) return;

  const button = $("#run-assessment");
  const params = new URLSearchParams();
  const current = $("#current-period").value.trim();
  const previous = $("#previous-period").value.trim();
  if (current) params.set("current_period", current);
  if (previous) params.set("previous_period", previous);

  const query = params.toString();
  const path = `/cases/${encodeURIComponent(state.selectedCase.id)}/risk-assessment${query ? `?${query}` : ""}`;

  setButtonLoading(button, true, "Analyzing…");
  try {
    const result = await api(path, { method: "POST" });
    renderAssessment(result);
    showToast("Preliminary risk assessment generated.", "success");
  } catch (error) {
    showToast(`Assessment failed: ${error.message}`, "error");
  } finally {
    setButtonLoading(button, false);
  }
}

function bindEvents() {
  document.querySelectorAll("[data-view]").forEach((button) => {
    button.addEventListener("click", () => setView(button.dataset.view));
  });

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-open-case]");
    if (button) openCase(button.dataset.openCase);
  });

  $("#new-case-button").addEventListener("click", openCaseModal);
  $("#welcome-new-case").addEventListener("click", openCaseModal);
  $("#list-new-case").addEventListener("click", openCaseModal);
  $("#close-modal").addEventListener("click", closeCaseModal);
  $("#cancel-modal").addEventListener("click", closeCaseModal);
  $("#case-modal").addEventListener("click", (event) => {
    if (event.target === $("#case-modal")) closeCaseModal();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeCaseModal();
  });

  $("#case-form").addEventListener("submit", createCase);
  $("#upload-form").addEventListener("submit", uploadDocument);
  $("#evidence-form").addEventListener("submit", collectEvidence);
  $("#run-assessment").addEventListener("click", runAssessment);
  $("#refresh-cases").addEventListener("click", async () => {
    try {
      await loadCases();
      showToast("Workspace refreshed.", "success");
    } catch (error) {
      showToast(`Refresh failed: ${error.message}`, "error");
    }
  });
  $("#back-to-cases").addEventListener("click", () => setView("investigations"));

  $("#document-file").addEventListener("change", (event) => {
    $("#file-name").textContent = event.target.files[0]?.name || "No file selected";
  });
}

async function init() {
  $("#today-label").textContent = new Date().toLocaleDateString(undefined, {
    weekday: "short", day: "numeric", month: "short", year: "numeric",
  });
  bindEvents();
  await checkAPI();

  try {
    await loadCases();
  } catch (error) {
    showToast(`Could not load cases: ${error.message}`, "error");
  }
}

document.addEventListener("DOMContentLoaded", init);
