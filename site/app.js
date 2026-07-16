const mockResult = {
  status: "success",
  recognized_text: {
    product_name: "Ethanol",
    brand: "Sigma-Aldrich",
    catalog_no: "459836",
    expiration_date: "2027-04-30",
    quantity: "500 mL",
    storage: "Room temperature",
  },
  confidence: 0.92,
  review_state: "Ready for inventory match",
};

const input = document.querySelector("#label-image");
const dropZone = document.querySelector("#drop-zone");
const preview = document.querySelector("#preview");
const previewImage = document.querySelector("#preview-image");
const scanStage = document.querySelector("#scan-stage");
const fileMeta = document.querySelector("#file-meta");
const fileName = document.querySelector("#file-name");
const fileProperties = document.querySelector("#file-properties");
const resultPlaceholder = document.querySelector("#result-placeholder");
const result = document.querySelector("#result");
const confirmationNote = document.querySelector("#confirmation-note");
const confirmButton = document.querySelector("#confirm-result");

document.querySelector("#raw-json").textContent = JSON.stringify(mockResult, null, 2);

function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatFileType(file) {
  return (file.type || "Image").replace("image/", "").toUpperCase();
}

function showFile(file) {
  if (!file || !file.type.startsWith("image/")) return;

  const reader = new FileReader();
  reader.addEventListener("load", () => {
    previewImage.src = reader.result;
    fileName.textContent = file.name;
    fileProperties.textContent = `${formatFileType(file)} - ${formatFileSize(file.size)} - ${new Intl.DateTimeFormat([], {
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date())}`;

    dropZone.hidden = true;
    preview.hidden = false;
    fileMeta.hidden = false;
    resultPlaceholder.hidden = true;
    result.hidden = false;
    confirmationNote.hidden = true;
    scanStage.classList.add("has-file");
  });
  reader.readAsDataURL(file);
}

input.addEventListener("change", () => showFile(input.files[0]));

for (const eventName of ["dragenter", "dragover"]) {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.add("dragging");
  });
}

for (const eventName of ["dragleave", "drop"]) {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.remove("dragging");
  });
}

dropZone.addEventListener("drop", (event) => showFile(event.dataTransfer.files[0]));

confirmButton.addEventListener("click", () => {
  confirmationNote.hidden = false;
  confirmButton.textContent = "Result confirmed";
  confirmButton.disabled = true;
});
