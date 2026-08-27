document.addEventListener("DOMContentLoaded", () => {
  const list = document.getElementById("materialList");
  const search = document.getElementById("materialSearch");
  const skillFilter = document.getElementById("materialSkillFilter");
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
    const skill = skillFilter.value;

    cards.forEach((card) => {
      const matchesSkill = skill === "Todas las habilidades" || !card.dataset.skill || card.dataset.skill === skill;
      const matchesQuery = !query || card.dataset.title.includes(query);
      card.classList.toggle("is-hidden", !(matchesSkill && matchesQuery));
    });
  }

  search.addEventListener("input", applyFilters);
  skillFilter.addEventListener("change", applyFilters);

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

  let selectedFile = null;
  let currentMaterialTitle = "";
  let audioFullReady = false;
  let audioSummaryReady = false;
  let questionsReady = false;
  let audioFullBlob = null;
  let audioSummaryBlob = null;

  function resetUploadForm() {
    selectedFile = null;
    uploadTitleInput.value = "";
    uploadFileInput.value = "";
    dropzoneText.textContent = "Arrastra el archivo aquí o haz clic para seleccionar";
    uploadStartBtn.disabled = true;
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
    uploadStartBtn.disabled = false;
  }

  uploadOpenBtn.addEventListener("click", openUpload);
  uploadCancelBtn.addEventListener("click", closeUpload);

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

  uploadStartBtn.addEventListener("click", async () => {
    if (!selectedFile) return;

    currentMaterialTitle = uploadTitleInput.value.trim() || selectedFile.name;

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("title", currentMaterialTitle);

    closeUpload();
    showLoading();

    try {
      const response = await fetch("/api/material/process", {
        method: "POST",
        body: formData,
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "No se pudo procesar el documento.");
      }

      resultTranscribedText.textContent = data.transcribed_text;
      resultSummaryText.textContent = data.summary_text;
      resultSubtitle.textContent = "A partir del documento original · revisa el contenido antes de aprobar";
      resetResultState();

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
    };

    storyGenerateBtn.disabled = true;
    storyGenerateBtn.textContent = "Creando…";
    storyOverlay.classList.remove("is-open");
    showLoading();
    loadingText.textContent = "Creando un cuento con las elecciones del alumno…";

    try {
      const response = await fetch("/api/story/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "No se pudo crear el cuento.");
      }

      currentMaterialTitle = data.title;
      resultTranscribedText.textContent = data.story;
      resultSummaryText.textContent = data.summary;
      resultSubtitle.textContent = "Creado con las elecciones del alumno · la miss puede editarlo antes de aprobar";
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
      formData.append("title", currentMaterialTitle);
      formData.append("transcribed_text", transcribedText);
      formData.append("summary_text", summaryText);
      formData.append("questions_json", JSON.stringify(questionsData));
      formData.append("audio_full", audioFullBlob, "audio.wav");
      formData.append("audio_summary", audioSummaryBlob, "audio_resumen.wav");

      const response = await fetch("/api/material/save", {
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

  function invalidateAudio(audioEl, kind) {
    if (audioEl.src) URL.revokeObjectURL(audioEl.src);
    audioEl.removeAttribute("src");
    audioEl.load();
    if (kind === "full") {
      audioFullReady = false;
      audioFullBlob = null;
    } else {
      audioSummaryReady = false;
      audioSummaryBlob = null;
    }
    updateDoneButtonState();
  }

  resultTranscribedText.addEventListener("input", () => {
    if (audioFullReady) invalidateAudio(resultAudioFull, "full");
  });
  resultSummaryText.addEventListener("input", () => {
    if (audioSummaryReady) invalidateAudio(resultAudioSummary, "summary");
  });

  async function fetchSpeech(text) {
    const response = await fetch("/api/material/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.error || "No se pudo generar el audio.");
    }

    return response.blob();
  }

  async function generateAudio(button, audioEl, getText, onSuccess) {
    const text = (getText() || "").trim();
    if (!text) {
      alert("No hay texto para generar el audio.");
      return;
    }

    const originalLabel = button.textContent;
    button.disabled = true;
    button.textContent = "Generando...";

    try {
      const blob = await fetchSpeech(text);
      if (audioEl.src) {
        URL.revokeObjectURL(audioEl.src);
      }
      audioEl.src = URL.createObjectURL(blob);
      audioEl.play().catch(() => {});
      onSuccess(blob);
    } catch (error) {
      alert(error.message || "No se pudo generar el audio.");
    } finally {
      button.disabled = false;
      button.textContent = originalLabel;
    }
  }

  generateAudioFullBtn.addEventListener("click", () => {
    generateAudio(generateAudioFullBtn, resultAudioFull, () => resultTranscribedText.textContent, (blob) => {
      audioFullBlob = blob;
      audioFullReady = true;
      updateDoneButtonState();
    });
  });

  generateAudioSummaryBtn.addEventListener("click", () => {
    generateAudio(generateAudioSummaryBtn, resultAudioSummary, () => resultSummaryText.textContent, (blob) => {
      audioSummaryBlob = blob;
      audioSummaryReady = true;
      updateDoneButtonState();
    });
  });

  function updateDoneButtonState() {
    resultDoneBtn.disabled = !(audioFullReady && audioSummaryReady && questionsReady);
  }

  function resetResultState() {
    audioFullReady = false;
    audioSummaryReady = false;
    questionsReady = false;
    audioFullBlob = null;
    audioSummaryBlob = null;

    if (resultAudioFull.src) {
      URL.revokeObjectURL(resultAudioFull.src);
    }
    if (resultAudioSummary.src) {
      URL.revokeObjectURL(resultAudioSummary.src);
    }
    resultAudioFull.removeAttribute("src");
    resultAudioSummary.removeAttribute("src");
    questionsResult.innerHTML = "";

    updateDoneButtonState();
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
      const response = await fetch("/api/material/questions", {
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
