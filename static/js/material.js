document.addEventListener("DOMContentLoaded", () => {
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";

  function authorizedFetch(url, options = {}) {
    const headers = new Headers(options.headers || {});
    headers.set("X-CSRF-Token", csrfToken);
    return fetch(url, { ...options, headers });
  }

  const list = document.getElementById("materialList");
  const search = document.getElementById("materialSearch");
  const typeFilter = document.getElementById("materialTypeFilter");
  const cards = Array.from(list.querySelectorAll(".material-card"));

  cards.forEach((card) => {
    const header = card.querySelector(".material-card__header");
    header.addEventListener("click", () => {
      const wasOpen = card.classList.contains("is-open");
      cards.forEach((c) => c.classList.remove("is-open"));
      if (!wasOpen) {
        card.classList.add("is-open");
      }
    });
  });

  // Vista previa de "oraciones con imágenes": tarjetas horizontales, una por
  // oración, con flechas para deslizar (ver .material-card__slider* en
  // dashboard.css). Cada material de ese tipo tiene su propio slider.
  function wireImageSentenceSliders() {
    document.querySelectorAll("[data-slider]").forEach((slider) => {
      const track = slider.querySelector("[data-slider-track]");
      const prevBtn = slider.querySelector("[data-slider-prev]");
      const nextBtn = slider.querySelector("[data-slider-next]");
      if (!track || !prevBtn || !nextBtn) return;

      function slideBy(direction) {
        const slide = track.querySelector(".material-card__slide");
        const step = slide ? slide.getBoundingClientRect().width + 10 : track.clientWidth;
        track.scrollBy({ left: direction * step, behavior: "smooth" });
      }

      function updateNav() {
        const maxScroll = track.scrollWidth - track.clientWidth;
        prevBtn.disabled = track.scrollLeft <= 1;
        nextBtn.disabled = maxScroll <= 1 || track.scrollLeft >= maxScroll - 1;
      }

      prevBtn.addEventListener("click", () => slideBy(-1));
      nextBtn.addEventListener("click", () => slideBy(1));
      track.addEventListener("scroll", updateNav);
      // El track empieza oculto (la tarjeta de material recién se despliega
      // al tocarla) y clientWidth/scrollWidth valen 0 mientras tanto -sin
      // esto, "Siguiente" quedaría deshabilitado para siempre. ResizeObserver
      // recalcula en cuanto el contenedor pasa a tener tamaño real.
      new ResizeObserver(updateNav).observe(track);
    });
  }

  wireImageSentenceSliders();

  function applyFilters() {
    const query = search.value.trim().toLowerCase();
    const tipo = typeFilter.value;

    cards.forEach((card) => {
      const matchesType = !tipo || card.dataset.tipo === tipo;
      const matchesQuery = !query || card.dataset.title.includes(query);
      card.classList.toggle("is-hidden", !(matchesType && matchesQuery));
    });
  }

  search.addEventListener("input", applyFilters);
  typeFilter.addEventListener("change", applyFilters);

  // Delete flow: click "Eliminar" on a card -> confirm -> DELETE -> reload
  const deleteOverlay = document.getElementById("deleteOverlay");
  const deleteMaterialName = document.getElementById("deleteMaterialName");
  const deleteCancelBtn = document.getElementById("deleteCancelBtn");
  const deleteConfirmBtn = document.getElementById("deleteConfirmBtn");
  let pendingDeleteId = null;

  cards.forEach((card) => {
    const deleteBtn = card.querySelector(".material-card__delete");
    if (!deleteBtn) return;
    deleteBtn.addEventListener("click", (event) => {
      event.stopPropagation();
      pendingDeleteId = deleteBtn.dataset.materialId;
      deleteMaterialName.textContent = deleteBtn.dataset.materialName || "este material";
      deleteOverlay.classList.add("is-open");
    });
  });

  function closeDeleteOverlay() {
    deleteOverlay.classList.remove("is-open");
    pendingDeleteId = null;
  }

  deleteCancelBtn.addEventListener("click", closeDeleteOverlay);

  deleteConfirmBtn.addEventListener("click", async () => {
    if (!pendingDeleteId) return;

    const originalLabel = deleteConfirmBtn.textContent;
    deleteConfirmBtn.disabled = true;
    deleteConfirmBtn.textContent = "Eliminando...";

    try {
      const response = await authorizedFetch(`/api/material/${pendingDeleteId}`, {
        method: "DELETE",
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.error || "No se pudo eliminar el material.");
      }
      window.location.reload();
    } catch (error) {
      alert(error.message || "No se pudo eliminar el material.");
      deleteConfirmBtn.disabled = false;
      deleteConfirmBtn.textContent = originalLabel;
      closeDeleteOverlay();
    }
  });

  // Upload flow: dropzone -> loading -> results
  const uploadOpenBtn = document.getElementById("uploadOpenBtn");
  const uploadOverlay = document.getElementById("uploadOverlay");
  const uploadCancelBtn = document.getElementById("uploadCancelBtn");
  const uploadStartBtn = document.getElementById("uploadStartBtn");
  const uploadTitleInput = document.getElementById("uploadTitleInput");
  const uploadPeriodoYearSelect = document.getElementById("uploadPeriodoYearSelect");
  const uploadPeriodoSelect = document.getElementById("uploadPeriodoSelect");
  const uploadTemaSelect = document.getElementById("uploadTemaSelect");
  const uploadFileInput = document.getElementById("uploadFileInput");
  const dropzone = document.getElementById("dropzone");
  const dropzoneText = document.getElementById("dropzoneText");
  const dropzoneHint = document.getElementById("dropzoneHint");
  const uploadManualOption = document.getElementById("uploadManualOption");
  const manualEditorOpenBtn = document.getElementById("manualEditorOpenBtn");
  const loadingOverlay = document.getElementById("loadingOverlay");
  const loadingSpinner = document.getElementById("loadingSpinner");
  const loadingText = document.getElementById("loadingText");
  const loadingCloseBtn = document.getElementById("loadingCloseBtn");
  const resultOverlay = document.getElementById("resultOverlay");
  const resultModalTitle = document.getElementById("resultModalTitle");
  const resultDoneBtn = document.getElementById("resultDoneBtn");
  const resultCancelBtn = document.getElementById("resultCancelBtn");
  const resultSubtitle = document.getElementById("resultSubtitle");
  const resultTranscribedText = document.getElementById("resultTranscribedText");
  const resultSummaryText = document.getElementById("resultSummaryText");
  const storyOverlay = document.getElementById("storyOverlay");
  const storyOpenBtn = document.getElementById("storyOpenBtn");
  const storyCancelBtn = document.getElementById("storyCancelBtn");
  const storyForm = document.getElementById("storyForm");
  const storyGenerateBtn = document.getElementById("storyGenerateBtn");
  const storyModalTitle = document.getElementById("storyModalTitle");
  const storyModalDescription = document.getElementById("storyModalDescription");
  const storyTypeCuentoBtn = document.getElementById("storyTypeCuentoBtn");
  const storyTypeOracionBtn = document.getElementById("storyTypeOracionBtn");
  const storyTypeOracionImagenBtn = document.getElementById("storyTypeOracionImagenBtn");
  const storyTypeBitsBtn = document.getElementById("storyTypeBitsBtn");
  const storyCuentoFields = document.getElementById("storyCuentoFields");
  const storySentenceFields = document.getElementById("storySentenceFields");
  const storyImageFields = document.getElementById("storyImageFields");
  const storyBitsFields = document.getElementById("storyBitsFields");
  const bitsSyllablesInput = document.getElementById("bitsSyllables");
  const bitsSyllableCountInput = document.getElementById("bitsSyllableCount");
  const bitsGradeInput = document.getElementById("bitsGrade");
  const bitsCountInput = document.getElementById("bitsCount");
  const bitsDetailsInput = document.getElementById("bitsDetails");
  const uploadTypeCuentoBtn = document.getElementById("uploadTypeCuentoBtn");
  const uploadTypeOracionBtn = document.getElementById("uploadTypeOracionBtn");
  const uploadTypeOracionImagenBtn = document.getElementById("uploadTypeOracionImagenBtn");
  const uploadTypeBitsBtn = document.getElementById("uploadTypeBitsBtn");
  const resultTranscribedLabel = document.getElementById("resultTranscribedLabel");
  const resultTranscribedBlock = document.getElementById("resultTranscribedBlock");
  const resultSummaryBlock = document.getElementById("resultSummaryBlock");
  const resultSentencesBlock = document.getElementById("resultSentencesBlock");
  const resultSentencesLabel = document.getElementById("resultSentencesLabel");
  const resultSentencesNote = document.getElementById("resultSentencesNote");
  const resultSentencesList = document.getElementById("resultSentencesList");
  const addSentenceBtn = document.getElementById("addSentenceBtn");
  const generateMoreSentencesBtn = document.getElementById("generateMoreSentencesBtn");
  const resultAudioColumn = document.getElementById("resultAudioColumn");
  const resultQuestionsColumn = document.getElementById("resultQuestionsColumn");
  const imageDesignOverlay = document.getElementById("imageDesignOverlay");
  const imageDesignTitle = document.getElementById("imageDesignTitle");
  const imageDesignPrevBtn = document.getElementById("imageDesignPrevBtn");
  const imageDesignNextBtn = document.getElementById("imageDesignNextBtn");
  const imageDesignCounter = document.getElementById("imageDesignCounter");
  const imageDesignStage = document.getElementById("imageDesignStage");
  const imageDesignMixedLine = document.getElementById("imageDesignMixedLine");
  const imageDesignNounControls = document.getElementById("imageDesignNounControls");
  const imageDesignRemoveBtn = document.getElementById("imageDesignRemoveBtn");
  const imageDesignEmpty = document.getElementById("imageDesignEmpty");
  const imageDesignBackBtn = document.getElementById("imageDesignBackBtn");
  const imageDesignDiscardBtn = document.getElementById("imageDesignDiscardBtn");
  const imageDesignSaveBtn = document.getElementById("imageDesignSaveBtn");
  const bitsDesignOverlay = document.getElementById("bitsDesignOverlay");
  const bitsDesignTitle = document.getElementById("bitsDesignTitle");
  const bitsDesignPrevBtn = document.getElementById("bitsDesignPrevBtn");
  const bitsDesignNextBtn = document.getElementById("bitsDesignNextBtn");
  const bitsDesignCounter = document.getElementById("bitsDesignCounter");
  const bitsDesignStage = document.getElementById("bitsDesignStage");
  const bitsDesignImage = document.getElementById("bitsDesignImage");
  const bitsDesignNounControls = document.getElementById("bitsDesignNounControls");
  const bitsDesignRemoveBtn = document.getElementById("bitsDesignRemoveBtn");
  const bitsDesignEmpty = document.getElementById("bitsDesignEmpty");
  const bitsDesignBackBtn = document.getElementById("bitsDesignBackBtn");
  const bitsDesignDiscardBtn = document.getElementById("bitsDesignDiscardBtn");
  const bitsDesignSaveBtn = document.getElementById("bitsDesignSaveBtn");
  const classifyOverlay = document.getElementById("classifyOverlay");
  const classifyMaterialTitle = document.getElementById("classifyMaterialTitle");
  const classifyBackBtn = document.getElementById("classifyBackBtn");
  const classifySaveBtn = document.getElementById("classifySaveBtn");

  let selectedFile = null;
  let currentStoryType = "cuento";
  // Tema/nivel del último borrador de oraciones por IA; lo reutiliza el botón
  // "Generar 5 con IA" dentro de la revisión. Vacío si las oraciones vienen de
  // un documento subido (ahí la IA infiere el tema de las oraciones actuales).
  let lastSentenceContext = { topic: "", grade_level: "" };
  let currentUploadType = "cuento";
  let currentResultType = "cuento";
  // "Modo editor": la docente escribe las oraciones a mano, sin documento ni
  // IA. `manualEntryMode` es válido para "oracion" y "oracion_imagen";
  // `manualImageEntryMode` además activa, solo para esta última, las 2
  // imágenes por oración que sube ella misma (ver appendImageSentenceItem),
  // que se envían junto con el resto al guardar (ver saveManualImageSentenceMaterial).
  let manualEntryMode = false;
  let manualImageEntryMode = false;
  // "bits": mismo concepto que manualImageEntryMode pero para una sola
  // imagen por fila (ver appendBitsItem/saveManualBitsMaterial). Independiente
  // de manualImageEntryMode para no cruzar estado entre los dos flujos si
  // la docente cambia de tipo sin cerrar el modal.
  let manualBitsEntryMode = false;
  // Identificador propio de cada fila de "oracion_imagen", para poder
  // relacionar sus 2 imágenes con la oración correcta al guardar (ver
  // getImageSentencesData y saveManualImageSentenceMaterial) incluso si el
  // servidor descarta alguna fila duplicada al normalizar.
  let imageSentenceRowSeq = 0;
  // Mismo propósito que imageSentenceRowSeq, pero para las filas de "bits"
  // (ver getBitsData/saveManualBitsMaterial).
  let bitRowSeq = 0;
  // El contenido (cuento, oraciones, oraciones con imágenes...) ya quedó
  // aprobado y solo falta clasificarlo: guarda qué función ejecutar y a qué
  // modal volver si la docente se arrepiente (ver openClassifyModal, más
  // abajo del todo). Sin esto no hay nada que hacer si tocan "Guardar
  // material" en classifyOverlay.
  let pendingSave = null;
  let currentMaterialTitle = "";
  let audioFullReady = false;
  let audioSummaryReady = false;
  let questionsReady = false;
  let audioFullBlob = null;
  let audioSummaryBlob = null;
  let currentTargetDurationMinutes = null;
  let audioFullDurationSeconds = null;
  let audioSummaryDurationSeconds = null;
  let imageDesignToken = "";
  let designSentences = [];
  let currentDesignIndex = 0;
  let imageDesignBusy = false;
  // Mismo esquema que imageDesignToken/designSentences/currentDesignIndex/
  // imageDesignBusy, pero para el diseño de "bits" (bitsDesignOverlay) -
  // estado separado a propósito, para que descartar un diseño no deje
  // basura en el otro flujo.
  let bitsDesignToken = "";
  let designBits = [];
  let currentBitsDesignIndex = 0;
  let bitsDesignBusy = false;

  const uploadTemaOptions = Array.from(uploadTemaSelect.options).filter((option) => option.value);

  function filterUploadTemas(resetSelection = true) {
    if (resetSelection) {
      uploadTemaSelect.value = "";
    }

    const selectedPeriodo = uploadPeriodoSelect.value;
    uploadTemaOptions.forEach((option) => {
      const isVisible = Boolean(selectedPeriodo) && option.dataset.periodo === selectedPeriodo;
      option.hidden = !isVisible;
      option.disabled = !isVisible;
    });
  }

  filterUploadTemas();
  uploadPeriodoSelect.addEventListener("change", () => {
    filterUploadTemas();
    updateClassifySaveState();
  });
  // period_filter.js restablece Periodo al cambiar Año. Este segundo
  // listener se ejecuta después y mantiene Tema sincronizado con ese reset.
  uploadPeriodoYearSelect.addEventListener("change", () => {
    filterUploadTemas();
    updateClassifySaveState();
  });
  uploadTemaSelect.addEventListener("change", () => {
    updateClassifySaveState();
  });

  const uploadTypeButtons = [uploadTypeCuentoBtn, uploadTypeOracionBtn, uploadTypeOracionImagenBtn, uploadTypeBitsBtn];

  function setUploadType(type) {
    currentUploadType = type;
    uploadTypeButtons.forEach((btn) => {
      const active = btn.dataset.type === type;
      btn.classList.toggle("is-active", active);
      btn.setAttribute("aria-selected", String(active));
    });
    uploadTitleInput.placeholder = type === "cuento"
      ? "Título del cuento"
      : type === "oracion_imagen"
        ? "Título de las oraciones con imágenes"
        : type === "bits"
          ? "Título de los bits"
          : "Título del material";
    dropzoneHint.textContent = type === "oracion_imagen"
      ? "DOC, TXT o PDF con una oración por línea - máx. 50 MB"
      : type === "bits"
        ? "DOC, TXT o PDF con una palabra por línea - máx. 50 MB"
        : "DOC, TXT o PDF · máx. 50 MB";
    // El modo editor (escribir el material a mano, sin documento) no aplica
    // a "cuento".
    uploadManualOption.hidden = type === "cuento";
    manualEditorOpenBtn.textContent = type === "bits"
      ? "✏️ Modo editor: crear los bits a mano"
      : "✏️ Modo editor: escribir las oraciones a mano";
    updateUploadButtonState();
  }

  // Ajusta la pantalla de revisión de contenido extraído por IA según el
  // tipo: las oraciones solo revisan el texto, sin resumen, audios ni
  // preguntas (eso es exclusivo de los cuentos).
  function configureResultModalForType(type) {
    currentResultType = type;
    // El modo editor lo activa explícitamente openManualEditor() DESPUÉS de
    // llamar a esta función; cualquier otro camino (documento, IA) arranca
    // siempre en modo revisión normal.
    manualEntryMode = false;
    manualImageEntryMode = false;
    manualBitsEntryMode = false;
    // El nombre del material también se puede editar aquí mismo (ver el
    // listener "input" de resultModalTitle): se muestra el que ya se
    // escribió al inicio -o el de la IA/el documento- en vez de un rótulo
    // fijo como "Contenido generado".
    resultModalTitle.textContent = currentMaterialTitle;
    resultSentencesNote.hidden = false;
    const isOracion = type === "oracion";
    const isImageSentence = type === "oracion_imagen";
    const isBits = type === "bits";
    const isSentenceType = isOracion || isImageSentence || isBits;
    resultTranscribedLabel.textContent = "Texto completo";
    resultTranscribedBlock.hidden = isSentenceType;
    resultSummaryBlock.hidden = isSentenceType;
    resultSentencesBlock.hidden = !isSentenceType;
    resultAudioColumn.hidden = isSentenceType;
    resultQuestionsColumn.hidden = isSentenceType;
    generateMoreSentencesBtn.hidden = isImageSentence || isBits;
    resultSentencesLabel.textContent = isBits
      ? "Palabras para revisar"
      : isImageSentence
        ? "Oraciones con imágenes para revisar"
        : "Oraciones para revisar";
    resultSentencesNote.textContent = isBits
      ? "Corrige cada palabra; usa ✕ para quitar la que no quieras guardar."
      : isImageSentence
        ? "Corrige cada oración y sus dos sustantivos; usa ✕ para quitar la que no quieras guardar."
        : "Corrige cada oración; usa ✕ para quitar la que no quieras guardar.";
    if (addSentenceBtn) {
      addSentenceBtn.textContent = isBits ? "+ Agregar palabra" : "+ Agregar oración";
    }
    resultDoneBtn.textContent = (isImageSentence || isBits)
      ? "Siguiente: diseñar imágenes"
      : "Continuar";
  }

  function updateUploadButtonState() {
    uploadStartBtn.disabled = !selectedFile;
  }

  function resetUploadForm() {
    resetImageDesignState();
    resetBitsDesignState();
    selectedFile = null;
    uploadTitleInput.value = "";
    filterUploadTemas();
    uploadFileInput.value = "";
    dropzoneText.textContent = "Arrastra el archivo aquí o haz clic para seleccionar";
    setUploadType("cuento");
  }

  function openUpload() {
    resetUploadForm();
    uploadOverlay.classList.add("is-open");
  }

  function closeUpload() {
    uploadOverlay.classList.remove("is-open");
  }

  // "Modo editor": salta el documento y la IA -la docente escribe las
  // oraciones ella misma. Reutiliza la misma pantalla de revisión que ya
  // usan la extracción y la generación con IA (mismo botón "+ Agregar
  // oración", mismo guardado para "oracion"); para "oracion_imagen" activa
  // además los cuadros de subir imagen de appendImageSentenceItem y guarda
  // directo con ellas, sin pasar por el diseño con IA (ver
  // saveManualImageSentenceMaterial).
  function openManualEditor(type) {
    // Si no escribió un nombre en el modal de arriba, arranca con uno
    // genérico -el título ahora también se edita aquí mismo (ver
    // resultModalTitle), así que no hace falta que quede vacío.
    currentMaterialTitle = uploadTitleInput.value.trim() || "Nuevo material";
    currentTargetDurationMinutes = null;
    configureResultModalForType(type);
    resetResultState();
    manualEntryMode = true;
    resultSentencesNote.hidden = true;

    if (type === "oracion_imagen") {
      manualImageEntryMode = true;
      renderImageSentenceRows([]);
      appendImageSentenceItem({}, { focus: true });
      resultSubtitle.textContent = "Modo editor - escribe cada oración, sus dos palabras y sube tú misma las imágenes que las reemplazarán";
      resultDoneBtn.textContent = "Continuar";
    } else if (type === "bits") {
      manualBitsEntryMode = true;
      renderBitsRows([]);
      appendBitsItem({}, { focus: true });
      resultSubtitle.textContent = "Modo editor - escribe cada palabra y sube tú misma la imagen que la representará";
      resultDoneBtn.textContent = "Continuar";
    } else {
      lastSentenceContext = { topic: currentMaterialTitle, grade_level: "" };
      renderSentences([]);
      appendSentenceItem("", { focus: true });
      resultSubtitle.textContent = "Modo editor · escribe cada oración";
    }

    updateDoneButtonState();
    closeUpload();
    resultOverlay.classList.add("is-open");
  }

  function setSelectedFile(file) {
    if (!file) return;
    selectedFile = file;
    dropzoneText.textContent = file.name;
    updateUploadButtonState();
  }

  uploadOpenBtn.addEventListener("click", openUpload);
  uploadCancelBtn.addEventListener("click", closeUpload);
  uploadTypeButtons.forEach((btn) => {
    btn.addEventListener("click", () => setUploadType(btn.dataset.type));
  });

  manualEditorOpenBtn.addEventListener("click", () => {
    openManualEditor(currentUploadType);
  });

  dropzone.addEventListener("dragover", (event) => {
    event.preventDefault();
    dropzone.classList.add("is-dragover");
  });

  dropzone.addEventListener("dragleave", () => {
    dropzone.classList.remove("is-dragover");
  });

  dropzone.addEventListener("drop", (event) => {
    event.preventDefault();
    dropzone.classList.remove("is-dragover");
    const file = event.dataTransfer.files && event.dataTransfer.files[0];
    setSelectedFile(file);
  });

  uploadFileInput.addEventListener("change", () => {
    setSelectedFile(uploadFileInput.files && uploadFileInput.files[0]);
  });

  function showLoading(message = "Extrayendo texto y generando resumen con IA...") {
    loadingSpinner.hidden = false;
    loadingText.textContent = message;
    loadingCloseBtn.hidden = true;
    loadingOverlay.classList.add("is-open");
  }

  function showLoadingError(message) {
    loadingSpinner.hidden = true;
    loadingText.textContent = message;
    loadingCloseBtn.hidden = false;
  }

  async function saveSentenceMaterial(sentences) {
    const formData = new FormData();
    formData.append("tipo_material", "oracion");
    formData.append("title", currentMaterialTitle);
    formData.append("sentences_json", JSON.stringify(sentences));
    formData.append("id_periodo", uploadPeriodoSelect.value);
    formData.append("id_tema", uploadTemaSelect.value);

    const response = await authorizedFetch("/api/material/save", {
      method: "POST",
      body: formData,
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "No se pudieron guardar las oraciones.");
    }
  }

  async function saveDesignedImageSentenceMaterial() {
    const formData = new FormData();
    formData.append("tipo_material", "oracion_imagen");
    formData.append("title", currentMaterialTitle);
    formData.append("staging_token", imageDesignToken);
    formData.append("sentences_json", JSON.stringify(designSentences.map((sentence) => ({
      texto: sentence.texto,
      sustantivos: sentence.sustantivos.map((noun) => noun.palabra),
      staging_index: sentence.staging_index,
    }))));
    formData.append("id_periodo", uploadPeriodoSelect.value);
    formData.append("id_tema", uploadTemaSelect.value);

    const response = await authorizedFetch("/api/material/save", {
      method: "POST",
      body: formData,
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "No se pudieron guardar las oraciones con imágenes.");
    }
    return data;
  }

  // Modo editor de "oracion_imagen": a diferencia de saveDesignedImageSentenceMaterial
  // (que aprueba un diseño ya generado en el servidor, identificado por
  // staging_token), aquí las imágenes nunca pasaron por el servidor -viven
  // solo como File en cada fila (ver buildNounImagePicker)- así que se
  // envían junto con el resto en el mismo POST. `rowIndex` viaja como
  // "staging_index" -mismo nombre que ya lee /api/material/save para
  // volver a relacionar cada oración con sus imágenes aunque el servidor
  // descarte alguna fila duplicada al normalizar.
  async function saveManualImageSentenceMaterial(items) {
    const formData = new FormData();
    formData.append("tipo_material", "oracion_imagen");
    formData.append("title", currentMaterialTitle);
    formData.append("sentences_json", JSON.stringify(items.map((item) => ({
      texto: item.texto,
      sustantivos: item.sustantivos,
      staging_index: item.rowIndex,
    }))));
    formData.append("id_periodo", uploadPeriodoSelect.value);
    formData.append("id_tema", uploadTemaSelect.value);
    items.forEach((item) => {
      item.files.forEach((file, nounIndex) => {
        formData.append(`imagen_${item.rowIndex}_${nounIndex}`, file, file.name);
      });
    });

    const response = await authorizedFetch("/api/material/save", {
      method: "POST",
      body: formData,
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "No se pudieron guardar las oraciones con imágenes.");
    }
    return data;
  }

  async function saveStoryMaterial(transcribedText, summaryText, questionsData) {
    const formData = new FormData();
    formData.append("tipo_material", "cuento");
    formData.append("title", currentMaterialTitle);
    formData.append("transcribed_text", transcribedText);
    formData.append("summary_text", summaryText);
    formData.append("questions_json", JSON.stringify(questionsData));
    formData.append("audio_full", audioFullBlob, "audio.wav");
    formData.append("audio_summary", audioSummaryBlob, "audio_resumen.wav");
    formData.append("id_periodo", uploadPeriodoSelect.value);
    formData.append("id_tema", uploadTemaSelect.value);
    if (currentTargetDurationMinutes !== null) {
      formData.append("target_duration_minutes", String(currentTargetDurationMinutes));
    }

    const response = await authorizedFetch("/api/material/save", {
      method: "POST",
      body: formData,
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "No se pudo guardar el material.");
    }
    return data;
  }

  async function prepareImageSentenceDesign(items) {
    resetImageDesignState();
    resultOverlay.classList.remove("is-open");
    showLoading("Generando las imágenes con IA, puede tardar un momento");

    try {
      const response = await authorizedFetch("/api/material/image-sentences/prepare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: currentMaterialTitle, items }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.error || "No se pudieron generar las imágenes.");
      }

      imageDesignToken = typeof data.token === "string" ? data.token : "";
      designSentences = (Array.isArray(data.items) ? data.items : []).map((item) => ({
        ...item,
        staging_index: item.index,
        sustantivos: Array.isArray(item.sustantivos)
          ? item.sustantivos.map((noun) => ({ ...noun }))
          : [],
      }));
      if (!imageDesignToken || !designSentences.length) {
        throw new Error("No se recibió un diseño válido para las oraciones.");
      }

      currentDesignIndex = 0;
      renderDesignSentence();
      imageDesignTitle.textContent = currentMaterialTitle;
      imageDesignOverlay.classList.add("is-open");
    } catch (error) {
      resetImageDesignState();
      resultOverlay.classList.add("is-open");
      throw error;
    } finally {
      loadingOverlay.classList.remove("is-open");
    }
  }

  async function saveDesignedBitsMaterial() {
    const formData = new FormData();
    formData.append("tipo_material", "bits");
    formData.append("title", currentMaterialTitle);
    formData.append("staging_token", bitsDesignToken);
    formData.append("bits_json", JSON.stringify(designBits.map((bit) => ({
      palabra: bit.palabra,
      staging_index: bit.staging_index,
    }))));
    formData.append("id_periodo", uploadPeriodoSelect.value);
    formData.append("id_tema", uploadTemaSelect.value);

    const response = await authorizedFetch("/api/material/save", {
      method: "POST",
      body: formData,
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "No se pudieron guardar los bits.");
    }
    return data;
  }

  // Modo editor de "bits": mismo principio que saveManualImageSentenceMaterial
  // pero con una sola imagen por fila (sin sufijo de sustantivo en el nombre
  // del campo).
  async function saveManualBitsMaterial(items) {
    const formData = new FormData();
    formData.append("tipo_material", "bits");
    formData.append("title", currentMaterialTitle);
    formData.append("bits_json", JSON.stringify(items.map((item) => ({
      palabra: item.palabra,
      staging_index: item.rowIndex,
    }))));
    formData.append("id_periodo", uploadPeriodoSelect.value);
    formData.append("id_tema", uploadTemaSelect.value);
    items.forEach((item) => {
      if (item.file) {
        formData.append(`imagen_${item.rowIndex}`, item.file, item.file.name);
      }
    });

    const response = await authorizedFetch("/api/material/save", {
      method: "POST",
      body: formData,
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "No se pudieron guardar los bits.");
    }
    return data;
  }

  async function prepareBitsDesign(items) {
    resetBitsDesignState();
    resultOverlay.classList.remove("is-open");
    showLoading("Generando las imágenes con IA, puede tardar un momento");

    try {
      const response = await authorizedFetch("/api/bits/prepare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: currentMaterialTitle, items }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.error || "No se pudieron generar las imágenes.");
      }

      bitsDesignToken = typeof data.token === "string" ? data.token : "";
      designBits = (Array.isArray(data.items) ? data.items : []).map((item) => ({ ...item, staging_index: item.index }));
      if (!bitsDesignToken || !designBits.length) {
        throw new Error("No se recibió un diseño válido para los bits.");
      }

      currentBitsDesignIndex = 0;
      renderBitsDesignItem();
      bitsDesignTitle.textContent = currentMaterialTitle;
      bitsDesignOverlay.classList.add("is-open");
    } catch (error) {
      resetBitsDesignState();
      resultOverlay.classList.add("is-open");
      throw error;
    } finally {
      loadingOverlay.classList.remove("is-open");
    }
  }

  uploadStartBtn.addEventListener("click", async () => {
    if (!selectedFile) return;

    currentMaterialTitle = uploadTitleInput.value.trim() || selectedFile.name;
    const uploadType = currentUploadType;

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("title", currentMaterialTitle);
    formData.append("tipo_material", uploadType);

    closeUpload();
    showLoading(uploadType === "oracion_imagen"
      ? "Identificando las oraciones con imagenes con IA..."
      : uploadType === "oracion"
        ? "Identificando las oraciones con IA..."
        : uploadType === "bits"
          ? "Identificando las palabras con IA..."
          : undefined);

    try {
      const response = await authorizedFetch("/api/material/process", {
        method: "POST",
        body: formData,
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "No se pudo procesar el documento.");
      }

      currentTargetDurationMinutes = null;
      configureResultModalForType(uploadType);
      resetResultState();

      if (uploadType === "oracion_imagen") {
        renderImageSentenceRows(data.items || []);
        resultSubtitle.textContent = "A partir del documento original - revisa las oraciones y sus dos sustantivos antes de aprobar";
      } else if (uploadType === "bits") {
        renderBitsRows(data.items || []);
        resultSubtitle.textContent = "A partir del documento original - revisa las palabras antes de aprobar";
      } else if (uploadType === "oracion") {
        lastSentenceContext = { topic: currentMaterialTitle, grade_level: "" };
        renderSentences(data.sentences || []);
        resultSubtitle.textContent = "A partir del documento original · revisa las oraciones identificadas antes de aprobar";
      } else {
        resultTranscribedText.textContent = data.transcribed_text;
        resultSummaryText.textContent = data.summary_text;
        resultSubtitle.textContent = "A partir del documento original · revisa el contenido antes de aprobar";
      }

      loadingOverlay.classList.remove("is-open");
      resultOverlay.classList.add("is-open");
    } catch (error) {
      showLoadingError(error.message || "No se pudo procesar el documento.");
    }
  });

  loadingCloseBtn.addEventListener("click", () => {
    loadingOverlay.classList.remove("is-open");
  });

  resultCancelBtn.addEventListener("click", () => {
    resultOverlay.classList.remove("is-open");
    resetResultState();
  });

  classifyBackBtn.addEventListener("click", () => {
    classifyOverlay.classList.remove("is-open");
    pendingSave?.backOverlay.classList.add("is-open");
  });

  classifySaveBtn.addEventListener("click", async () => {
    if (!pendingSave || classifySaveBtn.disabled) return;
    const originalLabel = classifySaveBtn.textContent;
    classifySaveBtn.disabled = true;
    classifyBackBtn.disabled = true;
    classifySaveBtn.textContent = "Guardando...";
    try {
      await pendingSave.run();
      classifyOverlay.classList.remove("is-open");
      window.location.reload();
    } catch (error) {
      alert(error.message || "No se pudo guardar el material.");
      classifySaveBtn.disabled = false;
      classifyBackBtn.disabled = false;
      classifySaveBtn.textContent = originalLabel;
    }
  });

  // El nombre del material se puede corregir aquí mismo, no solo en el
  // input inicial del modal de subida: currentMaterialTitle es lo que
  // finalmente viaja en el "title" del guardado (ver saveSentenceMaterial,
  // saveDesignedImageSentenceMaterial y el guardado del cuento más abajo),
  // así que basta con mantenerlo sincronizado con lo que quede escrito en
  // el título.
  resultModalTitle.addEventListener("input", () => {
    currentMaterialTitle = resultModalTitle.textContent.replace(/\s+/g, " ").trim();
  });

  // Mismo nombre editable en el paso de diseño de imágenes: saveDesignedImageSentenceMaterial
  // también lee currentMaterialTitle al guardar.
  imageDesignTitle.addEventListener("input", () => {
    currentMaterialTitle = imageDesignTitle.textContent.replace(/\s+/g, " ").trim();
  });

  // "Crear con IA" genera un cuento o un set de oraciones. Ambos borradores
  // caen en la misma pantalla de revisión/edición antes de crear el material.
  const storyTypeButtons = [storyTypeCuentoBtn, storyTypeOracionBtn, storyTypeOracionImagenBtn, storyTypeBitsBtn];
  const storyFieldGroups = {
    cuento: storyCuentoFields,
    oracion: storySentenceFields,
    oracion_imagen: storyImageFields,
    bits: storyBitsFields,
  };
  const storyCopy = {
    cuento: [
      "Crear un cuento con IA",
      "Define aquí los datos del cuento y la IA prepara un borrador editable.",
    ],
    oracion: [
      "Crear oraciones con IA",
      "Indica el tema y el nivel. La IA prepara un borrador de oraciones para revisar y editar antes de crear el material.",
    ],
    oracion_imagen: [
      "Crear oraciones con imágenes con IA",
      "Indica el tema y el nivel. La IA prepara un borrador de oraciones con una imagen para cada una, para revisar antes de crear el material.",
    ],
    // TODO: título/descripción reales cuando se implemente la generación de bits.
    bits: [
      "Crear bits con IA",
      "Pendiente de definir.",
    ],
  };

  function setStoryType(type) {
    currentStoryType = type;
    storyTypeButtons.forEach((btn) => {
      const active = btn.dataset.type === type;
      btn.classList.toggle("is-active", active);
      btn.setAttribute("aria-selected", String(active));
    });
    Object.entries(storyFieldGroups).forEach(([key, group]) => {
      const active = key === type;
      group.hidden = !active;
      // Deshabilitar el grupo oculto lo excluye de la validación nativa del form.
      group.querySelectorAll("input, textarea").forEach((el) => { el.disabled = !active; });
    });
    const [title, description] = storyCopy[type];
    storyModalTitle.textContent = title;
    storyModalDescription.textContent = description;
  }

  storyTypeButtons.forEach((btn) => {
    btn.addEventListener("click", () => setStoryType(btn.dataset.type));
  });

  storyOpenBtn.addEventListener("click", () => {
    resetImageDesignState();
    resetBitsDesignState();
    storyForm.reset();
    setStoryType("cuento");
    storyOverlay.classList.add("is-open");
  });

  storyCancelBtn.addEventListener("click", () => {
    storyOverlay.classList.remove("is-open");
  });

  // "Oraciones con imágenes": cada oración conserva los dos sustantivos
  // concretos que más adelante se reemplazarán por imágenes.
  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
  }

  function markNouns(texto, nouns) {
    const source = String(texto || "");
    const escapedNouns = Array.from(new Set(
      (nouns || [])
        .map((noun) => String(noun || "").trim())
        .filter(Boolean)
    ))
      .sort((a, b) => b.length - a.length)
      .map((noun) => noun.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
    if (!escapedNouns.length) return escapeHtml(source);

    const matcher = new RegExp(escapedNouns.join("|"), "gi");
    let html = "";
    let cursor = 0;
    let match = matcher.exec(source);
    while (match) {
      html += escapeHtml(source.slice(cursor, match.index));
      html += `<mark>${escapeHtml(match[0])}</mark>`;
      cursor = match.index + match[0].length;
      match = matcher.exec(source);
    }
    html += escapeHtml(source.slice(cursor));
    return html;
  }

  storyForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    if (currentStoryType === "oracion_imagen") {
      const imagePayload = {
        topic: document.getElementById("sentenceImageTopic").value.trim(),
        grade_level: document.getElementById("sentenceImageGrade").value.trim(),
        count: Number.parseInt(document.getElementById("sentenceImageCount").value, 10),
        extra_details: document.getElementById("sentenceImageDetails").value.trim(),
      };

      storyGenerateBtn.disabled = true;
      storyGenerateBtn.textContent = "Creando…";
      storyOverlay.classList.remove("is-open");
      showLoading();
      loadingText.textContent = "Generando oraciones con dos sustantivos…";

      try {
        const response = await authorizedFetch("/api/sentences/generate-images", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(imagePayload),
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.error || "No se pudieron generar las oraciones.");
        }
        currentMaterialTitle = data.title;
        currentTargetDurationMinutes = null;
        configureResultModalForType("oracion_imagen");
        resetResultState();
        renderImageSentenceRows(data.items || []);
        resultSubtitle.textContent = "Borrador generado por IA - revisa las oraciones y sus dos sustantivos antes de crear el material";
        loadingOverlay.classList.remove("is-open");
        resultOverlay.classList.add("is-open");
      } catch (error) {
        showLoadingError(error.message || "No se pudieron generar las oraciones.");
      } finally {
        storyGenerateBtn.disabled = false;
        storyGenerateBtn.textContent = "Generar borrador";
      }
      return;
    }

    if (currentStoryType === "oracion") {
      const sentencePayload = {
        topic: document.getElementById("sentenceTopic").value.trim(),
        grade_level: document.getElementById("sentenceGrade").value.trim(),
        count: Number.parseInt(document.getElementById("sentenceCount").value, 10),
        extra_details: document.getElementById("sentenceDetails").value.trim(),
      };

      storyGenerateBtn.disabled = true;
      storyGenerateBtn.textContent = "Creando…";
      storyOverlay.classList.remove("is-open");
      showLoading();
      loadingText.textContent = "Generando un borrador de oraciones con IA…";

      try {
        const response = await authorizedFetch("/api/sentences/generate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(sentencePayload),
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.error || "No se pudieron generar las oraciones.");
        }

        currentMaterialTitle = data.title;
        currentTargetDurationMinutes = null;
        lastSentenceContext = {
          topic: sentencePayload.topic,
          grade_level: sentencePayload.grade_level,
        };
        configureResultModalForType("oracion");
        resetResultState();
        renderSentences(data.sentences || []);
        resultSubtitle.textContent = "Borrador generado por IA · revisa y edita las oraciones antes de crear el material";
        loadingOverlay.classList.remove("is-open");
        resultOverlay.classList.add("is-open");
      } catch (error) {
        showLoadingError(error.message || "No se pudieron generar las oraciones.");
      } finally {
        storyGenerateBtn.disabled = false;
        storyGenerateBtn.textContent = "Generar borrador";
      }
      return;
    }

    if (currentStoryType === "bits") {
      const bitsPayload = {
        silabas: bitsSyllablesInput.value.trim(),
        cantidad_silabas: Number.parseInt(bitsSyllableCountInput.value, 10),
        grade_level: bitsGradeInput.value.trim(),
        count: Number.parseInt(bitsCountInput.value, 10),
        extra_details: bitsDetailsInput.value.trim(),
      };

      storyGenerateBtn.disabled = true;
      storyGenerateBtn.textContent = "Creando…";
      storyOverlay.classList.remove("is-open");
      showLoading();
      loadingText.textContent = "Generando palabras con IA…";

      try {
        const response = await authorizedFetch("/api/bits/generate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(bitsPayload),
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.error || "No se pudieron generar las palabras.");
        }
        currentMaterialTitle = data.title;
        currentTargetDurationMinutes = null;
        configureResultModalForType("bits");
        resetResultState();
        renderBitsRows(data.items || []);
        resultSubtitle.textContent = "Borrador generado por IA - revisa las palabras antes de crear el material";
        loadingOverlay.classList.remove("is-open");
        resultOverlay.classList.add("is-open");
      } catch (error) {
        showLoadingError(error.message || "No se pudieron generar las palabras.");
      } finally {
        storyGenerateBtn.disabled = false;
        storyGenerateBtn.textContent = "Generar borrador";
      }
      return;
    }

    const payload = {
      character: document.getElementById("storyCharacter").value.trim(),
      setting: document.getElementById("storySetting").value.trim(),
      grade_level: document.getElementById("storyGrade").value.trim(),
      objective: document.getElementById("storyObjective").value.trim(),
      extra_details: document.getElementById("storyDetails").value.trim(),
      duration_minutes: Number.parseInt(document.getElementById("storyDuration").value, 10),
    };

    storyGenerateBtn.disabled = true;
    storyGenerateBtn.textContent = "Creando…";
    storyOverlay.classList.remove("is-open");
    showLoading();
    loadingText.textContent = "Creando un cuento con IA…";

    try {
      const response = await authorizedFetch("/api/story/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "No se pudo crear el cuento.");
      }

      currentMaterialTitle = data.title;
      currentTargetDurationMinutes = data.target_duration_minutes;
      resultTranscribedText.textContent = data.story;
      resultSummaryText.textContent = data.summary;
      configureResultModalForType("cuento");
      resultSubtitle.textContent = `Creado para ${data.target_duration_minutes} min · ${data.word_count} palabras · la miss puede editarlo antes de aprobar`;
      resetResultState();
      loadingOverlay.classList.remove("is-open");
      resultOverlay.classList.add("is-open");
    } catch (error) {
      showLoadingError(error.message || "No se pudo crear el cuento.");
    } finally {
      storyGenerateBtn.disabled = false;
      storyGenerateBtn.textContent = "Generar borrador";
    }
  });

  // El contenido en sí ya queda aprobado aquí -el guardado real (con
  // periodo y tema) pasa a classifyOverlay (ver openClassifyModal), un paso
  // aparte que se abre en vez de guardar directo.
  resultDoneBtn.addEventListener("click", async () => {
    if (currentResultType === "oracion_imagen") {
      const items = getImageSentencesData();
      if (!items.length) {
        alert("Agrega al menos una oración con dos sustantivos.");
        return;
      }
      if (manualImageEntryMode) {
        // Modo editor: nada de diseño con IA -las imágenes ya las subió la
        // docente en la misma revisión (ver getImageSentencesData).
        openClassifyModal(resultOverlay, () => saveManualImageSentenceMaterial(items));
        return;
      }
      if (items.length > 20) {
        alert("Puedes diseñar un máximo de 20 oraciones a la vez.");
        return;
      }
      const originalLabel = resultDoneBtn.textContent;
      resultDoneBtn.disabled = true;
      resultDoneBtn.textContent = "Generando imágenes...";
      try {
        await prepareImageSentenceDesign(items);
      } catch (error) {
        alert(error.message || "No se pudieron generar las imágenes.");
      } finally {
        resultDoneBtn.textContent = originalLabel;
        updateDoneButtonState();
      }
      return;
    }

    if (currentResultType === "bits") {
      const items = getBitsData();
      if (!items.length) {
        alert("Agrega al menos una palabra.");
        return;
      }
      if (manualBitsEntryMode) {
        // Modo editor: nada de diseño con IA -las imágenes ya las subió la
        // docente en la misma revisión (ver getBitsData).
        openClassifyModal(resultOverlay, () => saveManualBitsMaterial(items));
        return;
      }
      if (items.length > 20) {
        alert("Puedes diseñar un máximo de 20 bits a la vez.");
        return;
      }
      const originalLabel = resultDoneBtn.textContent;
      resultDoneBtn.disabled = true;
      resultDoneBtn.textContent = "Generando imágenes...";
      try {
        await prepareBitsDesign(items);
      } catch (error) {
        alert(error.message || "No se pudieron generar las imágenes.");
      } finally {
        resultDoneBtn.textContent = originalLabel;
        updateDoneButtonState();
      }
      return;
    }

    if (currentResultType === "oracion") {
      const sentences = getSentencesData();
      if (!sentences.length) {
        alert("No hay oraciones para guardar.");
        return;
      }
      openClassifyModal(resultOverlay, () => saveSentenceMaterial(sentences));
      return;
    }

    const transcribedText = resultTranscribedText.textContent.trim();
    const summaryText = resultSummaryText.textContent.trim();
    const questionsData = getQuestionsData();

    if (!transcribedText || !summaryText) {
      alert("Falta el texto completo o el resumen.");
      return;
    }
    if (!questionsData.length) {
      alert("Genera las preguntas antes de guardar.");
      return;
    }
    if (questionsData.some((question) => !question.respuesta_esperada)) {
      alert("Revisa y completa la respuesta esperada de cada pregunta.");
      return;
    }
    if (!audioFullBlob || !audioSummaryBlob) {
      alert("Genera ambos audios antes de guardar.");
      return;
    }

    openClassifyModal(resultOverlay, () => saveStoryMaterial(transcribedText, summaryText, questionsData));
  });

  // Text-to-speech: send the (possibly edited) text and play back the result
  const generateAudioFullBtn = document.getElementById("generateAudioFullBtn");
  const generateAudioSummaryBtn = document.getElementById("generateAudioSummaryBtn");
  const resultAudioFull = document.getElementById("resultAudioFull");
  const resultAudioSummary = document.getElementById("resultAudioSummary");
  const resultAudioFullMeta = document.getElementById("resultAudioFullMeta");
  const resultAudioSummaryMeta = document.getElementById("resultAudioSummaryMeta");

  function formatAudioDuration(seconds) {
    if (!Number.isFinite(seconds)) return "";
    const roundedSeconds = Math.max(0, Math.round(seconds));
    const minutes = Math.floor(roundedSeconds / 60);
    const remainder = roundedSeconds % 60;
    return minutes ? `${minutes} min ${String(remainder).padStart(2, "0")} s` : `${remainder} s`;
  }

  function invalidateAudio(audioEl, kind) {
    if (audioEl.src) URL.revokeObjectURL(audioEl.src);
    audioEl.removeAttribute("src");
    audioEl.load();
    if (kind === "full") {
      audioFullReady = false;
      audioFullBlob = null;
      audioFullDurationSeconds = null;
      resultAudioFullMeta.textContent = "";
    } else {
      audioSummaryReady = false;
      audioSummaryBlob = null;
      audioSummaryDurationSeconds = null;
      resultAudioSummaryMeta.textContent = "";
    }
    updateDoneButtonState();
  }

  resultTranscribedText.addEventListener("input", () => {
    if (audioFullReady) invalidateAudio(resultAudioFull, "full");
    updateDoneButtonState();
  });
  resultSummaryText.addEventListener("input", () => {
    if (audioSummaryReady) invalidateAudio(resultAudioSummary, "summary");
  });

  async function fetchSpeech(text, targetDurationMinutes = null) {
    const payload = { text };
    if (targetDurationMinutes !== null) {
      payload.target_duration_minutes = targetDurationMinutes;
    }
    const response = await authorizedFetch("/api/material/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.error || "No se pudo generar el audio.");
    }

    const durationSeconds = Number.parseFloat(
      response.headers.get("X-MAXCIM-Audio-Duration-Seconds") || ""
    );
    return {
      blob: await response.blob(),
      durationSeconds: Number.isFinite(durationSeconds) ? durationSeconds : null,
    };
  }

  async function generateAudio(button, audioEl, getText, targetDurationMinutes, onSuccess) {
    const text = (getText() || "").trim();
    if (!text) {
      alert("No hay texto para generar el audio.");
      return;
    }

    const originalLabel = button.textContent;
    button.disabled = true;
    button.textContent = "Generando...";

    try {
      const { blob, durationSeconds } = await fetchSpeech(text, targetDurationMinutes);
      if (audioEl.src) {
        URL.revokeObjectURL(audioEl.src);
      }
      audioEl.src = URL.createObjectURL(blob);
      audioEl.play().catch(() => {});
      onSuccess(blob, durationSeconds);
    } catch (error) {
      alert(error.message || "No se pudo generar el audio.");
    } finally {
      button.disabled = false;
      button.textContent = originalLabel;
    }
  }

  generateAudioFullBtn.addEventListener("click", () => {
    generateAudio(generateAudioFullBtn, resultAudioFull, () => resultTranscribedText.textContent, currentTargetDurationMinutes, (blob, durationSeconds) => {
      audioFullBlob = blob;
      audioFullReady = true;
      audioFullDurationSeconds = durationSeconds;
      resultAudioFullMeta.textContent = durationSeconds === null
        ? "Audio completo generado"
        : `Duración real: ${formatAudioDuration(durationSeconds)}${currentTargetDurationMinutes === null ? "" : ` · objetivo: ${currentTargetDurationMinutes} min`}`;
      updateDoneButtonState();
    });
  });

  generateAudioSummaryBtn.addEventListener("click", () => {
    generateAudio(generateAudioSummaryBtn, resultAudioSummary, () => resultSummaryText.textContent, null, (blob, durationSeconds) => {
      audioSummaryBlob = blob;
      audioSummaryReady = true;
      audioSummaryDurationSeconds = durationSeconds;
      resultAudioSummaryMeta.textContent = durationSeconds === null
        ? "Audio resumen generado"
        : `Duración real: ${formatAudioDuration(durationSeconds)}`;
      updateDoneButtonState();
    });
  });

  // El periodo y el tema ya no se eligen aquí -eso pasó a classifyOverlay,
  // un paso posterior (ver openClassifyModal)- así que este botón solo
  // depende de que el contenido en sí esté listo.
  function updateDoneButtonState() {
    let contentReady;
    if (currentResultType === "oracion_imagen") {
      // getImageSentencesData() también marca en rojo las filas incompletas
      // (efecto secundario deseado); no se usa su cantidad para decidir si
      // ya se puede guardar porque deduplica por texto -dos oraciones
      // completas con el mismo texto no deberían bloquear el guardado.
      getImageSentencesData();
      contentReady = allImageSentenceRowsComplete();
    } else if (currentResultType === "bits") {
      // Mismo motivo que oracion_imagen: marca en rojo las filas incompletas
      // como efecto secundario, y no usa la cantidad devuelta (dedupe por
      // palabra) para decidir si ya se puede guardar.
      getBitsData();
      contentReady = allBitsRowsComplete();
    } else if (currentResultType === "oracion") {
      contentReady = sentenceRowsAreValid();
    } else {
      contentReady = audioFullReady && audioSummaryReady && questionsReady;
    }
    resultDoneBtn.disabled = !contentReady;
  }

  function resetResultState() {
    resetImageDesignState();
    resetBitsDesignState();
    audioFullReady = false;
    audioSummaryReady = false;
    questionsReady = false;
    audioFullBlob = null;
    audioSummaryBlob = null;
    audioFullDurationSeconds = null;
    audioSummaryDurationSeconds = null;

    if (resultAudioFull.src) {
      URL.revokeObjectURL(resultAudioFull.src);
    }
    if (resultAudioSummary.src) {
      URL.revokeObjectURL(resultAudioSummary.src);
    }
    resultAudioFull.removeAttribute("src");
    resultAudioSummary.removeAttribute("src");
    resultAudioFullMeta.textContent = "";
    resultAudioSummaryMeta.textContent = "";
    questionsResult.innerHTML = "";
    resultSentencesList.innerHTML = "";

    // El tema se elige de nuevo para cada material; parte sin selección y con
    // las opciones acotadas al periodo vigente.
    filterUploadTemas(true);
    classifyOverlay.classList.remove("is-open");
    pendingSave = null;

    updateDoneButtonState();
  }

  // Último paso antes de guardar de verdad: contenido ya aprobado (cuento,
  // oraciones, oraciones con imágenes -generadas o del modo editor-), solo
  // falta el periodo y el tema. `run` hace el guardado en sí (uno de los
  // saveXxxMaterial de más arriba); `backOverlay` es a dónde volver si la
  // docente toca "Volver" en vez de "Guardar material" (ver
  // classifyBackBtn/classifySaveBtn, más abajo).
  function openClassifyModal(backOverlay, run) {
    pendingSave = { backOverlay, run };
    classifyMaterialTitle.textContent = currentMaterialTitle;
    classifySaveBtn.textContent = "Guardar material";
    classifyBackBtn.disabled = false;
    updateClassifySaveState();
    backOverlay.classList.remove("is-open");
    classifyOverlay.classList.add("is-open");
  }

  function updateClassifySaveState() {
    classifySaveBtn.disabled = !uploadTemaSelect.value;
  }

  // Sentence review: one editable line per sentence. The teacher can fix
  // wording, clear a line to drop it, remove it, add blank lines, or ask the
  // IA for more — mirroring how the story questions are reviewed before saving.
  function appendSentenceItem(text = "", { focus = false } = {}) {
    const item = document.createElement("li");
    item.className = "sentences-review__item";

    const editable = document.createElement("div");
    editable.className = "sentences-review__editable";
    editable.contentEditable = "true";
    editable.spellcheck = true;
    editable.textContent = typeof text === "string" ? text : "";
    // Recién creada, la fila no se marca inválida todavía aunque esté vacía
    // -eso se vería mal apenas se abre el editor-; "touched" pasa a true en
    // cuanto la docente escribe algo o sale del campo, y desde ahí sí se
    // valida que no quede en blanco (ver sentenceRowsAreValid).
    const markTouched = () => {
      item.dataset.touched = "true";
      updateDoneButtonState();
    };
    editable.addEventListener("input", markTouched);
    editable.addEventListener("blur", markTouched);

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "sentences-review__remove";
    remove.title = "Quitar esta oración";
    remove.textContent = "✕";
    remove.addEventListener("click", () => {
      item.remove();
      updateDoneButtonState();
    });

    item.append(editable, remove);
    resultSentencesList.appendChild(item);
    if (focus) editable.focus();
  }

  function renderSentences(sentences) {
    resultSentencesList.innerHTML = "";
    (sentences || []).forEach((sentence) => appendSentenceItem(sentence));
    updateDoneButtonState();
  }

  function getSentencesData() {
    return Array.from(resultSentencesList.querySelectorAll(".sentences-review__item:not(.sentences-review__item--image) .sentences-review__editable"))
      .map((el) => el.textContent.replace(/\s+/g, " ").trim())
      .filter(Boolean);
  }

  // Una oración no puede quedar en blanco (sea que vengan de un documento,
  // de la IA o escritas a mano) - para quitar una línea se usa el botón ✕,
  // no dejarla vacía. Marca cada fila ya "tocada" que esté vacía y devuelve
  // false si falta alguna por corregir, o si no queda ninguna oración.
  function sentenceRowsAreValid() {
    const rows = Array.from(
      resultSentencesList.querySelectorAll(".sentences-review__item:not(.sentences-review__item--image)")
    );
    if (!rows.length) return false;
    let valid = true;
    rows.forEach((row) => {
      const blank = !row.querySelector(".sentences-review__editable").textContent.replace(/\s+/g, " ").trim();
      row.classList.toggle("sentences-review__item--invalid", blank && row.dataset.touched === "true");
      if (blank) valid = false;
    });
    return valid;
  }

  // Cuadro para subir, a mano, la imagen que reemplazará a un sustantivo
  // (modo editor). El archivo elegido se previsualiza aquí mismo
  // (URL.createObjectURL) y recién se envía al guardar el material -junto
  // con el resto de la oración- por eso `onChange` avisa a la fila para que
  // se revalide (ver appendImageSentenceItem).
  function buildNounImagePicker(index, onChange) {
    const wrap = document.createElement("div");
    wrap.className = "sentences-review__image-picker";

    const preview = document.createElement("img");
    preview.className = "sentences-review__image-preview";
    preview.alt = "";
    preview.hidden = true;

    const dropLabel = document.createElement("label");
    dropLabel.className = "sentences-review__image-dropzone";

    const icon = document.createElement("span");
    icon.className = "sentences-review__image-dropzone-icon";
    icon.textContent = "🖼️";

    const text = document.createElement("span");
    text.className = "sentences-review__image-dropzone-text";
    text.textContent = "Subir imagen";

    const fileInput = document.createElement("input");
    fileInput.type = "file";
    fileInput.accept = "image/*";
    fileInput.hidden = true;
    fileInput.dataset.imageSentenceFile = String(index);

    fileInput.addEventListener("change", () => {
      const file = fileInput.files && fileInput.files[0];
      if (!file) return;
      preview.src = URL.createObjectURL(file);
      preview.hidden = false;
      text.textContent = file.name;
      dropLabel.classList.add("has-image");
      dropLabel.setAttribute("aria-invalid", "false");
      onChange();
    });

    dropLabel.append(icon, text, fileInput);
    wrap.append(preview, dropLabel);
    return wrap;
  }

  function appendImageSentenceItem(item = {}, { focus = false } = {}) {
    const row = document.createElement("li");
    row.className = "sentences-review__item sentences-review__item--image";
    // Único dentro de esta revisión: ver el comentario de imageSentenceRowSeq.
    row.dataset.rowIndex = String(imageSentenceRowSeq++);

    const content = document.createElement("div");
    content.className = "sentences-review__image-content";

    const editable = document.createElement("div");
    editable.className = "sentences-review__editable";
    editable.contentEditable = "true";
    editable.spellcheck = true;
    editable.dataset.imageSentenceText = "";
    editable.textContent = typeof item.texto === "string" ? item.texto : "";

    const preview = document.createElement("div");
    preview.className = "sentences-review__preview";
    preview.setAttribute("aria-label", "Vista previa con sustantivos resaltados");

    const nouns = Array.isArray(item.sustantivos) ? item.sustantivos : [];
    const nounFields = document.createElement("div");
    nounFields.className = "sentences-review__nouns";
    const nounInputs = [0, 1].map((index) => {
      const field = document.createElement("div");
      field.className = "sentences-review__noun-field";

      const label = document.createElement("label");
      label.className = "sentences-review__noun-label";

      const labelText = document.createElement("span");
      labelText.textContent = `Sustantivo ${index + 1}`;

      const input = document.createElement("input");
      input.type = "text";
      input.className = "sentences-review__noun-input";
      input.value = typeof nouns[index] === "string" ? nouns[index] : "";
      input.maxLength = 300;
      input.autocomplete = "off";
      input.dataset.imageSentenceNoun = String(index);

      label.append(labelText, input);
      field.appendChild(label);
      // Solo en modo editor: la palabra ya trae su propio cuadro para subir
      // la imagen que la reemplazará -sin esto, la imagen se genera después
      // con IA en el paso de diseño (image-sentences/prepare).
      if (manualImageEntryMode) {
        field.appendChild(buildNounImagePicker(index, handleFieldChange));
      }
      nounFields.appendChild(field);
      return input;
    });

    function refreshPreview() {
      const text = editable.textContent.replace(/\s+/g, " ").trim();
      const currentNouns = nounInputs.map((input) => input.value.replace(/\s+/g, " ").trim());
      preview.innerHTML = text
        ? markNouns(text, currentNouns)
        : '<span class="sentences-review__preview-empty">Vista previa de la oración</span>';
    }

    // Recién creada, la fila no se marca inválida todavía aunque esté
    // incompleta -eso se vería mal apenas se abre la revisión-; "touched"
    // pasa a true en cuanto la docente edita algo o sale de un campo, y
    // desde ahí sí se exige texto + los 2 sustantivos (ver getImageSentencesData).
    function handleFieldChange() {
      row.dataset.touched = "true";
      refreshPreview();
      updateDoneButtonState();
    }

    editable.addEventListener("input", handleFieldChange);
    editable.addEventListener("blur", handleFieldChange);
    nounInputs.forEach((input) => {
      input.addEventListener("input", handleFieldChange);
      input.addEventListener("blur", handleFieldChange);
    });

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "sentences-review__remove";
    remove.title = "Quitar esta oración";
    remove.setAttribute("aria-label", "Quitar esta oración");
    remove.textContent = "✕";
    remove.addEventListener("click", () => {
      row.remove();
      updateDoneButtonState();
    });

    content.append(editable, preview, nounFields);
    row.append(content, remove);
    resultSentencesList.appendChild(row);
    refreshPreview();
    if (focus) editable.focus();
  }

  function renderImageSentenceRows(items) {
    resultSentencesList.innerHTML = "";
    (items || []).forEach((item) => appendImageSentenceItem(item));
    updateDoneButtonState();
  }

  // Fila a fila, los 2 File elegidos en los cuadros de subir imagen (modo
  // editor); [] si no está en ese modo, o si a alguno todavía le falta el
  // archivo (undefined en su lugar).
  function getImageSentenceFiles(row) {
    if (!manualImageEntryMode) return [];
    return Array.from(row.querySelectorAll("[data-image-sentence-file]"))
      .map((input) => input.files && input.files[0]);
  }

  // Como sentenceRowsAreValid(), pero para "oracion_imagen": exige texto +
  // 2 sustantivos en cada fila, sin deduplicar (a diferencia de
  // getImageSentencesData, que sí deduplica porque arma el payload a enviar).
  // En modo editor también exige las 2 imágenes que sube la docente -sin
  // eso no hay nada que guardar todavía.
  function allImageSentenceRowsComplete() {
    const rows = Array.from(resultSentencesList.querySelectorAll(".sentences-review__item--image"));
    if (!rows.length) return false;
    return rows.every((row) => {
      const text = row.querySelector("[data-image-sentence-text]")
        ?.textContent.replace(/\s+/g, " ").trim() || "";
      const nouns = Array.from(row.querySelectorAll("[data-image-sentence-noun]"))
        .map((input) => input.value.replace(/\s+/g, " ").trim());
      if (!(Boolean(text) && nouns.length === 2 && nouns.every(Boolean))) return false;
      if (!manualImageEntryMode) return true;
      const files = getImageSentenceFiles(row);
      return files.length === 2 && files.every(Boolean);
    });
  }

  // Una oración con imágenes tampoco puede quedar en blanco ni incompleta:
  // hace falta el texto Y sus 2 sustantivos (y, en modo editor, sus 2
  // imágenes), sea que la fila venga de un documento, de la IA o se haya
  // escrito a mano. Igual que en las oraciones planas, solo se marca
  // inválida una vez "tocada" (ver appendImageSentenceItem). En modo editor
  // cada item también lleva `rowIndex` y `files`, que es lo que
  // saveManualImageSentenceMaterial necesita para guardar.
  function getImageSentencesData() {
    const seen = new Set();
    const items = [];
    Array.from(resultSentencesList.querySelectorAll(".sentences-review__item--image")).forEach((row) => {
      const text = row.querySelector("[data-image-sentence-text]")
        ?.textContent.replace(/\s+/g, " ").trim() || "";
      const nounInputs = Array.from(row.querySelectorAll("[data-image-sentence-noun]"));
      const nouns = nounInputs.map((input) => input.value.replace(/\s+/g, " ").trim());
      const files = getImageSentenceFiles(row);
      const imagesComplete = !manualImageEntryMode || (files.length === 2 && files.every(Boolean));
      const complete = Boolean(text) && nouns.length === 2 && nouns.every(Boolean) && imagesComplete;
      const touched = row.dataset.touched === "true";

      row.classList.toggle("sentences-review__item--invalid", touched && !complete);
      nounInputs.forEach((input) => {
        input.setAttribute("aria-invalid", String(touched && !complete && !input.value.trim()));
      });
      if (manualImageEntryMode) {
        row.querySelectorAll(".sentences-review__image-dropzone").forEach((dropzone, index) => {
          dropzone.setAttribute("aria-invalid", String(touched && !files[index]));
        });
      }

      const key = text.toLocaleLowerCase("es");
      if (complete && !seen.has(key) && items.length < 120) {
        seen.add(key);
        items.push({
          texto: text,
          sustantivos: nouns,
          ...(manualImageEntryMode ? { rowIndex: row.dataset.rowIndex, files } : {}),
        });
      }
    });
    return items;
  }

  // "Bits": una sola palabra + una imagen por fila (a diferencia de
  // "oracion_imagen", que tiene texto + 2 sustantivos). Reusa el mismo
  // esqueleto de fila (.sentences-review__item--image, .sentences-review__
  // editable, buildNounImagePicker) pero sin preview de sustantivos
  // resaltados ni grid de 2 columnas -no hace falta, es una sola palabra.
  function appendBitsItem(item = {}, { focus = false } = {}) {
    const row = document.createElement("li");
    row.className = "sentences-review__item sentences-review__item--image sentences-review__item--bit";
    // Único dentro de esta revisión: mismo propósito que imageSentenceRowSeq.
    row.dataset.rowIndex = String(bitRowSeq++);

    const content = document.createElement("div");
    content.className = "sentences-review__image-content";

    const editable = document.createElement("div");
    editable.className = "sentences-review__editable";
    editable.contentEditable = "true";
    editable.spellcheck = true;
    editable.dataset.bitWord = "";
    editable.textContent = typeof item.palabra === "string" ? item.palabra : "";

    // Recién creada, la fila no se marca inválida todavía aunque esté
    // incompleta (mismo criterio que appendImageSentenceItem).
    function handleFieldChange() {
      row.dataset.touched = "true";
      updateDoneButtonState();
    }

    editable.addEventListener("input", handleFieldChange);
    editable.addEventListener("blur", handleFieldChange);

    content.appendChild(editable);

    // Solo en modo editor: la palabra ya trae su propio cuadro para subir la
    // imagen que la representará -sin esto, la imagen se genera después con
    // IA en el paso de diseño (/api/bits/prepare).
    if (manualBitsEntryMode) {
      content.appendChild(buildNounImagePicker(0, handleFieldChange));
    }

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "sentences-review__remove";
    remove.title = "Quitar esta palabra";
    remove.setAttribute("aria-label", "Quitar esta palabra");
    remove.textContent = "✕";
    remove.addEventListener("click", () => {
      row.remove();
      updateDoneButtonState();
    });

    row.append(content, remove);
    resultSentencesList.appendChild(row);
    if (focus) editable.focus();
  }

  function renderBitsRows(items) {
    resultSentencesList.innerHTML = "";
    (items || []).forEach((item) => appendBitsItem(item));
    updateDoneButtonState();
  }

  // El File elegido en el cuadro de subir imagen (modo editor); null si no
  // está en ese modo, o si todavía no eligió archivo.
  function getBitsFile(row) {
    if (!manualBitsEntryMode) return null;
    const input = row.querySelector("[data-image-sentence-file]");
    return (input && input.files && input.files[0]) || null;
  }

  // Como allImageSentenceRowsComplete(), pero para "bits": exige la palabra
  // (y, en modo editor, su imagen) en cada fila, sin deduplicar.
  function allBitsRowsComplete() {
    const rows = Array.from(resultSentencesList.querySelectorAll(".sentences-review__item--bit"));
    if (!rows.length) return false;
    return rows.every((row) => {
      const word = row.querySelector("[data-bit-word]")?.textContent.replace(/\s+/g, " ").trim() || "";
      if (!word) return false;
      if (!manualBitsEntryMode) return true;
      return Boolean(getBitsFile(row));
    });
  }

  // Como getImageSentencesData(), pero para "bits": arma el payload a enviar
  // (deduplicado por palabra). En modo editor cada item también lleva
  // `rowIndex` y `file`, que es lo que saveManualBitsMaterial necesita.
  function getBitsData() {
    const seen = new Set();
    const items = [];
    Array.from(resultSentencesList.querySelectorAll(".sentences-review__item--bit")).forEach((row) => {
      const word = row.querySelector("[data-bit-word]")?.textContent.replace(/\s+/g, " ").trim() || "";
      const file = getBitsFile(row);
      const imageComplete = !manualBitsEntryMode || Boolean(file);
      const complete = Boolean(word) && imageComplete;
      const touched = row.dataset.touched === "true";

      row.classList.toggle("sentences-review__item--invalid", touched && !complete);
      if (manualBitsEntryMode) {
        row.querySelector(".sentences-review__image-dropzone")
          ?.setAttribute("aria-invalid", String(touched && !file));
      }

      const key = word.toLocaleLowerCase("es");
      if (complete && !seen.has(key) && items.length < 120) {
        seen.add(key);
        items.push({
          palabra: word,
          ...(manualBitsEntryMode ? { rowIndex: row.dataset.rowIndex, file } : {}),
        });
      }
    });
    return items;
  }

  function resetImageDesignState() {
    imageDesignToken = "";
    designSentences = [];
    currentDesignIndex = 0;
    imageDesignBusy = false;
    imageDesignOverlay.classList.remove("is-open");
    imageDesignMixedLine.replaceChildren();
    imageDesignNounControls.replaceChildren();
    imageDesignStage.hidden = true;
    imageDesignEmpty.hidden = true;
    imageDesignCounter.textContent = "Oración 0 de 0";
    imageDesignPrevBtn.disabled = true;
    imageDesignNextBtn.disabled = true;
    imageDesignRemoveBtn.disabled = true;
    imageDesignSaveBtn.disabled = true;
    imageDesignSaveBtn.textContent = "Continuar";
  }

  function updateDesignNav() {
    const count = designSentences.length;
    imageDesignCounter.textContent = count
      ? `Oración ${currentDesignIndex + 1} de ${count}`
      : "Oración 0 de 0";
    imageDesignPrevBtn.disabled = imageDesignBusy || !count || currentDesignIndex === 0;
    imageDesignNextBtn.disabled = imageDesignBusy || !count || currentDesignIndex >= count - 1;
    imageDesignRemoveBtn.disabled = imageDesignBusy || !count;
    imageDesignSaveBtn.disabled = imageDesignBusy || !count;
    imageDesignNounControls.querySelectorAll("input, button").forEach((control) => {
      control.disabled = imageDesignBusy;
    });
  }

  function appendDesignText(value) {
    if (!value) return;
    const text = document.createElement("span");
    text.className = "image-design__text";
    text.textContent = value;
    imageDesignMixedLine.appendChild(text);
  }

  function renderDesignMixedLine(sentence) {
    imageDesignMixedLine.replaceChildren();
    const template = String(sentence.plantilla || sentence.texto || "");
    const placeholderPattern = /\{\{([01])\}\}/g;
    let cursor = 0;
    let match = placeholderPattern.exec(template);

    while (match) {
      appendDesignText(template.slice(cursor, match.index));
      const nounIndex = Number.parseInt(match[1], 10);
      const noun = sentence.sustantivos[nounIndex];
      if (noun) {
        const image = document.createElement("img");
        image.className = "image-design__img";
        image.src = noun.imagen_url;
        image.alt = noun.palabra;
        image.dataset.nounIndex = String(nounIndex);
        imageDesignMixedLine.appendChild(image);
      }
      cursor = match.index + match[0].length;
      match = placeholderPattern.exec(template);
    }
    appendDesignText(template.slice(cursor));
  }

  async function regenerateDesignNoun(sentence, nounIndex, input, button) {
    const noun = sentence.sustantivos[nounIndex];
    const proposedWord = input.value.replace(/\s+/g, " ").trim();
    if (!proposedWord) {
      alert("Escribe el sustantivo antes de regenerar la imagen.");
      return;
    }

    const payload = {
      token: imageDesignToken,
      sentence_index: sentence.staging_index,
      noun_index: nounIndex,
    };
    if (proposedWord !== noun.palabra) {
      payload.palabra = proposedWord;
    }

    const originalLabel = button.textContent;
    imageDesignBusy = true;
    button.textContent = "Generando…";
    updateDesignNav();
    try {
      const response = await authorizedFetch("/api/material/image-sentences/regenerate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.error || "No se pudo regenerar la imagen.");
      }

      sentence.plantilla = data.plantilla;
      sentence.sustantivos[nounIndex] = {
        ...noun,
        palabra: data.palabra,
        imagen_url: data.imagen_url,
        fuente: data.fuente === "manual" ? "manual" : "ia",
      };
      if (designSentences[currentDesignIndex] === sentence) {
        renderDesignSentence();
      }
    } catch (error) {
      alert(error.message || "No se pudo regenerar la imagen.");
    } finally {
      imageDesignBusy = false;
      button.textContent = originalLabel;
      updateDesignNav();
    }
  }

  async function uploadDesignNounImage(sentence, nounIndex, input, fileInput, button) {
    const file = fileInput.files?.[0];
    if (!file || imageDesignBusy) {
      fileInput.value = "";
      return;
    }

    const noun = sentence.sustantivos[nounIndex];
    const proposedWord = input.value.replace(/\s+/g, " ").trim();
    if (!proposedWord) {
      fileInput.value = "";
      alert("Escribe el sustantivo antes de subir la imagen.");
      return;
    }

    const formData = new FormData();
    formData.append("token", imageDesignToken);
    formData.append("sentence_index", sentence.staging_index);
    formData.append("noun_index", nounIndex);
    if (proposedWord !== noun.palabra) {
      formData.append("palabra", proposedWord);
    }
    formData.append("imagen", file);

    const originalLabel = button.textContent;
    imageDesignBusy = true;
    button.textContent = "Subiendo…";
    updateDesignNav();
    try {
      const response = await authorizedFetch("/api/material/image-sentences/upload-image", {
        method: "POST",
        body: formData,
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.error || "No se pudo subir la imagen.");
      }

      sentence.plantilla = data.plantilla;
      sentence.sustantivos[nounIndex] = {
        ...noun,
        palabra: data.palabra,
        imagen_url: data.imagen_url,
        fuente: data.fuente === "ia" ? "ia" : "manual",
      };
      if (designSentences[currentDesignIndex] === sentence) {
        renderDesignSentence();
      }
    } catch (error) {
      alert(error.message || "No se pudo subir la imagen.");
    } finally {
      imageDesignBusy = false;
      fileInput.value = "";
      button.textContent = originalLabel;
      updateDesignNav();
    }
  }

  function renderDesignSentence() {
    const count = designSentences.length;
    if (!count) {
      currentDesignIndex = 0;
      imageDesignStage.hidden = true;
      imageDesignEmpty.hidden = false;
      imageDesignMixedLine.replaceChildren();
      imageDesignNounControls.replaceChildren();
      updateDesignNav();
      return;
    }

    currentDesignIndex = Math.min(Math.max(currentDesignIndex, 0), count - 1);
    const sentence = designSentences[currentDesignIndex];
    imageDesignStage.hidden = false;
    imageDesignEmpty.hidden = true;
    renderDesignMixedLine(sentence);
    imageDesignNounControls.replaceChildren();

    sentence.sustantivos.forEach((noun, nounIndex) => {
      const group = document.createElement("div");
      group.className = "image-design__noun-control";

      const label = document.createElement("label");
      label.className = "image-design__noun-label";
      const heading = document.createElement("span");
      heading.className = "image-design__noun-heading";
      const caption = document.createElement("span");
      caption.textContent = `Sustantivo ${nounIndex + 1}`;
      const source = document.createElement("span");
      const isManual = noun.fuente === "manual";
      source.className = `image-design__source image-design__source--${isManual ? "manual" : "ia"}`;
      source.textContent = isManual ? "Subida por ti" : "Generada por IA";
      heading.append(caption, source);
      const input = document.createElement("input");
      input.type = "text";
      input.className = "image-design__noun-input";
      input.maxLength = 60;
      input.autocomplete = "off";
      input.value = noun.palabra;
      label.append(heading, input);

      const actions = document.createElement("div");
      actions.className = "image-design__noun-actions";

      const regenerate = document.createElement("button");
      regenerate.type = "button";
      regenerate.className = "btn btn--accent image-design__regenerate";
      regenerate.textContent = "Regenerar";
      regenerate.addEventListener("click", () => {
        regenerateDesignNoun(sentence, nounIndex, input, regenerate);
      });

      const fileInput = document.createElement("input");
      fileInput.type = "file";
      fileInput.className = "image-design__file-input";
      fileInput.accept = "image/*";
      fileInput.hidden = true;

      const upload = document.createElement("button");
      upload.type = "button";
      upload.className = "btn btn--ghost image-design__upload";
      upload.textContent = "Subir imagen";
      upload.addEventListener("click", () => {
        fileInput.click();
      });
      fileInput.addEventListener("change", () => {
        uploadDesignNounImage(sentence, nounIndex, input, fileInput, upload);
      });

      actions.append(regenerate, fileInput, upload);
      group.append(label, actions);
      imageDesignNounControls.appendChild(group);
    });
    updateDesignNav();
  }

  imageDesignPrevBtn.addEventListener("click", () => {
    if (currentDesignIndex <= 0) return;
    currentDesignIndex -= 1;
    renderDesignSentence();
  });

  imageDesignNextBtn.addEventListener("click", () => {
    if (currentDesignIndex >= designSentences.length - 1) return;
    currentDesignIndex += 1;
    renderDesignSentence();
  });

  imageDesignRemoveBtn.addEventListener("click", () => {
    if (!designSentences.length) return;
    designSentences.splice(currentDesignIndex, 1);
    if (currentDesignIndex >= designSentences.length) {
      currentDesignIndex = Math.max(0, designSentences.length - 1);
    }
    renderDesignSentence();
  });

  imageDesignBackBtn.addEventListener("click", () => {
    resetImageDesignState();
    resultOverlay.classList.add("is-open");
    updateDoneButtonState();
  });

  // "Descartar" desde cualquiera de los dos overlays de diseño (oraciones
  // con imágenes o bits) vuelve todo el flujo al inicio, sin importar en
  // cuál de los dos estaba la docente.
  function discardEverything() {
    imageDesignOverlay.classList.remove("is-open");
    bitsDesignOverlay.classList.remove("is-open");
    resultOverlay.classList.remove("is-open");
    classifyOverlay.classList.remove("is-open");
    loadingOverlay.classList.remove("is-open");
    uploadOverlay.classList.remove("is-open");
    storyOverlay.classList.remove("is-open");
    resetResultState();
    resetUploadForm();
    storyForm.reset();
    setStoryType("cuento");
    currentResultType = "cuento";
    currentMaterialTitle = "";
    currentTargetDurationMinutes = null;
    lastSentenceContext = { topic: "", grade_level: "" };
  }

  imageDesignDiscardBtn.addEventListener("click", discardEverything);

  imageDesignSaveBtn.addEventListener("click", () => {
    if (!designSentences.length) {
      alert("No hay oraciones con imágenes para guardar.");
      return;
    }
    openClassifyModal(imageDesignOverlay, () => saveDesignedImageSentenceMaterial());
  });

  // --- Diseño de "bits": mismo patrón que el diseño de oraciones con
  // imágenes de arriba (resetImageDesignState/updateDesignNav/
  // renderDesignSentence/regenerateDesignNoun/uploadDesignNounImage), pero
  // una sola imagen por bit -sin plantilla, sin mixed-line, un solo control.

  function resetBitsDesignState() {
    bitsDesignToken = "";
    designBits = [];
    currentBitsDesignIndex = 0;
    bitsDesignBusy = false;
    bitsDesignOverlay.classList.remove("is-open");
    bitsDesignImage.removeAttribute("src");
    bitsDesignNounControls.replaceChildren();
    bitsDesignStage.hidden = true;
    bitsDesignEmpty.hidden = true;
    bitsDesignCounter.textContent = "Bit 0 de 0";
    bitsDesignPrevBtn.disabled = true;
    bitsDesignNextBtn.disabled = true;
    bitsDesignRemoveBtn.disabled = true;
    bitsDesignSaveBtn.disabled = true;
    bitsDesignSaveBtn.textContent = "Continuar";
  }

  function updateBitsDesignNav() {
    const count = designBits.length;
    bitsDesignCounter.textContent = count
      ? `Bit ${currentBitsDesignIndex + 1} de ${count}`
      : "Bit 0 de 0";
    bitsDesignPrevBtn.disabled = bitsDesignBusy || !count || currentBitsDesignIndex === 0;
    bitsDesignNextBtn.disabled = bitsDesignBusy || !count || currentBitsDesignIndex >= count - 1;
    bitsDesignRemoveBtn.disabled = bitsDesignBusy || !count;
    bitsDesignSaveBtn.disabled = bitsDesignBusy || !count;
    bitsDesignNounControls.querySelectorAll("input, button").forEach((control) => {
      control.disabled = bitsDesignBusy;
    });
  }

  async function regenerateBitsDesignImage(bit, input, button) {
    const proposedWord = input.value.replace(/\s+/g, " ").trim();
    if (!proposedWord) {
      alert("Escribe la palabra antes de regenerar la imagen.");
      return;
    }

    const payload = { token: bitsDesignToken, item_index: bit.staging_index };
    if (proposedWord !== bit.palabra) {
      payload.palabra = proposedWord;
    }

    const originalLabel = button.textContent;
    bitsDesignBusy = true;
    button.textContent = "Generando…";
    updateBitsDesignNav();
    try {
      const response = await authorizedFetch("/api/bits/regenerate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.error || "No se pudo regenerar la imagen.");
      }

      bit.palabra = data.palabra;
      bit.imagen_url = data.imagen_url;
      bit.fuente = data.fuente === "manual" ? "manual" : "ia";
      if (designBits[currentBitsDesignIndex] === bit) {
        renderBitsDesignItem();
      }
    } catch (error) {
      alert(error.message || "No se pudo regenerar la imagen.");
    } finally {
      bitsDesignBusy = false;
      button.textContent = originalLabel;
      updateBitsDesignNav();
    }
  }

  async function uploadBitsDesignImage(bit, input, fileInput, button) {
    const file = fileInput.files?.[0];
    if (!file || bitsDesignBusy) {
      fileInput.value = "";
      return;
    }

    const proposedWord = input.value.replace(/\s+/g, " ").trim();
    if (!proposedWord) {
      fileInput.value = "";
      alert("Escribe la palabra antes de subir la imagen.");
      return;
    }

    const formData = new FormData();
    formData.append("token", bitsDesignToken);
    formData.append("item_index", bit.staging_index);
    if (proposedWord !== bit.palabra) {
      formData.append("palabra", proposedWord);
    }
    formData.append("imagen", file);

    const originalLabel = button.textContent;
    bitsDesignBusy = true;
    button.textContent = "Subiendo…";
    updateBitsDesignNav();
    try {
      const response = await authorizedFetch("/api/bits/upload-image", {
        method: "POST",
        body: formData,
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.error || "No se pudo subir la imagen.");
      }

      bit.palabra = data.palabra;
      bit.imagen_url = data.imagen_url;
      bit.fuente = data.fuente === "ia" ? "ia" : "manual";
      if (designBits[currentBitsDesignIndex] === bit) {
        renderBitsDesignItem();
      }
    } catch (error) {
      alert(error.message || "No se pudo subir la imagen.");
    } finally {
      bitsDesignBusy = false;
      fileInput.value = "";
      button.textContent = originalLabel;
      updateBitsDesignNav();
    }
  }

  function renderBitsDesignItem() {
    const count = designBits.length;
    if (!count) {
      currentBitsDesignIndex = 0;
      bitsDesignStage.hidden = true;
      bitsDesignEmpty.hidden = false;
      bitsDesignImage.removeAttribute("src");
      bitsDesignNounControls.replaceChildren();
      updateBitsDesignNav();
      return;
    }

    currentBitsDesignIndex = Math.min(Math.max(currentBitsDesignIndex, 0), count - 1);
    const bit = designBits[currentBitsDesignIndex];
    bitsDesignStage.hidden = false;
    bitsDesignEmpty.hidden = true;
    bitsDesignImage.src = bit.imagen_url;
    bitsDesignImage.alt = bit.palabra;
    bitsDesignNounControls.replaceChildren();

    const group = document.createElement("div");
    group.className = "image-design__noun-control";

    const label = document.createElement("label");
    label.className = "image-design__noun-label";
    const heading = document.createElement("span");
    heading.className = "image-design__noun-heading";
    const caption = document.createElement("span");
    caption.textContent = "Palabra";
    const source = document.createElement("span");
    const isManual = bit.fuente === "manual";
    source.className = `image-design__source image-design__source--${isManual ? "manual" : "ia"}`;
    source.textContent = isManual ? "Subida por ti" : "Generada por IA";
    heading.append(caption, source);
    const input = document.createElement("input");
    input.type = "text";
    input.className = "image-design__noun-input";
    input.maxLength = 60;
    input.autocomplete = "off";
    input.value = bit.palabra;
    label.append(heading, input);

    const actions = document.createElement("div");
    actions.className = "image-design__noun-actions";

    const regenerate = document.createElement("button");
    regenerate.type = "button";
    regenerate.className = "btn btn--accent image-design__regenerate";
    regenerate.textContent = "Regenerar";
    regenerate.addEventListener("click", () => {
      regenerateBitsDesignImage(bit, input, regenerate);
    });

    const fileInput = document.createElement("input");
    fileInput.type = "file";
    fileInput.className = "image-design__file-input";
    fileInput.accept = "image/*";
    fileInput.hidden = true;

    const upload = document.createElement("button");
    upload.type = "button";
    upload.className = "btn btn--ghost image-design__upload";
    upload.textContent = "Subir imagen";
    upload.addEventListener("click", () => {
      fileInput.click();
    });
    fileInput.addEventListener("change", () => {
      uploadBitsDesignImage(bit, input, fileInput, upload);
    });

    actions.append(regenerate, fileInput, upload);
    group.append(label, actions);
    bitsDesignNounControls.appendChild(group);
    updateBitsDesignNav();
  }

  bitsDesignPrevBtn.addEventListener("click", () => {
    if (currentBitsDesignIndex <= 0) return;
    currentBitsDesignIndex -= 1;
    renderBitsDesignItem();
  });

  bitsDesignNextBtn.addEventListener("click", () => {
    if (currentBitsDesignIndex >= designBits.length - 1) return;
    currentBitsDesignIndex += 1;
    renderBitsDesignItem();
  });

  bitsDesignRemoveBtn.addEventListener("click", () => {
    if (!designBits.length) return;
    designBits.splice(currentBitsDesignIndex, 1);
    if (currentBitsDesignIndex >= designBits.length) {
      currentBitsDesignIndex = Math.max(0, designBits.length - 1);
    }
    renderBitsDesignItem();
  });

  bitsDesignBackBtn.addEventListener("click", () => {
    resetBitsDesignState();
    resultOverlay.classList.add("is-open");
    updateDoneButtonState();
  });

  bitsDesignDiscardBtn.addEventListener("click", discardEverything);

  bitsDesignSaveBtn.addEventListener("click", () => {
    if (!designBits.length) {
      alert("No hay bits para guardar.");
      return;
    }
    openClassifyModal(bitsDesignOverlay, () => saveDesignedBitsMaterial());
  });

  bitsDesignTitle.addEventListener("input", () => {
    currentMaterialTitle = bitsDesignTitle.textContent.replace(/\s+/g, " ").trim();
  });

  addSentenceBtn?.addEventListener("click", () => {
    if (currentResultType === "oracion_imagen") {
      appendImageSentenceItem({}, { focus: true });
    } else if (currentResultType === "bits") {
      appendBitsItem({}, { focus: true });
    } else {
      appendSentenceItem("", { focus: true });
    }
    updateDoneButtonState();
  });

  generateMoreSentencesBtn?.addEventListener("click", async () => {
    const existing = getSentencesData();
    const originalLabel = generateMoreSentencesBtn.textContent;
    generateMoreSentencesBtn.disabled = true;
    generateMoreSentencesBtn.textContent = "Generando…";
    try {
      const response = await authorizedFetch("/api/sentences/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          count: 5,
          existing,
          topic: lastSentenceContext.topic || currentMaterialTitle || "",
          grade_level: lastSentenceContext.grade_level || "",
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "No se pudieron generar más oraciones.");
      }
      (data.sentences || []).forEach((sentence) => appendSentenceItem(sentence));
      updateDoneButtonState();
    } catch (error) {
      alert(error.message || "No se pudieron generar más oraciones.");
    } finally {
      generateMoreSentencesBtn.disabled = false;
      generateMoreSentencesBtn.textContent = originalLabel;
    }
  });

  // Question generation: request N questions per type and list them, editable, by category
  const generateQuestionsBtn = document.getElementById("generateQuestionsBtn");
  const questionsResult = document.getElementById("questionsResult");
  const questionCountInputs = Array.from(document.querySelectorAll(".question-row__input"));

  const questionTypeMeta = {};
  questionCountInputs.forEach((input) => {
    const label = input.closest(".question-row").querySelector(".question-row__label");
    questionTypeMeta[input.dataset.questionType] = {
      label: label.textContent,
      color: label.style.color,
    };
  });

  // Serializes the teacher-reviewed question and answer pairs exactly as shown.
  const QUESTION_TYPE_TO_TIPO = {
    literales: "literal",
    inferenciales: "inferencial",
    criticas: "critica",
  };

  function getQuestionsData() {
    const categories = Array.from(questionsResult.querySelectorAll(".questions-result__category"));
    const data = [];

    categories.forEach((category) => {
      const tipo = QUESTION_TYPE_TO_TIPO[category.dataset.type] || category.dataset.type;
      Array.from(category.querySelectorAll(".questions-result__item")).forEach((item) => {
        const question = item.querySelector(".questions-result__question").textContent.trim();
        const expectedAnswer = item.querySelector(".questions-result__answer").textContent.trim();
        if (!question) return;
        data.push({
          tipo,
          pregunta: question,
          respuesta_esperada: expectedAnswer,
          editada_por_docente:
            question !== item.dataset.originalQuestion
            || expectedAnswer !== item.dataset.originalAnswer,
        });
      });
    });

    return data;
  }

  function renderQuestions(questionsByType) {
    questionsResult.innerHTML = "";

    Object.entries(questionsByType).forEach(([type, questions]) => {
      if (!questions.length) return;
      const meta = questionTypeMeta[type] || { label: type, color: "#132a5e" };

      const category = document.createElement("div");
      category.className = "questions-result__category";
      category.dataset.type = type;

      const titleId = `questionsCategory-${type}`;
      const title = document.createElement("div");
      title.className = "questions-result__category-title";
      title.id = titleId;
      title.style.color = meta.color;
      title.textContent = meta.label;
      category.appendChild(title);

      // Semantic list so the questions can be traversed and read aloud (e.g.
      // by a screen reader or TTS) in order, grouped under their category.
      const list = document.createElement("ul");
      list.className = "questions-result__list";
      list.setAttribute("aria-labelledby", titleId);

      questions.forEach((rawQuestion) => {
        const questionText = typeof rawQuestion === "string"
          ? rawQuestion
          : (rawQuestion.pregunta || "");
        const expectedAnswer = typeof rawQuestion === "string"
          ? ""
          : (rawQuestion.respuesta_esperada || "");
        const item = document.createElement("li");
        item.className = "questions-result__item";
        item.dataset.originalQuestion = questionText.trim();
        item.dataset.originalAnswer = expectedAnswer.trim();

        const questionLabel = document.createElement("span");
        questionLabel.className = "questions-result__field-label";
        questionLabel.textContent = "Pregunta";
        const question = document.createElement("div");
        question.className = "questions-result__editable questions-result__question";
        question.contentEditable = "true";
        question.spellcheck = true;
        question.textContent = questionText;

        const answerLabel = document.createElement("span");
        answerLabel.className = "questions-result__field-label";
        answerLabel.textContent = "Respuesta esperada o criterio";
        const answer = document.createElement("div");
        answer.className = "questions-result__editable questions-result__answer";
        answer.contentEditable = "true";
        answer.spellcheck = true;
        answer.dataset.placeholder = "Completa este criterio";
        answer.textContent = expectedAnswer;

        item.append(questionLabel, question, answerLabel, answer);
        list.appendChild(item);
      });

      category.appendChild(list);
      questionsResult.appendChild(category);
    });
  }

  generateQuestionsBtn.addEventListener("click", async () => {
    const counts = {};
    questionCountInputs.forEach((input) => {
      counts[input.dataset.questionType] = Math.max(0, parseInt(input.value, 10) || 0);
    });

    if (!Object.values(counts).some((count) => count > 0)) {
      alert("Indica al menos una pregunta para generar.");
      return;
    }

    const text = resultTranscribedText.textContent.trim();
    if (!text) {
      alert("No hay texto para generar preguntas.");
      return;
    }

    const originalLabel = generateQuestionsBtn.textContent;
    generateQuestionsBtn.disabled = true;
    generateQuestionsBtn.textContent = "Generando...";

    try {
      const response = await authorizedFetch("/api/material/questions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, counts }),
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "No se pudieron generar las preguntas.");
      }

      renderQuestions(data.questions);
      questionsReady = Object.values(data.questions).some((questions) => questions.length > 0);
      updateDoneButtonState();
    } catch (error) {
      alert(error.message || "No se pudieron generar las preguntas.");
    } finally {
      generateQuestionsBtn.disabled = false;
      generateQuestionsBtn.textContent = originalLabel;
    }
  });
});
