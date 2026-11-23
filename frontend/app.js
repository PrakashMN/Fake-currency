(() => {
  "use strict";

  const PAGE_SIZE = 8;

  const state = {
    file: null,
    page: 0,
    total: 0,
    filter: "all",
    modelMode: "demo",
    busy: false,
  };

  const $ = (id) => document.getElementById(id);

  const els = {
    modelPill: $("modelPill"),
    modelPillText: $("modelPillText"),
    statTotal: $("statTotal"),
    statFake: $("statFake"),
    statReal: $("statReal"),
    statConfidence: $("statConfidence"),
    dropzone: $("dropzone"),
    fileInput: $("fileInput"),
    preview: $("preview"),
    previewImg: $("previewImg"),
    clearBtn: $("clearBtn"),
    denomination: $("denomination"),
    detectBtn: $("detectBtn"),
    detectBtnLabel: $("detectBtnLabel"),
    demoHint: $("demoHint"),
    resultCard: $("resultCard"),
    resultEmpty: $("resultEmpty"),
    resultLoading: $("resultLoading"),
    resultBody: $("resultBody"),
    verdict: $("verdict"),
    verdictSub: $("verdictSub"),
    confidenceValue: $("confidenceValue"),
    confidenceBar: $("confidenceBar"),
    metaDenom: $("metaDenom"),
    metaMode: $("metaMode"),
    metaDate: $("metaDate"),
    metaFile: $("metaFile"),
    resultWarning: $("resultWarning"),
    downloadReport: $("downloadReport"),
    scanAnother: $("scanAnother"),
    historyTableWrap: $("historyTableWrap"),
    historyBody: $("historyBody"),
    historyEmpty: $("historyEmpty"),
    pager: $("pager"),
    pageLabel: $("pageLabel"),
    prevPage: $("prevPage"),
    nextPage: $("nextPage"),
    detailModal: $("detailModal"),
    modalClose: $("modalClose"),
    modalTitle: $("modalTitle"),
    modalImage: $("modalImage"),
    modalInfo: $("modalInfo"),
    modalReport: $("modalReport"),
    modalDelete: $("modalDelete"),
    toast: $("toast"),
    filterChips: Array.from(document.querySelectorAll(".chip[data-filter]")),
  };

  let activeDetectionId = null;
  let toastTimer = null;
  let previewUrl = null;
  let modalReturnFocus = null;

  /* ---------- Helpers ---------- */

  async function api(url, options = {}) {
    const response = await fetch(url, options);
    if (!response.ok) {
      let message = `Request failed (${response.status})`;
      try {
        const data = await response.json();
        if (typeof data.detail === "string") message = data.detail;
      } catch {
        /* keep default message */
      }
      throw new Error(message);
    }
    return response.json();
  }

  function formatDate(iso) {
    if (!iso) return "—";
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return iso;
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(date);
  }

  function formatDenomination(value) {
    if (!value || value === "unknown") return "Not specified";
    return `₹${value}`;
  }

  function modeLabel(mode) {
    return (
      {
        trained: "Trained model",
        demo: "Demo (simulated)",
        seeded: "Sample data",
      }[mode] ||
      mode ||
      "—"
    );
  }

  function createBadge(result) {
    const badge = document.createElement("span");
    const isFake = result === "FAKE";
    badge.className = `badge ${isFake ? "badge--fake" : "badge--real"}`;
    badge.textContent = isFake ? "Fake signal" : "Real label";
    return badge;
  }

  function toast(message, type = "info") {
    window.clearTimeout(toastTimer);
    els.toast.textContent = message;
    els.toast.className = `toast is-visible toast--${type}`;
    toastTimer = window.setTimeout(() => {
      els.toast.className = "toast";
    }, 4200);
  }

  function updateDetectButton() {
    els.detectBtn.disabled = state.busy || !state.file;
    els.detectBtn.setAttribute("aria-busy", state.busy ? "true" : "false");
    els.detectBtnLabel.textContent = state.busy ? "Analyzing…" : "Analyze image";
    els.resultCard.setAttribute("aria-busy", state.busy ? "true" : "false");
  }

  /* ---------- Data loading ---------- */

  async function loadModelInfo() {
    try {
      const info = await api("/api/model");
      state.modelMode = info.mode;
      els.modelPill.classList.remove("is-loading", "is-demo", "is-trained");

      if (info.mode === "trained") {
        els.modelPill.classList.add("is-trained");
        els.modelPillText.textContent = "Model active · ₹500 only";
        els.demoHint.hidden = true;
      } else {
        els.modelPill.classList.add("is-demo");
        els.modelPillText.textContent = "Demo mode — model not trained";
        els.demoHint.hidden = false;
        els.demoHint.textContent =
          "Demo mode: predictions are simulated because no trained model was found.";
      }
    } catch (error) {
      els.modelPill.classList.remove("is-loading");
      els.modelPill.classList.add("is-demo");
      els.modelPillText.textContent = "Model status unavailable";
      console.error(error);
    }
  }

  async function loadStats() {
    try {
      const stats = await api("/api/stats");
      els.statTotal.textContent = stats.total;
      els.statFake.textContent = stats.fake;
      els.statReal.textContent = stats.real;
      els.statConfidence.textContent = stats.total
        ? `${(stats.avg_confidence * 100).toFixed(1)}%`
        : "—";
    } catch (error) {
      console.error(error);
    }
  }

  async function loadHistory() {
    const params = new URLSearchParams({
      limit: String(PAGE_SIZE),
      offset: String(state.page * PAGE_SIZE),
    });
    if (state.filter !== "all") params.set("result", state.filter);

    try {
      const data = await api(`/api/detections?${params.toString()}`);
      state.total = data.total;
      renderHistory(data.items);
      renderPager();
    } catch (error) {
      console.error(error);
      toast("Could not load detection history.", "error");
    }
  }

  /* ---------- Rendering ---------- */

  function renderHistory(items) {
    els.historyBody.replaceChildren();

    const hasItems = items.length > 0;
    els.historyEmpty.hidden = hasItems;
    els.historyTableWrap.hidden = !hasItems;
    if (!hasItems) return;

    const fragment = document.createDocumentFragment();

    for (const item of items) {
      const row = document.createElement("tr");
      row.className = "history-row";
      row.tabIndex = 0;
      row.setAttribute("aria-label", `Open details for detection ${item.id}`);
      row.addEventListener("click", (event) => {
        if (event.target.closest("a, button")) return;
        openDetail(item.id);
      });
      row.addEventListener("keydown", (event) => {
        if (event.target !== row) return;
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          openDetail(item.id);
        }
      });

      const noteCell = document.createElement("td");
      const thumb = document.createElement("img");
      thumb.className = "thumb";
      thumb.src = item.image_url;
      thumb.alt = `Scanned note ${item.id}`;
      thumb.loading = "lazy";
      noteCell.append(thumb);

      const dateCell = document.createElement("td");
      dateCell.className = "muted";
      dateCell.textContent = formatDate(item.created_at);

      const denomCell = document.createElement("td");
      denomCell.textContent = formatDenomination(item.denomination);

      const resultCell = document.createElement("td");
      resultCell.append(createBadge(item.result));

      const confidenceCell = document.createElement("td");
      confidenceCell.textContent = `${(item.confidence * 100).toFixed(1)}%`;

      const reportCell = document.createElement("td");
      const reportLink = document.createElement("a");
      reportLink.className = "report-link";
      reportLink.href = item.report_url;
      reportLink.download = "";
      reportLink.textContent = "Download";
      reportLink.title = "Download PDF report";
      reportCell.append(reportLink);

      const actionCell = document.createElement("td");
      const deleteButton = document.createElement("button");
      deleteButton.className = "link-danger";
      deleteButton.type = "button";
      deleteButton.textContent = "Delete";
      deleteButton.setAttribute("aria-label", `Delete image classification ${item.id}`);
      deleteButton.addEventListener("click", () => deleteDetection(item.id));
      actionCell.append(deleteButton);

      row.append(
        noteCell,
        dateCell,
        denomCell,
        resultCell,
        confidenceCell,
        reportCell,
        actionCell
      );
      fragment.append(row);
    }

    els.historyBody.append(fragment);
  }

  function renderPager() {
    const pages = Math.max(1, Math.ceil(state.total / PAGE_SIZE));
    els.pager.hidden = state.total <= PAGE_SIZE;
    els.pageLabel.textContent = `Page ${state.page + 1} of ${pages}`;
    els.prevPage.disabled = state.page <= 0;
    els.nextPage.disabled = state.page >= pages - 1;
  }

  function showEmpty() {
    els.resultBody.hidden = true;
    els.resultLoading.hidden = true;
    els.resultEmpty.hidden = false;
  }

  function showLoading() {
    els.resultEmpty.hidden = true;
    els.resultBody.hidden = true;
    els.resultLoading.hidden = false;
  }

  function renderResult(data) {
    const isFake = data.result === "FAKE";
    const percentage = Math.round(data.confidence * 1000) / 10;

    els.resultEmpty.hidden = true;
    els.resultLoading.hidden = true;
    els.resultBody.hidden = false;

    els.verdict.textContent = isFake ? "Possible fake signal" : "Likely real label";
    els.verdict.className = `verdict ${
      isFake ? "verdict--fake" : "verdict--real"
    }`;
    els.verdictSub.textContent = isFake
      ? "The model flagged this image based on patterns in its training examples. This is not a counterfeit determination."
      : "The model classified this image as likely real. It can still be wrong; this result does not verify authenticity.";

    els.confidenceValue.textContent = `${percentage.toFixed(1)}%`;
    els.confidenceBar.parentElement.setAttribute(
      "aria-valuenow",
      String(Math.round(percentage))
    );
    els.confidenceBar.className = `bar__fill ${
      isFake ? "bar__fill--fake" : "bar__fill--real"
    }`;
    els.confidenceBar.style.width = "0%";
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        els.confidenceBar.style.width = `${percentage}%`;
      });
    });

    els.metaDenom.textContent = formatDenomination(data.denomination);
    els.metaMode.textContent = modeLabel(data.model_mode);
    els.metaDate.textContent = formatDate(data.created_at);
    els.metaFile.textContent = data.original_filename;

    if (data.warning) {
      els.resultWarning.hidden = false;
      els.resultWarning.textContent = data.warning;
    } else {
      els.resultWarning.hidden = true;
      els.resultWarning.textContent = "";
    }

    els.downloadReport.href = data.report_url;

    if (window.innerWidth < 1024) {
      els.resultCard.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  /* ---------- Upload flow ---------- */

  function setFile(file) {
    if (!file) return;

    const supportedExtensions = [".jpg", ".jpeg", ".png", ".webp", ".bmp"];
    const fileName = file.name.toLowerCase();
    if (!supportedExtensions.some((extension) => fileName.endsWith(extension))) {
      toast("Choose a JPG, PNG, WEBP, or BMP image.", "error");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      toast("Image is larger than 10 MB.", "error");
      return;
    }

    state.file = file;
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = URL.createObjectURL(file);

    els.previewImg.src = previewUrl;
    els.preview.hidden = false;
    els.dropzone.hidden = true;
    updateDetectButton();
  }

  function clearFile() {
    state.file = null;
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
      previewUrl = null;
    }
    els.previewImg.removeAttribute("src");
    els.preview.hidden = true;
    els.dropzone.hidden = false;
    els.fileInput.value = "";
    updateDetectButton();
  }

  async function detect() {
    if (!state.file || state.busy) return;

    state.busy = true;
    updateDetectButton();
    showLoading();

    const form = new FormData();
    form.append("file", state.file);
    form.append("denomination", els.denomination.value);

    try {
      const data = await api("/api/detect", { method: "POST", body: form });
      renderResult(data);
      state.page = 0;
      await Promise.all([loadStats(), loadHistory()]);
      toast("Detection saved and PDF report generated.", "success");
    } catch (error) {
      showEmpty();
      toast(error.message, "error");
    } finally {
      state.busy = false;
      updateDetectButton();
      els.resultLoading.hidden = true;
    }
  }

  /* ---------- Detail modal ---------- */

  async function openDetail(id) {
    const trigger = document.activeElement;
    try {
      const item = await api(`/api/detections/${id}`);
      activeDetectionId = id;
      modalReturnFocus = trigger;

      els.modalTitle.textContent = `Detection #${String(id).padStart(4, "0")}`;
      els.modalImage.src = item.image_url;
      els.modalImage.alt = `Scanned note ${id}`;
      els.modalReport.href = item.report_url;
      els.modalInfo.replaceChildren();

      appendDetail("Result", createBadge(item.result));
      appendDetail("Confidence", `${(item.confidence * 100).toFixed(1)}%`);
      appendDetail("Denomination", formatDenomination(item.denomination));
      appendDetail("Detected at", formatDate(item.created_at));
      appendDetail("Original file", item.original_filename);
      appendDetail("Model mode", modeLabel(item.model_mode));

      els.detailModal.hidden = false;
      document.body.classList.add("modal-open");
      els.modalClose.focus();
    } catch (error) {
      toast(error.message, "error");
    }
  }

  function appendDetail(label, value) {
    const row = document.createElement("div");
    row.className = "detail-row";

    const labelElement = document.createElement("span");
    labelElement.className = "detail-row__label";
    labelElement.textContent = label;

    const valueElement = document.createElement("span");
    valueElement.className = "detail-row__value";
    if (value instanceof Node) {
      valueElement.append(value);
    } else {
      valueElement.textContent = value;
    }

    row.append(labelElement, valueElement);
    els.modalInfo.append(row);
  }

  function closeModal() {
    els.detailModal.hidden = true;
    document.body.classList.remove("modal-open");
    activeDetectionId = null;
    const focusTarget = modalReturnFocus;
    modalReturnFocus = null;
    if (focusTarget instanceof HTMLElement && focusTarget.isConnected) {
      focusTarget.focus();
    }
  }

  async function deleteDetection(id) {
    const confirmed = window.confirm(
      `Delete detection #${String(id).padStart(4, "0")} and its report?`
    );
    if (!confirmed) return;

    try {
      await api(`/api/detections/${id}`, { method: "DELETE" });
      if (activeDetectionId === id) closeModal();

      const remaining = Math.max(0, state.total - 1);
      const lastPage = Math.max(0, Math.ceil(remaining / PAGE_SIZE) - 1);
      if (state.page > lastPage) state.page = lastPage;

      toast("Detection deleted.", "success");
      await Promise.all([loadHistory(), loadStats()]);
    } catch (error) {
      toast(error.message, "error");
    }
  }

  /* ---------- Events ---------- */

  function bindEvents() {
    els.fileInput.addEventListener("change", (event) => {
      setFile(event.target.files[0]);
      event.target.value = "";
    });

    ["dragenter", "dragover"].forEach((name) => {
      els.dropzone.addEventListener(name, (event) => {
        event.preventDefault();
        els.dropzone.classList.add("is-dragover");
      });
    });

    ["dragleave", "drop"].forEach((name) => {
      els.dropzone.addEventListener(name, (event) => {
        event.preventDefault();
        els.dropzone.classList.remove("is-dragover");
      });
    });

    els.dropzone.addEventListener("drop", (event) => {
      const file = event.dataTransfer.files[0];
      if (file) setFile(file);
    });

    els.clearBtn.addEventListener("click", clearFile);
    els.detectBtn.addEventListener("click", detect);

    els.scanAnother.addEventListener("click", () => {
      clearFile();
      showEmpty();
      els.denomination.value = "500";
      els.dropzone.scrollIntoView({ behavior: "smooth", block: "center" });
    });

    els.filterChips.forEach((chip) => {
      chip.addEventListener("click", () => {
        state.filter = chip.dataset.filter;
        state.page = 0;
        els.filterChips.forEach((item) =>
          item.classList.toggle("is-active", item === chip)
        );
        loadHistory();
      });
    });

    els.prevPage.addEventListener("click", () => {
      if (state.page > 0) {
        state.page -= 1;
        loadHistory();
      }
    });

    els.nextPage.addEventListener("click", () => {
      const pages = Math.max(1, Math.ceil(state.total / PAGE_SIZE));
      if (state.page < pages - 1) {
        state.page += 1;
        loadHistory();
      }
    });

    els.modalClose.addEventListener("click", closeModal);
    document
      .querySelectorAll("[data-close]")
      .forEach((element) => element.addEventListener("click", closeModal));

    document.addEventListener("keydown", (event) => {
      if (els.detailModal.hidden) return;

      if (event.key === "Escape") {
        closeModal();
        return;
      }

      if (event.key !== "Tab") return;
      const focusable = Array.from(
        els.detailModal.querySelectorAll(
          'a[href], button:not(:disabled), [tabindex]:not([tabindex="-1"])'
        )
      ).filter((element) => !element.hidden);
      if (!focusable.length) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    });

    els.modalDelete.addEventListener("click", () => {
      if (activeDetectionId !== null) deleteDetection(activeDetectionId);
    });
  }

  async function init() {
    bindEvents();
    await Promise.allSettled([loadModelInfo(), loadStats(), loadHistory()]);
  }

  init();
})();
