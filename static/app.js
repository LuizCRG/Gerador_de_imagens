(() => {
  "use strict";

  const ASPECT_RATIO = 350 / 255;
  const MIN_CROP_WIDTH = 70;
  const MIN_CROP_SIZE = 40;
  const DEBOUNCE_MS = 350;
  const HANDLE_SIZE = 14;
  const DEFAULT_META = "Arraste ou clique";
  const TIPOS_IMAGEM = ["carro", "peca", "print"];

  const DEFAULTS = {
    larguraCarro: 500,
    escalaPecaPct: 100,
    larguraPrint: 350,
    tamTitulo: 132,
    tamSub: 40,
    tamEtiqueta: 24,
  };

  const iaStatusEl = document.getElementById("ia-status");
  const btnIaConfig = document.getElementById("btn-ia-config");
  const iaConfigPanel = document.getElementById("ia-config-panel");
  const iaApiKeyInput = document.getElementById("ia-api-key");
  const btnSalvarChave = document.getElementById("btn-salvar-chave");

  const state = {
    uploaded: { carro: false, peca: false, print: false },
    fileName: { carro: "", peca: "", print: "" },
    fundoRemovido: { carro: false, peca: false, print: false },
    aiBusy: { carro: false, peca: false, print: false },
    metaText: { carro: DEFAULT_META, peca: DEFAULT_META, print: DEFAULT_META },
    objectUrls: { carro: null, peca: null, print: null },
    uploadSeq: { carro: 0, peca: 0, print: 0 },
    uploadAbort: { carro: null, peca: null, print: null },
    cropMeta: { carro: null, peca: null, print: null },
    crops: { carro: null, peca: null, print: null },
    drag: null,
    previewTimer: null,
    previewSeq: 0,
    previewAbort: null,
    isSaving: false,
    errorSource: null,
  };

  const usarCarroInput = document.getElementById("usar-carro");
  const usarPecaInput = document.getElementById("usar-peca");
  const usarPrintInput = document.getElementById("usar-print");
  const usarEtiquetaInput = document.getElementById("usar-etiqueta");
  const usarTituloInput = document.getElementById("usar-titulo");
  const usarSubtituloInput = document.getElementById("usar-subtitulo");

  const larguraCarroInput = document.getElementById("largura-carro");
  const escalaPecaInput = document.getElementById("escala-peca");
  const larguraPrintInput = document.getElementById("largura-print");
  const tamTituloInput = document.getElementById("tam-titulo");
  const tamSubInput = document.getElementById("tam-sub");
  const tamEtiquetaInput = document.getElementById("tam-etiqueta");

  const valLarguraCarro = document.getElementById("val-largura-carro");
  const valEscalaPeca = document.getElementById("val-escala-peca");
  const valLarguraPrint = document.getElementById("val-largura-print");
  const valTamTitulo = document.getElementById("val-tam-titulo");
  const valTamSub = document.getElementById("val-tam-sub");
  const valTamEtiqueta = document.getElementById("val-tam-etiqueta");
  const btnRestaurarTamanhos = document.getElementById("btn-restaurar-tamanhos");

  const tituloInput = document.getElementById("titulo");
  const subtituloInput = document.getElementById("subtitulo");
  const subtituloContador = document.getElementById("subtitulo-contador");
  const etiquetaInput = document.getElementById("etiqueta");
  const cropEditors = Object.fromEntries(
    TIPOS_IMAGEM.map((tipo) => [
      tipo,
      {
        section: document.querySelector(`[data-crop-section="${tipo}"]`),
        info: document.querySelector(`[data-crop-info="${tipo}"]`),
        wrap: document.querySelector(`[data-crop-wrap="${tipo}"]`),
        canvas: document.querySelector(`[data-crop-canvas="${tipo}"]`),
        btnCentralizar: document.querySelector(`[data-btn-centralizar="${tipo}"]`),
        fixedRatio: tipo === "print" ? ASPECT_RATIO : null,
        maxH: tipo === "print" ? 360 : 240,
      },
    ])
  );
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

  function showError(msg, source = "preview") {
    state.errorSource = source;
    erroBanner.textContent = msg;
    erroBanner.hidden = false;
  }

  function clearError() {
    state.errorSource = null;
    erroBanner.textContent = "";
    erroBanner.hidden = true;
  }

  function clearSaveStatus() {
    statusSalvar.hidden = true;
    statusSalvar.textContent = "";
  }

  function anyElementActive() {
    return (
      usarCarroInput.checked ||
      usarPecaInput.checked ||
      usarPrintInput.checked ||
      usarTituloInput.checked ||
      usarSubtituloInput.checked
    );
  }

  function missingReason() {
    if (!anyElementActive()) {
      return "Ative pelo menos um elemento para gerar o anúncio.";
    }
    if (usarCarroInput.checked && !state.uploaded.carro) {
      return "Envie a foto do carro.";
    }
    if (usarPecaInput.checked && !state.uploaded.peca) {
      return "Envie a foto da peça.";
    }
    if (usarPrintInput.checked && !state.uploaded.print) {
      return "Envie o print de aplicação.";
    }
    if (usarTituloInput.checked && !tituloInput.value.trim()) {
      return "Informe o título.";
    }
    return null;
  }

  function allRequiredReady() {
    return missingReason() === null;
  }

  function updateRangeLabels() {
    valLarguraCarro.textContent = `${larguraCarroInput.value} px`;
    valEscalaPeca.textContent = `${escalaPecaInput.value}%`;
    valLarguraPrint.textContent = `${larguraPrintInput.value} px`;
    valTamTitulo.textContent = `${tamTituloInput.value} px`;
    valTamSub.textContent = `${tamSubInput.value} px`;
    valTamEtiqueta.textContent = `${tamEtiquetaInput.value} px`;
  }

  function syncBlockStates() {
    const checkboxesPorTipo = {
      carro: usarCarroInput.checked,
      peca: usarPecaInput.checked,
      print: usarPrintInput.checked,
    };
    const mapa = [
      ["carro", checkboxesPorTipo.carro],
      ["peca", checkboxesPorTipo.peca],
      ["print", checkboxesPorTipo.print],
      ["etiqueta", usarEtiquetaInput.checked],
      ["titulo", usarTituloInput.checked],
      ["subtitulo", usarSubtituloInput.checked],
    ];
    for (const [bloco, ativo] of mapa) {
      const el = document.querySelector(`[data-bloco="${bloco}"]`);
      if (el) {
        el.classList.toggle("is-disabled", !ativo);
      }
    }
    for (const tipo of TIPOS_IMAGEM) {
      const ed = cropEditors[tipo];
      if (!ed || !ed.section) {
        continue;
      }
      const mostrarCrop = Boolean(
        checkboxesPorTipo[tipo] && state.uploaded[tipo] && state.cropMeta[tipo]
      );
      ed.section.hidden = !mostrarCrop;
      if (mostrarCrop) {
        layoutCropCanvas(tipo);
      }
    }
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

  function rectFromRecorte(tipo, recorte, serverW, serverH) {
    const ed = cropEditors[tipo];
    const [l, t, r, b] = recorte;
    if (ed && ed.fixedRatio) {
      const maxW = Math.min(serverW, serverH * ed.fixedRatio);
      const w = clamp(Math.max(1, r - l), Math.min(MIN_CROP_WIDTH, maxW), maxW);
      const h = w / ed.fixedRatio;
      const x = clamp(l, 0, Math.max(0, serverW - w));
      const y = clamp(t, 0, Math.max(0, serverH - h));
      return { x, y, w, h };
    }
    const minW = Math.min(MIN_CROP_SIZE, serverW);
    const minH = Math.min(MIN_CROP_SIZE, serverH);
    const w = clamp(Math.max(1, r - l), minW, serverW);
    const h = clamp(Math.max(1, b - t), minH, serverH);
    const x = clamp(l, 0, Math.max(0, serverW - w));
    const y = clamp(t, 0, Math.max(0, serverH - h));
    return { x, y, w, h };
  }

  function recorteArray(tipo) {
    const meta = state.cropMeta[tipo];
    const crop = state.crops[tipo];
    if (!crop || !meta) {
      return null;
    }
    const { width, height } = meta;
    const l = clamp(Math.round(crop.x), 0, Math.max(0, width - 1));
    const t = clamp(Math.round(crop.y), 0, Math.max(0, height - 1));
    const r = Math.max(l + 1, clamp(Math.round(crop.x + crop.w), 1, width));
    const b = Math.max(t + 1, clamp(Math.round(crop.y + crop.h), 1, height));
    return [l, t, r, b];
  }

  function aplicarRecorteImagem(tipo, data, img) {
    if (!img || !data.recorte) {
      return;
    }
    if (state.drag && state.drag.tipo === tipo) {
      state.drag = null;
    }
    state.cropMeta[tipo] = {
      width: data.largura,
      height: data.altura,
      area: data.area || null,
      initialRecorte: data.recorte,
      image: img,
    };
    state.crops[tipo] = rectFromRecorte(tipo, data.recorte, data.largura, data.altura);
  }

  function buildPayload() {
    return {
      titulo: tituloInput.value,
      subtitulo: getSubtituloLinhas(),
      etiqueta: etiquetaInput.value,
      recorte_carro: usarCarroInput.checked ? recorteArray("carro") : null,
      recorte_peca: usarPecaInput.checked ? recorteArray("peca") : null,
      recorte_print: usarPrintInput.checked ? recorteArray("print") : null,
      usar_carro: usarCarroInput.checked,
      usar_peca: usarPecaInput.checked,
      usar_print: usarPrintInput.checked,
      usar_etiqueta: usarEtiquetaInput.checked,
      usar_titulo: usarTituloInput.checked,
      usar_subtitulo: usarSubtituloInput.checked,
      largura_carro: Number(larguraCarroInput.value),
      escala_peca: Number(escalaPecaInput.value) / 100,
      largura_print: Number(larguraPrintInput.value),
      tam_titulo: Number(tamTituloInput.value),
      tam_sub: Number(tamSubInput.value),
      tam_etiqueta: Number(tamEtiquetaInput.value),
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

  function schedulePreview(imediato = false) {
    cancelPendingPreview();
    clearSaveStatus();
    if (state.errorSource !== "upload") {
      clearError();
    }
    if (!allRequiredReady()) {
      showPreviewPlaceholder();
      return;
    }
    if (imediato) {
      runPreview();
      return;
    }
    state.previewTimer = setTimeout(runPreview, DEBOUNCE_MS);
  }

  async function runPreview() {
    state.previewTimer = null;
    if (!allRequiredReady()) {
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

  function layoutCropCanvas(tipo) {
    const ed = cropEditors[tipo];
    const meta = state.cropMeta[tipo];
    if (!ed || !ed.section || !ed.canvas || !ed.wrap || !meta || ed.section.hidden) {
      return;
    }
    const availableW = Math.max(220, (ed.wrap.clientWidth || 420) - 12);
    const scale = Math.min(availableW / meta.width, ed.maxH / meta.height);
    const displayW = Math.max(1, Math.round(meta.width * scale));
    const displayH = Math.max(1, Math.round(meta.height * scale));
    const dpr = window.devicePixelRatio || 1;

    ed.canvas.width = Math.round(displayW * dpr);
    ed.canvas.height = Math.round(displayH * dpr);
    ed.canvas.style.width = `${displayW}px`;
    ed.canvas.style.height = `${displayH}px`;
    renderCropCanvas(tipo);
  }

  function renderCropCanvas(tipo) {
    const ed = cropEditors[tipo];
    const meta = state.cropMeta[tipo];
    const crop = state.crops[tipo];
    if (!ed || !ed.canvas || !meta || !crop) {
      return;
    }
    const canvas = ed.canvas;
    const displayW = parseFloat(canvas.style.width) || canvas.clientWidth;
    const displayH = parseFloat(canvas.style.height) || canvas.clientHeight;
    if (!displayW || !displayH) {
      return;
    }

    const dpr = window.devicePixelRatio || 1;
    const ctx = canvas.getContext("2d");
    if (!ctx) {
      return;
    }

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = "#f1f5f9";
    ctx.fillRect(0, 0, displayW, displayH);
    ctx.drawImage(meta.image, 0, 0, displayW, displayH);

    const scaleX = displayW / meta.width;
    const scaleY = displayH / meta.height;
    const rx = crop.x * scaleX;
    const ry = crop.y * scaleY;
    const rw = crop.w * scaleX;
    const rh = crop.h * scaleY;

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

    if (ed.info) {
      const prefixo = ed.fixedRatio ? "Proporção 350:255" : "Recorte livre";
      ed.info.textContent =
        `${prefixo} • ${Math.round(crop.w)} × ${Math.round(crop.h)} px` +
        ` (x=${Math.round(crop.x)}, y=${Math.round(crop.y)})`;
    }
  }

  function getPointerInfo(tipo, e) {
    const ed = cropEditors[tipo];
    const meta = state.cropMeta[tipo];
    const crop = state.crops[tipo];
    const rect = ed.canvas.getBoundingClientRect();
    if (!rect.width || !rect.height || !meta || !crop) {
      return { sx: 0, sy: 0, inHandle: false, inBox: false };
    }
    const dx = e.clientX - rect.left;
    const dy = e.clientY - rect.top;
    const { width: serverW, height: serverH } = meta;
    const sx = dx * (serverW / rect.width);
    const sy = dy * (serverH / rect.height);

    const rx = crop.x * (rect.width / serverW);
    const ry = crop.y * (rect.height / serverH);
    const rw = crop.w * (rect.width / serverW);
    const rh = crop.h * (rect.height / serverH);

    const hxMin = Math.max(rx + rw * 0.5, rx + rw - 20);
    const hyMin = Math.max(ry + rh * 0.5, ry + rh - 20);
    const inHandle = dx >= hxMin && dx <= rx + rw + 10 && dy >= hyMin && dy <= ry + rh + 10;
    const inBox = dx >= rx && dx <= rx + rw && dy >= ry && dy <= ry + rh;

    return { sx, sy, inHandle, inBox };
  }

  function bindCropEditor(tipo) {
    const ed = cropEditors[tipo];
    if (!ed || !ed.canvas) {
      return;
    }
    const canvas = ed.canvas;

    canvas.addEventListener("pointerdown", (e) => {
      if (!state.crops[tipo] || !state.cropMeta[tipo]) {
        return;
      }
      if (e.pointerType === "mouse" && e.button !== 0) {
        return;
      }
      const { sx, sy, inHandle, inBox } = getPointerInfo(tipo, e);
      if (!inHandle && !inBox) {
        return;
      }

      e.preventDefault();
      canvas.setPointerCapture(e.pointerId);
      const mode = inHandle ? "resize" : "move";
      state.drag = {
        tipo,
        mode,
        pointerId: e.pointerId,
        startX: sx,
        startY: sy,
        startCrop: { ...state.crops[tipo] },
      };
      canvas.style.cursor = mode === "resize" ? "nwse-resize" : "grabbing";
    });

    canvas.addEventListener("pointermove", (e) => {
      const meta = state.cropMeta[tipo];
      const crop = state.crops[tipo];
      if (!crop || !meta) {
        return;
      }
      const { sx, sy, inHandle, inBox } = getPointerInfo(tipo, e);

      if (!state.drag || state.drag.tipo !== tipo) {
        canvas.style.cursor = inHandle ? "nwse-resize" : inBox ? "grab" : "default";
        return;
      }
      if (e.pointerId !== state.drag.pointerId) {
        return;
      }

      const { width: serverW, height: serverH } = meta;
      const { startCrop, startX, startY, mode } = state.drag;

      if (mode === "move") {
        const maxX = Math.max(0, serverW - startCrop.w);
        const maxY = Math.max(0, serverH - startCrop.h);
        crop.x = clamp(startCrop.x + (sx - startX), 0, maxX);
        crop.y = clamp(startCrop.y + (sy - startY), 0, maxY);
      } else {
        const dx = sx - startX;
        const dy = sy - startY;
        if (ed.fixedRatio) {
          const wFromX = startCrop.w + dx;
          const wFromY = (startCrop.h + dy) * ed.fixedRatio;
          const candidateW = Math.abs(dx) / 350 >= Math.abs(dy) / 255 ? wFromX : wFromY;
          const maxW = Math.min(serverW - startCrop.x, (serverH - startCrop.y) * ed.fixedRatio);
          const minW = Math.min(MIN_CROP_WIDTH, maxW);
          const nextW = clamp(candidateW, minW, maxW);
          crop.w = nextW;
          crop.h = nextW / ed.fixedRatio;
        } else {
          const maxW = Math.max(1, serverW - startCrop.x);
          const maxH = Math.max(1, serverH - startCrop.y);
          const minW = Math.min(MIN_CROP_SIZE, maxW);
          const minH = Math.min(MIN_CROP_SIZE, maxH);
          crop.w = clamp(startCrop.w + dx, minW, maxW);
          crop.h = clamp(startCrop.h + dy, minH, maxH);
        }
      }

      renderCropCanvas(tipo);
      schedulePreview();
    });

    function endCropDrag(e) {
      if (!state.drag || state.drag.tipo !== tipo || e.pointerId !== state.drag.pointerId) {
        return;
      }
      if (canvas.hasPointerCapture && canvas.hasPointerCapture(e.pointerId)) {
        canvas.releasePointerCapture(e.pointerId);
      }
      state.drag = null;
      if (state.crops[tipo] && state.cropMeta[tipo]) {
        const { inHandle, inBox } = getPointerInfo(tipo, e);
        canvas.style.cursor = inHandle ? "nwse-resize" : inBox ? "grab" : "default";
      } else {
        canvas.style.cursor = "default";
      }
    }

    canvas.addEventListener("pointerup", endCropDrag);
    canvas.addEventListener("pointercancel", endCropDrag);

    if (ed.btnCentralizar) {
      ed.btnCentralizar.addEventListener("click", () => {
        const meta = state.cropMeta[tipo];
        if (!meta) {
          return;
        }
        state.crops[tipo] = rectFromRecorte(
          tipo,
          meta.initialRecorte,
          meta.width,
          meta.height
        );
        renderCropCanvas(tipo);
        schedulePreview();
      });
    }
  }

  for (const tipo of TIPOS_IMAGEM) {
    bindCropEditor(tipo);
  }

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
    clearSaveStatus();

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
        showError(data.erro || "Não foi possível enviar a imagem.", "upload");
        return;
      }

      const nextUrl = URL.createObjectURL(file);
      let loadedImg = null;
      try {
        loadedImg = await loadHtmlImage(nextUrl);
      } catch {
        URL.revokeObjectURL(nextUrl);
        if (seq === state.uploadSeq[tipo]) {
          metaEl.textContent = state.metaText[tipo];
          showError(
            "Não foi possível exibir esta imagem no navegador (use PNG ou JPEG RGB).",
            "upload"
          );
        }
        return;
      }
      if (seq !== state.uploadSeq[tipo]) {
        URL.revokeObjectURL(nextUrl);
        return;
      }

      if (state.objectUrls[tipo]) {
        URL.revokeObjectURL(state.objectUrls[tipo]);
      }
      state.objectUrls[tipo] = nextUrl;
      state.uploaded[tipo] = true;
      state.fileName[tipo] = file.name;
      state.fundoRemovido[tipo] = false;
      state.aiBusy[tipo] = false;

      thumbImg.src = nextUrl;
      thumbWrap.hidden = false;
      const resumo = `${file.name} (${data.largura}×${data.altura})`;
      state.metaText[tipo] = resumo;
      metaEl.textContent = resumo;
      metaEl.title = resumo;
      dropzone.classList.add("is-uploaded");
      updateAiBgButton(tipo);
      clearError();

      aplicarRecorteImagem(tipo, data, loadedImg);
      syncBlockStates();

      schedulePreview();
    } catch (err) {
      if (err && err.name === "AbortError") {
        return;
      }
      if (seq === state.uploadSeq[tipo]) {
        metaEl.textContent = state.metaText[tipo];
        showError("Erro de conexão ao enviar a imagem.", "upload");
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

  function validateBeforeSave() {
    return missingReason();
  }

  async function salvarPng() {
    if (state.isSaving) {
      return;
    }
    clearSaveStatus();
    const validationError = validateBeforeSave();
    if (validationError) {
      showError(validationError, "save");
      return;
    }
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
        showError(data.erro || "Erro ao salvar o PNG.", "save");
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
      showError("Erro de conexão ao salvar o PNG.", "save");
    } finally {
      state.isSaving = false;
      btnBaixar.disabled = false;
      btnBaixar.textContent = "Baixar PNG";
    }
  }

  tituloInput.addEventListener("input", () => schedulePreview());
  subtituloInput.addEventListener("input", () => {
    updateSubtitleCounter();
    schedulePreview();
  });
  etiquetaInput.addEventListener("input", () => schedulePreview());

  for (const checkbox of [
    usarCarroInput,
    usarPecaInput,
    usarPrintInput,
    usarEtiquetaInput,
    usarTituloInput,
    usarSubtituloInput,
  ]) {
    checkbox.addEventListener("change", () => {
      syncBlockStates();
      schedulePreview(true);
    });
  }

  for (const slider of [
    larguraCarroInput,
    escalaPecaInput,
    larguraPrintInput,
    tamTituloInput,
    tamSubInput,
    tamEtiquetaInput,
  ]) {
    slider.addEventListener("input", () => {
      updateRangeLabels();
      schedulePreview();
    });
  }

  btnRestaurarTamanhos.addEventListener("click", () => {
    larguraCarroInput.value = String(DEFAULTS.larguraCarro);
    escalaPecaInput.value = String(DEFAULTS.escalaPecaPct);
    larguraPrintInput.value = String(DEFAULTS.larguraPrint);
    tamTituloInput.value = String(DEFAULTS.tamTitulo);
    tamSubInput.value = String(DEFAULTS.tamSub);
    tamEtiquetaInput.value = String(DEFAULTS.tamEtiqueta);
    updateRangeLabels();
    schedulePreview(true);
  });

  function atualizarBadgeIa(configurada) {
    if (!iaStatusEl) return;
    iaStatusEl.textContent = configurada ? "IA: Pronta" : "IA: Sem chave";
    iaStatusEl.classList.toggle("is-ready", configurada);
    iaStatusEl.classList.toggle("is-missing", !configurada);
  }

  async function carregarStatusIa() {
    if (!iaStatusEl) return;
    try {
      const res = await fetch("/api/config/ia");
      if (!res.ok) throw new Error("status");
      const data = await res.json();
      atualizarBadgeIa(Boolean(data.configurada));
    } catch {
      iaStatusEl.textContent = "IA: Indisponível";
      iaStatusEl.classList.remove("is-ready", "is-missing");
    }
  }

  async function salvarChaveIa() {
    if (!iaApiKeyInput || !btnSalvarChave) return;
    const chave = (iaApiKeyInput.value || "").trim();
    if (!chave) {
      showError("Informe a chave da Poof API.", "ia");
      iaApiKeyInput.focus();
      return;
    }

    btnSalvarChave.disabled = true;
    btnSalvarChave.textContent = "Salvando...";
    try {
      const res = await fetch("/api/config/ia", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: chave }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        showError(data.erro || "Não foi possível salvar a chave API.", "ia");
        return;
      }
      clearError();
      iaApiKeyInput.value = "";
      atualizarBadgeIa(Boolean(data.configurada));
      if (iaConfigPanel) {
        iaConfigPanel.hidden = true;
      }
    } catch {
      showError("Erro de conexão ao salvar a chave API.", "ia");
    } finally {
      btnSalvarChave.disabled = false;
      btnSalvarChave.textContent = "Salvar chave";
    }
  }

  function updateAiBgButton(tipo) {
    const row = document.querySelector(`.ai-bg-row[data-ai-row="${tipo}"]`);
    const btn = document.querySelector(`.btn-remover-fundo[data-tipo="${tipo}"]`);
    if (row) {
      row.hidden = !state.uploaded[tipo];
    }
    if (btn) {
      btn.disabled = state.aiBusy[tipo] || !state.uploaded[tipo];
      const ativo = Boolean(state.fundoRemovido[tipo]);
      btn.textContent = ativo ? "Restaurar original" : "Remover fundo (IA)";
      btn.classList.toggle("is-active", ativo);
    }
  }

  async function toggleRemoverFundo(tipo) {
    if (state.aiBusy[tipo] || !state.uploaded[tipo]) {
      return;
    }
    const usar = !state.fundoRemovido[tipo];
    const reqSeq = state.uploadSeq[tipo];
    const btn = document.querySelector(`.btn-remover-fundo[data-tipo="${tipo}"]`);
    const dropzone = document.querySelector(`.dropzone[data-tipo="${tipo}"]`);
    const thumbImg = dropzone ? dropzone.querySelector(".dropzone-thumb") : null;
    const thumbWrap = dropzone ? dropzone.querySelector(".dropzone-thumb-wrap") : null;
    const metaEl = dropzone ? dropzone.querySelector(".dropzone-meta") : null;

    state.aiBusy[tipo] = true;
    if (btn) {
      btn.disabled = true;
      btn.textContent = usar ? "Removendo fundo..." : "Restaurando...";
    }

    const controller = new AbortController();
    const abortTimer = setTimeout(() => controller.abort(), 80000);

    try {
      const res = await fetch(`/api/imagem/${tipo}/remover-fundo`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ usar }),
        signal: controller.signal,
      });
      const data = await res.json().catch(() => ({}));
      if (state.uploadSeq[tipo] !== reqSeq) {
        return;
      }
      if (!res.ok) {
        const msg = data.erro || "Erro ao processar fundo com IA.";
        if (
          (res.status === 400 && /chave|api/i.test(msg)) ||
          /inválida|sem permissão/i.test(msg)
        ) {
          if (res.status === 400) {
            atualizarBadgeIa(false);
          }
          if (iaConfigPanel) {
            iaConfigPanel.hidden = false;
          }
        }
        showError(msg, "ai");
        return;
      }

      const dataUrl = `data:image/png;base64,${data.png}`;
      const loadedImg = await loadHtmlImage(dataUrl);
      if (state.uploadSeq[tipo] !== reqSeq) {
        return;
      }

      if (state.objectUrls[tipo]) {
        URL.revokeObjectURL(state.objectUrls[tipo]);
        state.objectUrls[tipo] = null;
      }
      if (thumbImg) {
        thumbImg.src = dataUrl;
      }
      if (thumbWrap) {
        thumbWrap.hidden = false;
      }

      state.fundoRemovido[tipo] = Boolean(data.fundo_removido);
      const nomeBase = state.fileName[tipo] || tipo;
      const sufixo = state.fundoRemovido[tipo] ? " • sem fundo" : "";
      const resumo = `${nomeBase} (${data.largura}×${data.altura}${sufixo})`;
      state.metaText[tipo] = resumo;
      if (metaEl) {
        metaEl.textContent = resumo;
        metaEl.title = resumo;
      }

      aplicarRecorteImagem(tipo, data, loadedImg);
      syncBlockStates();

      clearError();
      clearSaveStatus();
      schedulePreview(true);
    } catch (err) {
      if (state.uploadSeq[tipo] === reqSeq) {
        if (err && err.name === "AbortError") {
          showError("Tempo limite excedido ao aguardar resposta da IA.", "ai");
        } else {
          showError("Erro de conexão ao remover fundo com IA.", "ai");
        }
      }
    } finally {
      clearTimeout(abortTimer);
      if (state.uploadSeq[tipo] === reqSeq) {
        state.aiBusy[tipo] = false;
        updateAiBgButton(tipo);
      }
    }
  }

  btnBaixar.addEventListener("click", salvarPng);

  if (btnIaConfig && iaConfigPanel) {
    btnIaConfig.addEventListener("click", () => {
      iaConfigPanel.hidden = !iaConfigPanel.hidden;
      if (!iaConfigPanel.hidden && iaApiKeyInput) {
        iaApiKeyInput.focus();
      }
    });
  }

  if (btnSalvarChave) {
    btnSalvarChave.addEventListener("click", salvarChaveIa);
  }

  if (iaApiKeyInput) {
    iaApiKeyInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        salvarChaveIa();
      }
    });
  }

  for (const btn of document.querySelectorAll(".btn-remover-fundo")) {
    btn.addEventListener("click", () => {
      const tipo = btn.dataset.tipo;
      if (tipo) {
        toggleRemoverFundo(tipo);
      }
    });
  }

  if (typeof ResizeObserver !== "undefined") {
    for (const tipo of TIPOS_IMAGEM) {
      const wrap = cropEditors[tipo] && cropEditors[tipo].wrap;
      if (wrap) {
        new ResizeObserver(() => layoutCropCanvas(tipo)).observe(wrap);
      }
    }
  } else {
    window.addEventListener("resize", () => {
      for (const tipo of TIPOS_IMAGEM) {
        layoutCropCanvas(tipo);
      }
    });
  }

  updateSubtitleCounter();
  updateRangeLabels();
  syncBlockStates();
  carregarStatusIa();
})();
