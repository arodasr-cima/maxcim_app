document.addEventListener("DOMContentLoaded", () => {
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";
  const list = document.getElementById("materialList");
  const emptyState = document.getElementById("materialEmpty");
  const search = document.getElementById("materialSearch");
  const skillFilter = document.getElementById("materialSkillFilter");
  const toast = document.getElementById("appToast");
  if (!list || !search || !skillFilter) return;

  let cards = Array.from(list.querySelectorAll(".material-card"));
  let toastTimer = null;

  function showToast(message, type = "success") {
    if (!toast) return;
    window.clearTimeout(toastTimer);
    toast.textContent = message;
    toast.className = `toast toast--${type} is-open`;
    toastTimer = window.setTimeout(() => toast.classList.remove("is-open"), 3200);
  }

  async function responseData(response) {
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || "No se pudo completar la operación.");
    return data;
  }

  function wireCard(card) {
    const header = card.querySelector(".material-card__header");
    const deleteButton = card.querySelector(".material-card__delete");
    header?.addEventListener("click", () => {
      const opening = !card.classList.contains("is-open");
      cards.forEach((item) => {
        item.classList.remove("is-open");
        item.querySelector(".material-card__header")?.setAttribute("aria-expanded", "false");
      });
      if (opening) {
        card.classList.add("is-open");
        header.setAttribute("aria-expanded", "true");
      }
    });
    deleteButton?.addEventListener("click", async () => {
      if (!window.confirm("¿Eliminar este material y todos sus archivos?")) return;
      deleteButton.disabled = true;
      try {
        const response = await fetch(deleteButton.dataset.deleteUrl, {
          method: "DELETE",
          headers: { "X-CSRFToken": csrfToken },
        });
        if (!response.ok) await responseData(response);
        card.remove();
        cards = cards.filter((item) => item !== card);
        applyFilters();
        showToast("Material eliminado correctamente.");
      } catch (error) {
        deleteButton.disabled = false;
        showToast(error.message, "error");
      }
    });
  }

  cards.forEach(wireCard);

  function applyFilters() {
    const query = search.value.trim().toLocaleLowerCase("es");
    const skill = skillFilter.value;
    let visible = 0;
    cards.forEach((card) => {
      const matchesSkill = skill === "Todas las habilidades" || card.dataset.skill === skill;
      const matchesQuery = !query || (card.dataset.title || "").includes(query);
      const show = matchesSkill && matchesQuery;
      card.classList.toggle("is-hidden", !show);
      if (show) visible += 1;
    });
    if (emptyState) {
      emptyState.hidden = visible !== 0;
      const title = emptyState.querySelector("h2");
      const description = emptyState.querySelector("p");
      if (title && description) {
        title.textContent = cards.length ? "Sin coincidencias" : "Aún no hay materiales";
        description.textContent = cards.length
          ? "Prueba con otro texto o selecciona una habilidad diferente."
          : "Agrega una lectura para demostrar el flujo completo de MAXCIM.";
      }
    }
  }

  search.addEventListener("input", applyFilters);
  skillFilter.addEventListener("change", applyFilters);
  applyFilters();

  const uploadOpenBtn = document.getElementById("uploadOpenBtn");
  const uploadOverlay = document.getElementById("uploadOverlay");
  const uploadCancelBtn = document.getElementById("uploadCancelBtn");
  const uploadStartBtn = document.getElementById("uploadStartBtn");
  const uploadTitleInput = document.getElementById("uploadTitleInput");
  const uploadSkillInput = document.getElementById("uploadSkillInput");
  const uploadFileInput = document.getElementById("uploadFileInput");
  const dropzone = document.getElementById("dropzone");
  const dropzoneText = document.getElementById("dropzoneText");
  const loadingOverlay = document.getElementById("loadingOverlay");
  const loadingSpinner = document.getElementById("loadingSpinner");
  const loadingText = document.getElementById("loadingText");
  const loadingCloseBtn = document.getElementById("loadingCloseBtn");
  const resultOverlay = document.getElementById("resultOverlay");
  const resultCancelBtn = document.getElementById("resultCancelBtn");
  const resultDoneBtn = document.getElementById("resultDoneBtn");
  const resultTranscribedText = document.getElementById("resultTranscribedText");
  const resultSummaryText = document.getElementById("resultSummaryText");
  const generateAudioFullBtn = document.getElementById("generateAudioFullBtn");
  const generateAudioSummaryBtn = document.getElementById("generateAudioSummaryBtn");
  const resultAudioFull = document.getElementById("resultAudioFull");
  const resultAudioSummary = document.getElementById("resultAudioSummary");
  const generateQuestionsBtn = document.getElementById("generateQuestionsBtn");
  const questionsResult = document.getElementById("questionsResult");
  const questionCountInputs = Array.from(document.querySelectorAll(".question-row__input"));

  let selectedFile = null;
  let currentMaterialTitle = "";
  let audioFullBlob = null;
  let audioSummaryBlob = null;
  let questionsReady = false;

  function setOverlay(overlay, open) {
    overlay?.classList.toggle("is-open", open);
    overlay?.setAttribute("aria-hidden", String(!open));
    document.body.classList.toggle("modal-open", Boolean(document.querySelector(".overlay.is-open")));
  }

  function resetUploadForm() {
    selectedFile = null;
    uploadTitleInput.value = "";
    uploadFileInput.value = "";
    dropzoneText.textContent = "Arrastra el archivo aquí o haz clic para seleccionar";
    uploadStartBtn.disabled = true;
  }

  function setSelectedFile(file) {
    if (!file) return;
    const extension = file.name.split(".").pop().toLowerCase();
    if (!["txt", "pdf", "docx"].includes(extension)) {
      showToast("Selecciona un archivo TXT, PDF o DOCX.", "error");
      return;
    }
    if (file.size > 16 * 1024 * 1024) {
      showToast("El archivo supera el límite de 16 MB.", "error");
      return;
    }
    selectedFile = file;
    dropzoneText.textContent = file.name;
    uploadStartBtn.disabled = false;
    if (!uploadTitleInput.value.trim()) uploadTitleInput.value = file.name.replace(/\.[^.]+$/, "");
  }

  uploadOpenBtn?.addEventListener("click", () => {
    resetUploadForm();
    setOverlay(uploadOverlay, true);
    uploadTitleInput.focus();
  });
  uploadCancelBtn?.addEventListener("click", () => setOverlay(uploadOverlay, false));
  dropzone?.addEventListener("dragover", (event) => {
    event.preventDefault();
    dropzone.classList.add("is-dragover");
  });
  dropzone?.addEventListener("dragleave", () => dropzone.classList.remove("is-dragover"));
  dropzone?.addEventListener("drop", (event) => {
    event.preventDefault();
    dropzone.classList.remove("is-dragover");
    setSelectedFile(event.dataTransfer.files?.[0]);
  });
  uploadFileInput?.addEventListener("change", () => setSelectedFile(uploadFileInput.files?.[0]));

  function resetResultState() {
    audioFullBlob = null;
    audioSummaryBlob = null;
    questionsReady = false;
    [resultAudioFull, resultAudioSummary].forEach((audio) => {
      if (audio.src) URL.revokeObjectURL(audio.src);
      audio.removeAttribute("src");
      audio.load();
    });
    questionsResult.innerHTML = "";
    updateDoneButtonState();
  }

  function updateDoneButtonState() {
    resultDoneBtn.disabled = !(audioFullBlob && audioSummaryBlob && questionsReady);
  }

  function showLoading() {
    loadingSpinner.hidden = false;
    loadingText.textContent = "Extrayendo texto y generando resumen...";
    loadingCloseBtn.hidden = true;
    setOverlay(loadingOverlay, true);
  }

  function showLoadingError(message) {
    loadingSpinner.hidden = true;
    loadingText.textContent = message;
    loadingCloseBtn.hidden = false;
  }

  uploadStartBtn?.addEventListener("click", async () => {
    if (!selectedFile) return;
    currentMaterialTitle = uploadTitleInput.value.trim();
    if (!currentMaterialTitle) {
      showToast("Escribe un título para el material.", "error");
      uploadTitleInput.focus();
      return;
    }
    const formData = new FormData();
    formData.append("file", selectedFile);
    setOverlay(uploadOverlay, false);
    showLoading();
    try {
      const response = await fetch("/api/material/process", {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken },
        body: formData,
      });
      const data = await responseData(response);
      resultTranscribedText.textContent = data.transcribed_text;
      resultSummaryText.textContent = data.summary_text;
      resetResultState();
      setOverlay(loadingOverlay, false);
      setOverlay(resultOverlay, true);
      if (data.demo_mode) showToast("Documento procesado en modo demostración.");
    } catch (error) {
      showLoadingError(error.message);
    }
  });

  loadingCloseBtn?.addEventListener("click", () => setOverlay(loadingOverlay, false));
  resultCancelBtn?.addEventListener("click", () => {
    resetResultState();
    setOverlay(resultOverlay, false);
  });

  async function fetchSpeech(text) {
    const response = await fetch("/api/material/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
      body: JSON.stringify({ text }),
    });
    if (!response.ok) await responseData(response);
    return response.blob();
  }

  async function createAudio(button, audio, text, onReady) {
    if (!text.trim()) return showToast("No hay texto para generar audio.", "error");
    const original = button.textContent;
    button.disabled = true;
    button.textContent = "Generando...";
    try {
      const blob = await fetchSpeech(text);
      if (audio.src) URL.revokeObjectURL(audio.src);
      audio.src = URL.createObjectURL(blob);
      onReady(blob);
      audio.play().catch(() => {});
      updateDoneButtonState();
      showToast("Audio generado correctamente.");
    } catch (error) {
      showToast(error.message, "error");
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  }

  generateAudioFullBtn?.addEventListener("click", () => createAudio(
    generateAudioFullBtn,
    resultAudioFull,
    resultTranscribedText.textContent,
    (blob) => { audioFullBlob = blob; },
  ));
  generateAudioSummaryBtn?.addEventListener("click", () => createAudio(
    generateAudioSummaryBtn,
    resultAudioSummary,
    resultSummaryText.textContent,
    (blob) => { audioSummaryBlob = blob; },
  ));

  const typeLabels = { literales: "Literales", inferenciales: "Inferenciales", criticas: "Críticas" };
  const storageTypes = { literales: "literal", inferenciales: "inferencial", criticas: "critica" };

  function renderQuestions(groups) {
    questionsResult.innerHTML = "";
    Object.entries(groups).forEach(([type, questions]) => {
      if (!questions.length) return;
      const category = document.createElement("section");
      category.className = "questions-result__category";
      category.dataset.type = type;
      const title = document.createElement("h4");
      title.className = "questions-result__category-title";
      title.textContent = typeLabels[type] || type;
      const questionList = document.createElement("ul");
      questionList.className = "questions-result__list";
      questions.forEach((question) => {
        const item = document.createElement("li");
        item.className = "questions-result__item";
        item.contentEditable = "true";
        item.spellcheck = true;
        item.textContent = question;
        questionList.appendChild(item);
      });
      category.append(title, questionList);
      questionsResult.appendChild(category);
    });
  }

  function serializedQuestions() {
    return Array.from(questionsResult.querySelectorAll(".questions-result__category")).flatMap((category) =>
      Array.from(category.querySelectorAll(".questions-result__item"))
        .map((item) => item.textContent.trim())
        .filter(Boolean)
        .map((question) => ({ tipo: storageTypes[category.dataset.type], pregunta: question })),
    );
  }

  generateQuestionsBtn?.addEventListener("click", async () => {
    const counts = Object.fromEntries(questionCountInputs.map((input) => [
      input.dataset.questionType,
      Math.max(0, Math.min(15, Number.parseInt(input.value, 10) || 0)),
    ]));
    if (!Object.values(counts).some(Boolean)) return showToast("Indica al menos una pregunta.", "error");
    const original = generateQuestionsBtn.textContent;
    generateQuestionsBtn.disabled = true;
    generateQuestionsBtn.textContent = "Generando...";
    try {
      const response = await fetch("/api/material/questions", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
        body: JSON.stringify({ text: resultTranscribedText.textContent.trim(), counts }),
      });
      const data = await responseData(response);
      renderQuestions(data.questions);
      questionsReady = serializedQuestions().length > 0;
      updateDoneButtonState();
      showToast("Preguntas generadas correctamente.");
    } catch (error) {
      showToast(error.message, "error");
    } finally {
      generateQuestionsBtn.disabled = false;
      generateQuestionsBtn.textContent = original;
    }
  });

  resultDoneBtn?.addEventListener("click", async () => {
    const formData = new FormData();
    formData.append("title", currentMaterialTitle);
    formData.append("skill", uploadSkillInput.value);
    formData.append("transcribed_text", resultTranscribedText.textContent.trim());
    formData.append("summary_text", resultSummaryText.textContent.trim());
    formData.append("questions_json", JSON.stringify(serializedQuestions()));
    formData.append("audio_full", audioFullBlob, "audio.wav");
    formData.append("audio_summary", audioSummaryBlob, "audio_resumen.wav");
    resultDoneBtn.disabled = true;
    resultDoneBtn.textContent = "Guardando...";
    try {
      const response = await fetch("/api/material/save", {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken },
        body: formData,
      });
      await responseData(response);
      showToast("Material guardado correctamente.");
      window.setTimeout(() => window.location.reload(), 500);
    } catch (error) {
      resultDoneBtn.textContent = "Guardar material";
      updateDoneButtonState();
      showToast(error.message, "error");
    }
  });
});
