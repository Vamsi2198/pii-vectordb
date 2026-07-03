// AAGCP-Vector PRO Dashboard JavaScript

let piiChart = null;

async function runDemo() {
  const runBtn = document.getElementById("runBtn");
  const spinner = document.getElementById("spinner");
  const results = document.getElementById("results");
  const errorBox = document.getElementById("errorBox");
  const statusBadge = document.getElementById("status");
  const statusMsg = document.getElementById("statusMsg");

  // Reset UI
  errorBox.classList.add("hidden");
  results.classList.add("hidden");

  // Show spinner
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
      statusMsg.textContent = "✓ Demo executed successfully";
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
  // Detector Coverage
  document.getElementById("regexCount").textContent =
    data.detector_coverage.regex_entity_count;
  document.getElementById("nerBackend").textContent =
    data.detector_coverage.ner_backend || "Not available";

  // Before Cleaning
  document.getElementById("beforeVectors").textContent =
    data.dirty_scan.total_vectors;
  document.getElementById("beforeWithPII").textContent =
    data.dirty_scan.vectors_with_pii;
  document.getElementById("beforePIICount").textContent =
    data.dirty_scan.total_pii_instances;

  // After Cleaning
  document.getElementById("afterVectors").textContent =
    data.clean_scan.total_vectors;
  document.getElementById("afterWithPII").textContent =
    data.clean_scan.vectors_with_pii;
  document.getElementById("afterPIICount").textContent =
    data.clean_scan.total_pii_instances;

  // Migration Stats
  document.getElementById("reembedded").textContent =
    data.migration_stats.reembedded;
  document.getElementById("quarantined").textContent =
    data.migration_stats.quarantined;
  document.getElementById("tokensMinted").textContent =
    data.migration_stats.tokens_minted;

  // Queries
  populateQueries("queriesBefore", data.queries_before);
  populateQueries("queriesAfterAnalyst", data.queries_after_analyst);
  populateQueries("queriesAfterCompliance", data.queries_after_compliance);

  // Chart
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

  if (piiChart) {
    piiChart.destroy();
  }

  const labels = Object.keys(byType);
  const data = Object.values(byType);

  // Create color palette
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

  const result = [];
  for (let i = 0; i < count; i++) {
    result.push(colors[i % colors.length]);
  }
  return result;
}

// Auto-run on page load (optional - remove if you want manual trigger)
document.addEventListener("DOMContentLoaded", () => {
  console.log('Dashboard loaded. Click "Run Demo Pipeline" to execute.');
});
