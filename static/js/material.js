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
  const uploadFileInput = document.getElementById("uploadFileInput");
  const dropzone = document.getElementById("dropzone");
  const dropzoneText = document.getElementById("dropzoneText");
  const loadingOverlay = document.getElementById("loadingOverlay");
  const loadingSpinner = document.getElementById("loadingSpinner");
  const loadingText = document.getElementById("loadingText");
  const loadingCloseBtn = document.getElementById("loadingCloseBtn");
  const resultOverlay = document.getElementById("resultOverlay");
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
  const uploadTypeCuentoBtn = document.getElementById("uploadTypeCuentoBtn");
  const uploadTypeOracionBtn = document.getElementById("uploadTypeOracionBtn");
  const resultTranscribedLabel = document.getElementById("resultTranscribedLabel");
  const resultTranscribedBlock = document.getElementById("resultTranscribedBlock");
  const resultSummaryBlock = document.getElementById("resultSummaryBlock");
  const resultSentencesBlock = document.getElementById("resultSentencesBlock");
  const resultSentencesList = document.getElementById("resultSentencesList");
  const resultAudioColumn = document.getElementById("resultAudioColumn");
  const resultQuestionsColumn = document.getElementById("resultQuestionsColumn");

  let selectedFile = null;
  let currentUploadType = "cuento";
  let currentResultType = "cuento";
  let currentMaterialTitle = "";
  let audioFullReady = false;
  let audioSummaryReady = false;
  let questionsReady = false;
  let audioFullBlob = null;
  let audioSummaryBlob = null;
  let currentTargetDurationMinutes = null;
  let audioFullDurationSeconds = null;
  let audioSummaryDurationSeconds = null;

  function setUploadType(type) {
    currentUploadType = type;
    const isOracion = type === "oracion";
    uploadTypeCuentoBtn.classList.toggle("is-active", !isOracion);
    uploadTypeOracionBtn.classList.toggle("is-active", isOracion);
    uploadTypeCuentoBtn.setAttribute("aria-selected", String(!isOracion));
    uploadTypeOracionBtn.setAttribute("aria-selected", String(isOracion));
    uploadTitleInput.placeholder = isOracion ? "Título del material" : "Título del cuento";
    updateUploadButtonState();
  }

  // Ajusta la pantalla de revisión de contenido extraído por IA según el
  // tipo: las oraciones solo revisan el texto, sin resumen, audios ni
  // preguntas (eso es exclusivo de los cuentos).
  function configureResultModalForType(type) {
    currentResultType = type;
    const isOracion = type === "oracion";
    resultTranscribedLabel.textContent = "Texto completo";
    resultTranscribedBlock.hidden = isOracion;
    resultSummaryBlock.hidden = isOracion;
    resultSentencesBlock.hidden = !isOracion;
    resultAudioColumn.hidden = isOracion;
    resultQuestionsColumn.hidden = isOracion;
    resultDoneBtn.textContent = isOracion ? "Aprobar y guardar oraciones" : "Aprobar y guardar";
  }

  function updateUploadButtonState() {
    uploadStartBtn.disabled = !selectedFile;
  }

  function resetUploadForm() {
    selectedFile = null;
    uploadTitleInput.value = "";
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

  function setSelectedFile(file) {
    if (!file) return;
    selectedFile = file;
    dropzoneText.textContent = file.name;
    updateUploadButtonState();
  }

  uploadOpenBtn.addEventListener("click", openUpload);
  uploadCancelBtn.addEventListener("click", closeUpload);
  uploadTypeCuentoBtn.addEventListener("click", () => setUploadType("cuento"));
  uploadTypeOracionBtn.addEventListener("click", () => setUploadType("oracion"));

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

  function showLoading() {
    loadingSpinner.hidden = false;
    loadingText.textContent = "Extrayendo texto y generando resumen con IA...";
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

    const response = await authorizedFetch("/api/material/save", {
      method: "POST",
      body: formData,
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "No se pudieron guardar las oraciones.");
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
    showLoading();
    if (uploadType === "oracion") {
      loadingText.textContent = "Identificando las oraciones con IA...";
    }

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

      if (uploadType === "oracion") {
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

  storyOpenBtn.addEventListener("click", () => {
    storyForm.reset();
    storyOverlay.classList.add("is-open");
  });

  storyCancelBtn.addEventListener("click", () => {
    storyOverlay.classList.remove("is-open");
  });

  storyForm.addEventListener("submit", async (event) => {
    event.preventDefault();
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
    loadingText.textContent = "Creando un cuento con las elecciones del alumno…";

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

  resultDoneBtn.addEventListener("click", async () => {
    if (currentResultType === "oracion") {
      const sentences = getSentencesData();
      if (!sentences.length) {
        alert("No hay oraciones para guardar.");
        return;
      }
      const originalLabel = resultDoneBtn.textContent;
      resultDoneBtn.disabled = true;
      resultDoneBtn.textContent = "Guardando...";
      try {
        await saveSentenceMaterial(sentences);
        resultOverlay.classList.remove("is-open");
        window.location.reload();
      } catch (error) {
        alert(error.message || "No se pudieron guardar las oraciones.");
        resultDoneBtn.disabled = false;
        resultDoneBtn.textContent = originalLabel;
      }
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

    const originalLabel = resultDoneBtn.textContent;
    resultDoneBtn.disabled = true;
    resultDoneBtn.textContent = "Guardando...";

    try {
      const formData = new FormData();
      formData.append("tipo_material", "cuento");
      formData.append("title", currentMaterialTitle);
      formData.append("transcribed_text", transcribedText);
      formData.append("summary_text", summaryText);
      formData.append("questions_json", JSON.stringify(questionsData));
      formData.append("audio_full", audioFullBlob, "audio.wav");
      formData.append("audio_summary", audioSummaryBlob, "audio_resumen.wav");
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

      resultOverlay.classList.remove("is-open");
      window.location.reload();
    } catch (error) {
      alert(error.message || "No se pudo guardar el material.");
    } finally {
      resultDoneBtn.disabled = false;
      resultDoneBtn.textContent = originalLabel;
    }
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

  function updateDoneButtonState() {
    resultDoneBtn.disabled = currentResultType === "oracion"
      ? getSentencesData().length === 0
      : !(audioFullReady && audioSummaryReady && questionsReady);
  }

  function resetResultState() {
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

    updateDoneButtonState();
  }

  // Sentence review: one editable line per sentence the IA identified. The
  // teacher can fix wording or clear a line to drop it, mirroring how the
  // story questions are reviewed before saving.
  function renderSentences(sentences) {
    resultSentencesList.innerHTML = "";
    (sentences || []).forEach((sentence) => {
      const item = document.createElement("li");
      item.className = "sentences-review__item";

      const editable = document.createElement("div");
      editable.className = "sentences-review__editable";
      editable.contentEditable = "true";
      editable.spellcheck = true;
      editable.textContent = typeof sentence === "string" ? sentence : "";
      editable.addEventListener("input", updateDoneButtonState);

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
    });
    updateDoneButtonState();
  }

  function getSentencesData() {
    return Array.from(resultSentencesList.querySelectorAll(".sentences-review__editable"))
      .map((el) => el.textContent.replace(/\s+/g, " ").trim())
      .filter(Boolean);
  }

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
        answer.dataset.placeholder = "La miss debe completar este criterio";
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
