(() => {
  "use strict";

  const ASPECT_RATIO = 350 / 255;
  const MIN_CROP_WIDTH = 70;
  const DEBOUNCE_MS = 350;
  const HANDLE_SIZE = 14;
  const DEFAULT_META = "Arraste ou clique";

  const state = {
    uploaded: { carro: false, peca: false, print: false },
    metaText: { carro: DEFAULT_META, peca: DEFAULT_META, print: DEFAULT_META },
    objectUrls: { carro: null, peca: null, print: null },
    uploadSeq: { carro: 0, peca: 0, print: 0 },
    uploadAbort: { carro: null, peca: null, print: null },
    printMeta: null,
    crop: null,
    drag: null,
    previewTimer: null,
    previewSeq: 0,
    previewAbort: null,
    isSaving: false,
  };

  const tituloInput = document.getElementById("titulo");
  const subtituloInput = document.getElementById("subtitulo");
  const subtituloContador = document.getElementById("subtitulo-contador");
  const etiquetaInput = document.getElementById("etiqueta");
  const cropSection = document.getElementById("crop-section");
  const cropInfo = document.getElementById("crop-info");
  const cropCanvasWrap = document.getElementById("crop-canvas-wrap");
  const cropCanvas = document.getElementById("crop-canvas");
  const btnCentralizar = document.getElementById("btn-centralizar-recorte");
  const erroBanner = document.getElementById("erro-banner");
  const previewStatus = document.getElementById("preview-status");
  const previewImg = document.getElementById("preview-img");
  const previewPlaceholder = document.getElementById("preview-placeholder");
  const avisosBox = document.getElementById("avisos-box");
  const avisosOk = document.getElementById("avisos-ok");
  const avisosLista = document.getElementById("avisos-lista");
  const btnBaixar = document.getElementById("btn-baixar");
  const statusSalvar = document.getElementById("status-salvar");

  function clamp(val, min, max) {
    return Math.min(Math.max(val, min), max);
  }

  function showError(msg) {
    erroBanner.textContent = msg;
    erroBanner.hidden = false;
  }

  function clearError() {
    erroBanner.textContent = "";
    erroBanner.hidden = true;
  }

  function allPhotosUploaded() {
    return state.uploaded.carro && state.uploaded.peca && state.uploaded.print;
  }

  function getSubtituloLinhas() {
    return subtituloInput.value
      .split(/\r?\n/)
      .map((linha) => linha.trim())
      .filter(Boolean);
  }

  function updateSubtitleCounter() {
    const count = getSubtituloLinhas().length;
    subtituloContador.textContent = `${count}/3 linhas`;
    subtituloContador.classList.toggle("is-over", count > 3);
  }

  function rectFromRecorte(recorte, serverW, serverH) {
    const [l, t, r] = recorte;
    const maxW = Math.min(serverW, serverH * ASPECT_RATIO);
    const w = clamp(Math.max(1, r - l), Math.min(MIN_CROP_WIDTH, maxW), maxW);
    const h = w / ASPECT_RATIO;
    const x = clamp(l, 0, Math.max(0, serverW - w));
    const y = clamp(t, 0, Math.max(0, serverH - h));
    return { x, y, w, h };
  }

  function recorteArrayFromCrop() {
    if (!state.crop || !state.printMeta) {
      return null;
    }
    const { width, height } = state.printMeta;
    const l = clamp(Math.round(state.crop.x), 0, Math.max(0, width - 1));
    const t = clamp(Math.round(state.crop.y), 0, Math.max(0, height - 1));
    const r = Math.max(l + 1, clamp(Math.round(state.crop.x + state.crop.w), 1, width));
    const b = Math.max(t + 1, clamp(Math.round(state.crop.y + state.crop.h), 1, height));
    return [l, t, r, b];
  }

  function buildPayload() {
    return {
      titulo: tituloInput.value,
      subtitulo: getSubtituloLinhas(),
      etiqueta: etiquetaInput.value,
      recorte_print: recorteArrayFromCrop(),
    };
  }

  function loadHtmlImage(src) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error("Não foi possível carregar a imagem no navegador."));
      img.src = src;
    });
  }

  function cancelPendingPreview() {
    if (state.previewTimer !== null) {
      clearTimeout(state.previewTimer);
      state.previewTimer = null;
    }
    state.previewSeq += 1;
    if (state.previewAbort) {
      state.previewAbort.abort();
      state.previewAbort = null;
    }
    previewStatus.hidden = true;
  }

  function showPreviewPlaceholder() {
    previewImg.hidden = true;
    previewImg.removeAttribute("src");
    previewPlaceholder.hidden = false;
    avisosBox.hidden = true;
  }

  function renderAvisos(avisos) {
    avisosBox.hidden = false;
    avisosLista.textContent = "";
    if (!avisos || avisos.length === 0) {
      avisosOk.hidden = false;
      avisosLista.hidden = true;
      return;
    }
    avisosOk.hidden = true;
    avisosLista.hidden = false;
    for (const texto of avisos) {
      const li = document.createElement("li");
      li.textContent = texto;
      avisosLista.appendChild(li);
    }
  }

  function schedulePreview() {
    cancelPendingPreview();
    if (!allPhotosUploaded() || !tituloInput.value.trim()) {
      showPreviewPlaceholder();
      return;
    }
    state.previewTimer = setTimeout(runPreview, DEBOUNCE_MS);
  }

  async function runPreview() {
    state.previewTimer = null;
    if (!allPhotosUploaded() || !tituloInput.value.trim()) {
      showPreviewPlaceholder();
      return;
    }

    const seq = ++state.previewSeq;
    const controller = new AbortController();
    state.previewAbort = controller;
    previewStatus.hidden = false;

    try {
      const res = await fetch("/api/previa", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildPayload()),
        signal: controller.signal,
      });
      const data = await res.json().catch(() => ({}));
      if (seq !== state.previewSeq) {
        return;
      }
      if (!res.ok) {
        showError(data.erro || "Erro ao gerar a prévia.");
        return;
      }
      clearError();
      previewImg.src = `data:image/png;base64,${data.png}`;
      previewImg.hidden = false;
      previewPlaceholder.hidden = true;
      renderAvisos(data.avisos);
    } catch (err) {
      if (err && err.name === "AbortError") {
        return;
      }
      if (seq === state.previewSeq) {
        showError("Erro de conexão ao gerar a prévia.");
      }
    } finally {
      if (seq === state.previewSeq) {
        state.previewAbort = null;
        previewStatus.hidden = true;
      }
    }
  }

  function layoutCropCanvas() {
    if (!state.printMeta || cropSection.hidden) {
      return;
    }
    const availableW = Math.max(220, (cropCanvasWrap.clientWidth || 420) - 12);
    const maxH = 380;
    const scale = Math.min(availableW / state.printMeta.width, maxH / state.printMeta.height);
    const displayW = Math.max(1, Math.round(state.printMeta.width * scale));
    const displayH = Math.max(1, Math.round(state.printMeta.height * scale));
    const dpr = window.devicePixelRatio || 1;

    cropCanvas.width = Math.round(displayW * dpr);
    cropCanvas.height = Math.round(displayH * dpr);
    cropCanvas.style.width = `${displayW}px`;
    cropCanvas.style.height = `${displayH}px`;
    renderCropCanvas();
  }

  function renderCropCanvas() {
    if (!state.printMeta || !state.crop) {
      return;
    }
    const displayW = parseFloat(cropCanvas.style.width) || cropCanvas.clientWidth;
    const displayH = parseFloat(cropCanvas.style.height) || cropCanvas.clientHeight;
    if (!displayW || !displayH) {
      return;
    }

    const dpr = window.devicePixelRatio || 1;
    const ctx = cropCanvas.getContext("2d");
    if (!ctx) {
      return;
    }

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, displayW, displayH);
    ctx.drawImage(state.printMeta.image, 0, 0, displayW, displayH);

    const scaleX = displayW / state.printMeta.width;
    const scaleY = displayH / state.printMeta.height;
    const rx = state.crop.x * scaleX;
    const ry = state.crop.y * scaleY;
    const rw = state.crop.w * scaleX;
    const rh = state.crop.h * scaleY;

    ctx.fillStyle = "rgba(15, 23, 42, 0.58)";
    ctx.fillRect(0, 0, displayW, Math.max(0, ry));
    ctx.fillRect(0, ry + rh, displayW, Math.max(0, displayH - (ry + rh)));
    ctx.fillRect(0, ry, Math.max(0, rx), rh);
    ctx.fillRect(rx + rw, ry, Math.max(0, displayW - (rx + rw)), rh);

    ctx.strokeStyle = "rgba(255, 255, 255, 0.28)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(rx + rw / 3, ry);
    ctx.lineTo(rx + rw / 3, ry + rh);
    ctx.moveTo(rx + (2 * rw) / 3, ry);
    ctx.lineTo(rx + (2 * rw) / 3, ry + rh);
    ctx.moveTo(rx, ry + rh / 3);
    ctx.lineTo(rx + rw, ry + rh / 3);
    ctx.moveTo(rx, ry + (2 * rh) / 3);
    ctx.lineTo(rx + rw, ry + (2 * rh) / 3);
    ctx.stroke();

    ctx.strokeStyle = "rgba(0, 0, 0, 0.5)";
    ctx.lineWidth = 3;
    ctx.strokeRect(rx, ry, rw, rh);

    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 2;
    ctx.strokeRect(rx, ry, rw, rh);

    const hx = Math.max(0, rx + rw - HANDLE_SIZE);
    const hy = Math.max(0, ry + rh - HANDLE_SIZE);
    ctx.fillStyle = "#1677ff";
    ctx.fillRect(hx, hy, HANDLE_SIZE, HANDLE_SIZE);
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 2;
    ctx.strokeRect(hx, hy, HANDLE_SIZE, HANDLE_SIZE);

    ctx.beginPath();
    ctx.moveTo(hx + 4, hy + HANDLE_SIZE - 4);
    ctx.lineTo(hx + HANDLE_SIZE - 4, hy + 4);
    ctx.stroke();

    cropInfo.textContent =
      `Proporção 350:255 • ${Math.round(state.crop.w)} × ${Math.round(state.crop.h)} px` +
      ` (x=${Math.round(state.crop.x)}, y=${Math.round(state.crop.y)})`;
  }

  function getPointerInfo(e) {
    const rect = cropCanvas.getBoundingClientRect();
    const dx = e.clientX - rect.left;
    const dy = e.clientY - rect.top;
    const { width: serverW, height: serverH } = state.printMeta;
    const sx = dx * (serverW / rect.width);
    const sy = dy * (serverH / rect.height);

    const rx = state.crop.x * (rect.width / serverW);
    const ry = state.crop.y * (rect.height / serverH);
    const rw = state.crop.w * (rect.width / serverW);
    const rh = state.crop.h * (rect.height / serverH);

    const hxMin = rw <= 28 ? rx + rw * 0.55 : rx + rw - 18;
    const hyMin = rh <= 28 ? ry + rh * 0.55 : ry + rh - 18;
    const inHandle = dx >= hxMin && dx <= rx + rw + 6 && dy >= hyMin && dy <= ry + rh + 6;
    const inBox = dx >= rx && dx <= rx + rw && dy >= ry && dy <= ry + rh;

    return { sx, sy, inHandle, inBox };
  }

  cropCanvas.addEventListener("pointerdown", (e) => {
    if (!state.crop || !state.printMeta) {
      return;
    }
    if (e.pointerType === "mouse" && e.button !== 0) {
      return;
    }
    const { sx, sy, inHandle, inBox } = getPointerInfo(e);
    if (!inHandle && !inBox) {
      return;
    }

    e.preventDefault();
    cropCanvas.setPointerCapture(e.pointerId);
    const mode = inHandle ? "resize" : "move";
    state.drag = {
      mode,
      pointerId: e.pointerId,
      startX: sx,
      startY: sy,
      startCrop: { ...state.crop },
    };
    cropCanvas.style.cursor = mode === "resize" ? "nwse-resize" : "grabbing";
  });

  cropCanvas.addEventListener("pointermove", (e) => {
    if (!state.crop || !state.printMeta) {
      return;
    }
    const { sx, sy, inHandle, inBox } = getPointerInfo(e);

    if (!state.drag) {
      cropCanvas.style.cursor = inHandle ? "nwse-resize" : inBox ? "grab" : "default";
      return;
    }
    if (e.pointerId !== state.drag.pointerId) {
      return;
    }

    const { width: serverW, height: serverH } = state.printMeta;
    const { startCrop, startX, startY, mode } = state.drag;

    if (mode === "move") {
      const maxX = Math.max(0, serverW - startCrop.w);
      const maxY = Math.max(0, serverH - startCrop.h);
      state.crop.x = clamp(startCrop.x + (sx - startX), 0, maxX);
      state.crop.y = clamp(startCrop.y + (sy - startY), 0, maxY);
    } else {
      const dx = sx - startX;
      const dy = sy - startY;
      const wFromX = startCrop.w + dx;
      const wFromY = (startCrop.h + dy) * ASPECT_RATIO;
      const candidateW = Math.abs(dx) / 350 >= Math.abs(dy) / 255 ? wFromX : wFromY;
      const maxW = Math.min(serverW - startCrop.x, (serverH - startCrop.y) * ASPECT_RATIO);
      const minW = Math.min(MIN_CROP_WIDTH, maxW);
      const nextW = clamp(candidateW, minW, maxW);
      state.crop.w = nextW;
      state.crop.h = nextW / ASPECT_RATIO;
    }

    renderCropCanvas();
    schedulePreview();
  });

  function endCropDrag(e) {
    if (!state.drag || e.pointerId !== state.drag.pointerId) {
      return;
    }
    if (cropCanvas.hasPointerCapture && cropCanvas.hasPointerCapture(e.pointerId)) {
      cropCanvas.releasePointerCapture(e.pointerId);
    }
    state.drag = null;
    if (state.crop && state.printMeta) {
      const { inHandle, inBox } = getPointerInfo(e);
      cropCanvas.style.cursor = inHandle ? "nwse-resize" : inBox ? "grab" : "default";
    } else {
      cropCanvas.style.cursor = "default";
    }
  }

  cropCanvas.addEventListener("pointerup", endCropDrag);
  cropCanvas.addEventListener("pointercancel", endCropDrag);

  btnCentralizar.addEventListener("click", () => {
    if (!state.printMeta) {
      return;
    }
    state.crop = rectFromRecorte(
      state.printMeta.initialRecorte,
      state.printMeta.width,
      state.printMeta.height
    );
    renderCropCanvas();
    schedulePreview();
  });

  async function uploadImage(tipo, file) {
    if (!file) {
      return;
    }
    const dropzone = document.querySelector(`.dropzone[data-tipo="${tipo}"]`);
    const metaEl = dropzone.querySelector(".dropzone-meta");
    const thumbWrap = dropzone.querySelector(".dropzone-thumb-wrap");
    const thumbImg = dropzone.querySelector(".dropzone-thumb");

    if (state.uploadAbort[tipo]) {
      state.uploadAbort[tipo].abort();
    }
    const seq = ++state.uploadSeq[tipo];
    const controller = new AbortController();
    state.uploadAbort[tipo] = controller;

    dropzone.classList.add("is-uploading");
    metaEl.textContent = "Enviando...";
    cancelPendingPreview();

    const formData = new FormData();
    formData.append("arquivo", file);

    try {
      const res = await fetch(`/api/imagem/${tipo}`, {
        method: "POST",
        body: formData,
        signal: controller.signal,
      });
      const data = await res.json().catch(() => ({}));
      if (seq !== state.uploadSeq[tipo]) {
        return;
      }
      if (!res.ok) {
        metaEl.textContent = state.metaText[tipo];
        showError(data.erro || "Não foi possível enviar a imagem.");
        return;
      }

      const nextUrl = URL.createObjectURL(file);
      let loadedPrintImg = null;
      if (tipo === "print") {
        try {
          loadedPrintImg = await loadHtmlImage(nextUrl);
        } catch (err) {
          URL.revokeObjectURL(nextUrl);
          throw err;
        }
        if (seq !== state.uploadSeq[tipo]) {
          URL.revokeObjectURL(nextUrl);
          return;
        }
      }

      if (state.objectUrls[tipo]) {
        URL.revokeObjectURL(state.objectUrls[tipo]);
      }
      state.objectUrls[tipo] = nextUrl;
      state.uploaded[tipo] = true;

      thumbImg.src = nextUrl;
      thumbWrap.hidden = false;
      const resumo = `${file.name} (${data.largura}×${data.altura})`;
      state.metaText[tipo] = resumo;
      metaEl.textContent = resumo;
      metaEl.title = resumo;
      dropzone.classList.add("is-uploaded");
      clearError();

      if (tipo === "print" && loadedPrintImg) {
        state.drag = null;
        state.printMeta = {
          width: data.largura,
          height: data.altura,
          area: data.area,
          initialRecorte: data.recorte,
          image: loadedPrintImg,
        };
        state.crop = rectFromRecorte(data.recorte, data.largura, data.altura);
        cropSection.hidden = false;
        layoutCropCanvas();
      }

      schedulePreview();
    } catch (err) {
      if (err && err.name === "AbortError") {
        return;
      }
      if (seq === state.uploadSeq[tipo]) {
        metaEl.textContent = state.metaText[tipo];
        showError("Erro de conexão ao enviar a imagem.");
      }
    } finally {
      if (seq === state.uploadSeq[tipo]) {
        state.uploadAbort[tipo] = null;
        dropzone.classList.remove("is-uploading");
      }
    }
  }

  document.querySelectorAll(".dropzone").forEach((dropzone) => {
    const tipo = dropzone.dataset.tipo;
    const input = dropzone.querySelector(".dropzone-input");

    input.addEventListener("change", () => {
      const file = input.files && input.files[0];
      input.value = "";
      if (file) {
        uploadImage(tipo, file);
      }
    });

    dropzone.addEventListener("dragenter", (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add("is-dragover");
    });

    dropzone.addEventListener("dragover", (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (e.dataTransfer) {
        e.dataTransfer.dropEffect = "copy";
      }
      dropzone.classList.add("is-dragover");
    });

    dropzone.addEventListener("dragleave", (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (!dropzone.contains(e.relatedTarget)) {
        dropzone.classList.remove("is-dragover");
      }
    });

    dropzone.addEventListener("drop", (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove("is-dragover");
      const file = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
      if (file) {
        uploadImage(tipo, file);
      }
    });
  });

  function slugifyTitulo(titulo) {
    const semAcentos = (titulo || "").normalize("NFKD").replace(/[\u0300-\u036f]/g, "");
    const slug = semAcentos.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
    return slug || "anuncio";
  }

  function parseDownloadFilename(disposition, fallbackTitulo) {
    if (disposition) {
      const utf8Match = /filename\*=UTF-8''([^;]+)/i.exec(disposition);
      if (utf8Match) {
        try {
          return decodeURIComponent(utf8Match[1].trim().replace(/^"|"$/g, ""));
        } catch {
          // Segue para fallback simples.
        }
      }
      const plainMatch = /filename="?([^";]+)"?/i.exec(disposition);
      if (plainMatch && plainMatch[1].trim()) {
        return plainMatch[1].trim();
      }
    }
    return `${slugifyTitulo(fallbackTitulo)}.png`;
  }

  async function salvarPng() {
    if (state.isSaving) {
      return;
    }
    statusSalvar.hidden = true;
    statusSalvar.textContent = "";
    state.isSaving = true;
    btnBaixar.disabled = true;
    btnBaixar.textContent = "Salvando...";

    try {
      const res = await fetch("/api/salvar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildPayload()),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        showError(data.erro || "Erro ao salvar o PNG.");
        return;
      }

      clearError();
      const filename = parseDownloadFilename(res.headers.get("Content-Disposition"), tituloInput.value);
      const blob = await res.blob();
      const downloadUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = downloadUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(downloadUrl), 1000);

      statusSalvar.textContent = `Salvo em saida/${filename}`;
      statusSalvar.hidden = false;
    } catch {
      showError("Erro de conexão ao salvar o PNG.");
    } finally {
      state.isSaving = false;
      btnBaixar.disabled = false;
      btnBaixar.textContent = "Baixar PNG";
    }
  }

  tituloInput.addEventListener("input", schedulePreview);
  subtituloInput.addEventListener("input", () => {
    updateSubtitleCounter();
    schedulePreview();
  });
  etiquetaInput.addEventListener("input", schedulePreview);
  btnBaixar.addEventListener("click", salvarPng);

  if (typeof ResizeObserver !== "undefined") {
    new ResizeObserver(() => layoutCropCanvas()).observe(cropCanvasWrap);
  } else {
    window.addEventListener("resize", layoutCropCanvas);
  }

  updateSubtitleCounter();
})();
