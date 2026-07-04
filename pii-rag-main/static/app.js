const uploadBtn = document.getElementById("uploadBtn");
const queryBtn = document.getElementById("queryBtn");
const fileInput = document.getElementById("fileInput");
const authTokenInput = document.getElementById("authToken");
const questionInput = document.getElementById("questionInput");
const uploadStatus = document.getElementById("uploadStatus");
const fileList = document.getElementById("fileList");
const answerOutput = document.getElementById("answerOutput");
const retrievedOutput = document.getElementById("retrievedOutput");
const previewFrame = document.getElementById("previewFrame");
const previewMessage = document.getElementById("previewMessage");
const maskPiiCheckbox = document.getElementById("maskPiiCheckbox");

let uploadedFiles = [];

function renderFileList() {
  if (!uploadedFiles.length) {
    fileList.textContent = "None";
    return;
  }

  fileList.innerHTML = "";
  uploadedFiles.forEach((name) => {
    const item = document.createElement("div");
    item.className = "file-item";
    item.textContent = name;
    fileList.appendChild(item);
  });
}

uploadBtn.addEventListener("click", async () => {
  const file = fileInput.files[0];
  if (!file) {
    alert("Please choose a PDF to upload.");
    return;
  }

  const formData = new FormData();
  formData.append("file", file);
  formData.append("mask_pii", String(maskPiiCheckbox.checked));

  uploadBtn.disabled = true;
  uploadStatus.textContent = "Uploading...";

  try {
    const response = await fetch("/upload", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      const body = await response.text();
      throw new Error(`Upload failed: ${body}`);
    }

    const payload = await response.json();
    uploadedFiles.unshift(payload.filename || file.name);
    uploadedFiles = uploadedFiles.slice(0, 5);
    renderFileList();
    const modeText = maskPiiCheckbox.checked ? "masked" : "raw";
    uploadStatus.textContent = `Uploaded ${payload.filename || file.name} (${modeText} mode).`;

    if (payload.preview_url) {
      previewFrame.src = payload.preview_url;
      previewFrame.hidden = false;
      previewMessage.textContent = "Preview of uploaded PDF.";
    }
  } catch (error) {
    uploadStatus.textContent = `Upload error: ${error.message}`;
    previewFrame.hidden = true;
    previewMessage.textContent = "Unable to preview the uploaded PDF.";
  } finally {
    uploadBtn.disabled = false;
  }
});

queryBtn.addEventListener("click", async () => {
  const question = questionInput.value.trim();
  const authToken = authTokenInput.value.trim();

  if (!question) {
    alert("Please enter a question.");
    return;
  }

  queryBtn.disabled = true;
  answerOutput.textContent = "Thinking...";
  retrievedOutput.innerHTML = "";

  try {
    const params = new URLSearchParams({
      question,
      authorization: authToken,
      mask_pii: String(maskPiiCheckbox.checked),
    });
    const response = await fetch(`/query?${params.toString()}`);

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
  } finally {
    queryBtn.disabled = false;
  }
});

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

renderFileList();
