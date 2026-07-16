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
const previewEmpty = document.querySelector("#preview-empty");
const preview = document.querySelector("#preview");
const previewImage = document.querySelector("#preview-image");
const fileName = document.querySelector("#file-name");
const fileMetrics = document.querySelector("#file-metrics");
const resultPlaceholder = document.querySelector("#result-placeholder");
const result = document.querySelector("#result");

document.querySelector("#raw-json").textContent = JSON.stringify(mockResult, null, 2);

function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function showFile(file) {
  if (!file || !file.type.startsWith("image/")) return;

  const reader = new FileReader();
  reader.addEventListener("load", () => {
    previewImage.src = reader.result;
    fileName.textContent = file.name;
    document.querySelector("#file-type").textContent = file.type || "Image";
    document.querySelector("#file-size").textContent = formatFileSize(file.size);
    document.querySelector("#upload-time").textContent = new Intl.DateTimeFormat([], {
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date());

    previewEmpty.hidden = true;
    preview.hidden = false;
    fileMetrics.hidden = false;
    resultPlaceholder.hidden = true;
    result.hidden = false;
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
