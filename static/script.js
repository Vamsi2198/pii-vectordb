// AAGCP-Vector PRO Dashboard JavaScript

let piiChart = null;

function setupTabNavigation() {
  const tabButtons = document.querySelectorAll(".tab-button");
  tabButtons.forEach((button) => {
    button.addEventListener("click", () => {
      document.querySelectorAll(".tab-button").forEach((btn) => btn.classList.remove("active"));
      document.querySelectorAll(".app-view").forEach((view) => view.classList.add("hidden"));

      button.classList.add("active");
      const target = button.dataset.target;
      document.getElementById(target).classList.remove("hidden");
      document.getElementById(target).classList.add("active");
    });
  });
}

async function runDemo() {
  const runBtn = document.getElementById("runBtn");
  const spinner = document.getElementById("spinner");
  const results = document.getElementById("results");
  const errorBox = document.getElementById("errorBox");
  const statusBadge = document.getElementById("status");
  const statusMsg = document.getElementById("statusMsg");

  errorBox.classList.add("hidden");
  results.classList.add("hidden");
  spinner.classList.remove("hidden");
  runBtn.disabled = true;
  statusBadge.textContent = "Running";
  statusBadge.className = "status-badge running";
  statusMsg.textContent = "Executing pipeline...";

  try {
    const response = await fetch("/api/run-demo", { method: "POST" });
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }

    const result = await response.json();
    if (result.status === "success") {
      populateResults(result.data);
      results.classList.remove("hidden");
      statusBadge.textContent = "Complete";
      statusBadge.className = "status-badge complete";
      statusMsg.textContent = result.data.backend === "pinecone"
        ? "✓ Pinecone pipeline executed successfully"
        : "✓ Live pipeline executed successfully";
    } else {
      throw new Error("Pipeline failed");
    }
  } catch (error) {
    console.error("Error:", error);
    errorBox.classList.remove("hidden");
    document.getElementById("errorMsg").textContent = error.message;
    statusBadge.textContent = "Error";
    statusBadge.className = "status-badge error";
    statusMsg.textContent = "✗ An error occurred";
  } finally {
    spinner.classList.add("hidden");
    runBtn.disabled = false;
  }
}

function populateResults(data) {
  document.getElementById("regexCount").textContent =
    data.detector_coverage.regex_entity_count;
  document.getElementById("nerBackend").textContent =
    data.detector_coverage.ner_backend || "Not available";

  document.getElementById("beforeVectors").textContent =
    data.dirty_scan.total_vectors;
  document.getElementById("beforeWithPII").textContent =
    data.dirty_scan.vectors_with_pii;
  document.getElementById("beforePIICount").textContent =
    data.dirty_scan.total_pii_instances;

  document.getElementById("afterVectors").textContent =
    data.clean_scan.total_vectors;
  document.getElementById("afterWithPII").textContent =
    data.clean_scan.vectors_with_pii;
  document.getElementById("afterPIICount").textContent =
    data.clean_scan.total_pii_instances;

  document.getElementById("reembedded").textContent =
    data.migration_stats.reembedded;
  document.getElementById("quarantined").textContent =
    data.migration_stats.quarantined;
  document.getElementById("tokensMinted").textContent =
    data.migration_stats.tokens_minted;

  populateQueries("queriesBefore", data.queries_before);
  populateQueries("queriesAfterAnalyst", data.queries_after_analyst);
  populateQueries("queriesAfterCompliance", data.queries_after_compliance);

  updatePIIChart(data.dirty_scan.by_type);
}

function populateQueries(elementId, queries) {
  const container = document.getElementById(elementId);
  container.innerHTML = "";

  queries.forEach((query, idx) => {
    const item = document.createElement("div");
    item.className = "query-item";
    item.textContent = `${idx + 1}. ${query}`;
    container.appendChild(item);
  });

  if (queries.length === 0) {
    container.innerHTML = '<div class="query-item">No queries returned</div>';
  }
}

function updatePIIChart(byType) {
  const ctx = document.getElementById("piiChart");
  if (!ctx) return;

  if (piiChart) {
    piiChart.destroy();
  }

  const labels = Object.keys(byType);
  const data = Object.values(byType);
  const colors = generateColors(labels.length);

  piiChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: labels,
      datasets: [
        {
          data: data,
          backgroundColor: colors,
          borderColor: "#fff",
          borderWidth: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: "right",
          labels: {
            padding: 15,
            font: {
              size: 12,
              weight: "500",
            },
            usePointStyle: true,
          },
        },
      },
    },
  });
}

function generateColors(count) {
  const colors = [
    "#667eea",
    "#764ba2",
    "#f093fb",
    "#4facfe",
    "#43e97b",
    "#fa709a",
    "#fee140",
    "#30cfd0",
    "#a8edea",
    "#fed6e3",
    "#ff9a56",
    "#5f27cd",
  ];
  return Array.from({ length: count }, (_, idx) => colors[idx % colors.length]);
}

async function queryRag() {
  const authToken = document.getElementById("ragAuthToken").value.trim();
  const question = document.getElementById("ragQuestionInput").value.trim();
  const maskPii = document.getElementById("ragMaskPiiCheckbox").checked;
  const answerOutput = document.getElementById("ragAnswerOutput");
  const retrievedOutput = document.getElementById("ragRetrievedOutput");

  if (!question) {
    alert("Please enter a question.");
    return;
  }

  answerOutput.textContent = "Thinking...";
  retrievedOutput.innerHTML = "";

  try {
    const params = new URLSearchParams({
      question,
      authorization: authToken,
      mask_pii: String(maskPii),
    });
    const response = await fetch(`/rag/query?${params.toString()}`);
    if (!response.ok) {
      const body = await response.text();
      throw new Error(`Query failed: ${body}`);
    }
    const payload = await response.json();
    answerOutput.textContent = payload.answer || "No answer returned.";

    if (Array.isArray(payload.retrieved) && payload.retrieved.length) {
      retrievedOutput.innerHTML = "";
      payload.retrieved.slice(0, 5).forEach((item, index) => {
        const text = item.meta?.text ?? "(none)";
        const safeText = escapeHtml(text).replace(/\n/g, " ").slice(0, 420);
        const card = document.createElement("div");
        card.className = "chunk-item";
        card.innerHTML = `
          <strong>Chunk ${index + 1}</strong>
          <div><em>Score:</em> ${item.score?.toFixed(3) ?? "N/A"}</div>
          <div><em>Text:</em> ${safeText}</div>
        `;
        retrievedOutput.appendChild(card);
      });
    } else {
      retrievedOutput.textContent = "No chunks returned.";
    }
  } catch (error) {
    answerOutput.textContent = `Query error: ${error.message}`;
    retrievedOutput.textContent = "";
  }
}

async function uploadRagDocument() {
  const fileInput = document.getElementById("ragFileInput");
  const maskPii = document.getElementById("ragMaskPiiCheckbox").checked;
  const previewFrame = document.getElementById("ragPreviewFrame");
  const previewMessage = document.getElementById("ragPreviewMessage");

  if (!fileInput.files.length) {
    alert("Please choose a file to upload.");
    return;
  }

  const file = fileInput.files[0];
  const formData = new FormData();
  formData.append("file", file);
  formData.append("mask_pii", String(maskPii));

  try {
    const response = await fetch("/rag/upload", {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      const body = await response.text();
      throw new Error(`Upload failed: ${body}`);
    }
    const payload = await response.json();
    if (payload.preview_url) {
      previewFrame.src = payload.preview_url;
      previewFrame.hidden = false;
      previewMessage.textContent = "Preview of uploaded document.";
    }
  } catch (error) {
    previewFrame.hidden = true;
    previewMessage.textContent = `Upload error: ${error.message}`;
  }
}

async function loadRagDemoData() {
  try {
    const response = await fetch("/rag/api/load-demo-data", { method: "POST" });
    if (!response.ok) {
      throw new Error(`Demo load failed: ${response.status}`);
    }
    const payload = await response.json();
    alert(`Loaded ${payload.total_chunks} demo chunks.`);
    refreshRagIndexStatus();
  } catch (error) {
    alert(`Load demo data error: ${error.message}`);
  }
}

async function refreshRagIndexStatus() {
  const statusBox = document.getElementById("ragIndexStatus");
  if (!statusBox) return;
  statusBox.textContent = "Loading...";
  try {
    const response = await fetch("/rag/api/index-status");
    if (!response.ok) throw new Error(response.statusText);
    const payload = await response.json();
    statusBox.innerHTML = `Status: <strong>${payload.status}</strong><br>Total chunks: ${payload.total_chunks}`;
  } catch (error) {
    statusBox.textContent = `Unable to load index status: ${error.message}`;
  }
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function initialize() {
  setupTabNavigation();
  document.getElementById("ragUploadBtn").addEventListener("click", uploadRagDocument);
  document.getElementById("ragQueryBtn").addEventListener("click", queryRag);
  document.getElementById("ragLoadDemoBtn").addEventListener("click", loadRagDemoData);
  refreshRagIndexStatus();
  initMaskingStatus();
}

async function initMaskingStatus() {
  try {
    const res = await fetch("/api/status");
    const status = await res.json();
    const statusMsg = document.getElementById("statusMsg");
    const runBtn = document.getElementById("runBtn");
    if (status.backend === "pinecone") {
      statusMsg.textContent = `Pinecone: ${status.index_name} (${status.vector_count ?? "?"} vectors)`;
      runBtn.textContent = "▶ Run Pipeline on Pinecone";
    } else {
      statusMsg.textContent = "Live Pinecone backend unavailable — configure PINECONE_API_KEY";
      runBtn.textContent = "▶ Run Live AAGCP Pipeline";
    }
  } catch (e) {
    console.log('Dashboard loaded. Click "Run Demo Pipeline" to execute.');
  }
}

document.addEventListener("DOMContentLoaded", initialize);
