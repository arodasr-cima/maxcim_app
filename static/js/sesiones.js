document.addEventListener("DOMContentLoaded", () => {
  const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || "";
  const config = window.MAXCIM_SESSION_CONFIG || {};
  const form = document.getElementById("sessionForm");
  const classroom = document.getElementById("sessionClassroom");
  const material = document.getElementById("sessionMaterial");
  const objective = document.getElementById("sessionObjective");
  const startButton = document.getElementById("startSessionBtn");
  const livePanel = document.getElementById("liveSession");
  const liveTitle = document.getElementById("liveSessionTitle");
  const liveStatus = document.getElementById("liveSessionStatus");
  const studentInitials = document.getElementById("studentInitials");
  const studentName = document.getElementById("studentName");
  const studentMeta = document.getElementById("studentMeta");
  const recognitionStep = document.getElementById("recognitionStep");
  const conversationStep = document.getElementById("conversationStep");
  const evaluationStep = document.getElementById("evaluationStep");
  const finishButton = document.getElementById("finishSessionBtn");
  const simulateFaceButton = document.getElementById("simulateFaceBtn");
  const simulateTurnsButton = document.getElementById("simulateTurnsBtn");
  const evaluationPanel = document.getElementById("evaluationPanel");
  const approveButton = document.getElementById("approveEvaluationBtn");
  const evaluationReviewBadge = document.getElementById("evaluationReviewBadge");
  const teacherFeedback = document.getElementById("teacherFeedback");
  const toast = document.getElementById("sessionToast");

  let activeSessionUuid = null;
  let pollTimer = null;

  function showToast(message, isError = false) {
    toast.textContent = message;
    toast.classList.toggle("toast--error", isError);
    toast.classList.add("is-visible");
    window.setTimeout(() => toast.classList.remove("is-visible"), 3500);
  }

  async function requestJson(url, options = {}) {
    const headers = new Headers(options.headers || {});
    if ((options.method || "GET").toUpperCase() !== "GET") {
      headers.set("X-CSRF-Token", csrfToken);
    }
    const response = await fetch(url, { ...options, headers });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.error || "No se pudo completar la operación.");
    }
    return data;
  }

  function initials(name) {
    return (name || "?")
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0].toUpperCase())
      .join("") || "?";
  }

  function setStep(element, state) {
    element.classList.toggle("is-active", state === "active");
    element.classList.toggle("is-complete", state === "complete");
  }

  function renderSession(session) {
    livePanel.hidden = false;
    activeSessionUuid = session.uuid;

    if (session.status === "esperando_identificacion") {
      evaluationPanel.hidden = true;
      liveTitle.textContent = "Esperando identificación";
      liveStatus.textContent = "Esperando rostro";
      liveStatus.dataset.state = "waiting";
      studentInitials.textContent = "?";
      studentName.textContent = "MAXCIM está observando la cámara…";
      studentMeta.textContent = "La actividad comenzará al confirmar la identidad.";
      setStep(recognitionStep, "active");
      setStep(conversationStep, "pending");
      setStep(evaluationStep, "pending");
      finishButton.disabled = true;
      if (simulateTurnsButton) simulateTurnsButton.disabled = true;
    } else if (session.status === "activa") {
      evaluationPanel.hidden = true;
      liveTitle.textContent = "Interacción oral activa";
      liveStatus.textContent = "Conversando";
      liveStatus.dataset.state = "active";
      studentInitials.textContent = initials(session.student_name);
      studentName.textContent = session.student_name || `Alumno ${session.student_id}`;
      const confidence = session.recognition_confidence == null
        ? ""
        : ` · coincidencia ${(session.recognition_confidence * 100).toFixed(0)}%`;
      studentMeta.textContent = `ID institucional ${session.student_id}${confidence}`;
      setStep(recognitionStep, "complete");
      setStep(conversationStep, "active");
      setStep(evaluationStep, "pending");
      finishButton.disabled = false;
      if (simulateTurnsButton) simulateTurnsButton.disabled = false;
    } else {
      liveTitle.textContent = "Sesión finalizada";
      liveStatus.textContent = session.status === "evaluacion_aprobada" ? "Aprobada" : "Por revisar";
      liveStatus.dataset.state = "complete";
      studentInitials.textContent = initials(session.student_name);
      studentName.textContent = session.student_name || `Alumno ${session.student_id || "sin identificar"}`;
      studentMeta.textContent = "La conversación terminó y sus resultados quedaron registrados.";
      setStep(recognitionStep, "complete");
      setStep(conversationStep, "complete");
      setStep(evaluationStep, session.status === "evaluacion_aprobada" ? "complete" : "active");
      finishButton.disabled = true;
      if (simulateTurnsButton) simulateTurnsButton.disabled = true;
      if (session.evaluation) {
        renderEvaluation(session.evaluation);
      } else {
        evaluationPanel.hidden = true;
      }
    }
  }

  function numericValue(value) {
    return value == null ? "" : Math.round(Number(value));
  }

  function renderEvaluation(evaluation) {
    evaluationPanel.hidden = false;
    document.getElementById("participationScore").value = numericValue(evaluation.participation_percentage);
    document.getElementById("comprehensionScore").value = numericValue(evaluation.comprehension_percentage);
    document.getElementById("oralScore").value = numericValue(evaluation.oral_interaction_percentage);
    document.getElementById("overallScore").value = numericValue(evaluation.overall_percentage);
    teacherFeedback.value = evaluation.teacher_feedback || "";
    const isApproved = evaluation.status === "aprobada";
    evaluationReviewBadge.textContent = isApproved ? "Aprobada por la docente" : "Pendiente de la docente";
    evaluationReviewBadge.classList.toggle("review-badge--approved", isApproved);
    approveButton.disabled = false;
    approveButton.textContent = isApproved ? "Guardar cambios" : "Aprobar evaluación";
    document.getElementById("evaluationSummary").textContent = evaluation.ai_summary
      || "Las métricas objetivas están disponibles; la evaluación cualitativa de IA está pendiente.";

    const criteriaContainer = document.getElementById("evaluationCriteria");
    criteriaContainer.innerHTML = "";
    const bundle = evaluation.criteria || {};
    const criteria = bundle.criterios || {};
    Object.values(criteria).forEach((criterion) => {
      const item = document.createElement("article");
      item.className = "criterion-card";
      const score = criterion.puntuacion == null ? "Sin evidencia" : `${Math.round(criterion.puntuacion)}%`;
      const heading = document.createElement("div");
      const name = document.createElement("strong");
      const scoreLabel = document.createElement("span");
      const evidence = document.createElement("p");
      name.textContent = criterion.nombre || "Criterio";
      scoreLabel.textContent = score;
      evidence.textContent = criterion.evidencia || "No se registró evidencia suficiente.";
      heading.append(name, scoreLabel);
      item.append(heading, evidence);
      criteriaContainer.appendChild(item);
    });

    if (bundle.recomendacion_docente) {
      const recommendation = document.createElement("article");
      recommendation.className = "criterion-card criterion-card--recommendation";
      const heading = document.createElement("div");
      const title = document.createElement("strong");
      const text = document.createElement("p");
      title.textContent = "Recomendación para la docente";
      text.textContent = bundle.recomendacion_docente;
      heading.appendChild(title);
      recommendation.append(heading, text);
      criteriaContainer.appendChild(recommendation);
    }
    evaluationPanel.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function refreshSession() {
    if (!activeSessionUuid) return;
    try {
      const session = await requestJson(`/api/interactions/sessions/${activeSessionUuid}`);
      renderSession(session);
      if (!["esperando_identificacion", "activa"].includes(session.status)) {
        window.clearInterval(pollTimer);
        pollTimer = null;
      }
    } catch (error) {
      window.clearInterval(pollTimer);
      pollTimer = null;
      showToast(error.message, true);
    }
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    startButton.disabled = true;
    startButton.textContent = "Preparando…";
    try {
      const session = await requestJson("/api/interactions/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          classroom_id: classroom.value,
          material_id: material.value || null,
          objective: objective.value.trim(),
        }),
      });
      renderSession(session);
      livePanel.scrollIntoView({ behavior: "smooth", block: "center" });
      if (pollTimer) window.clearInterval(pollTimer);
      pollTimer = window.setInterval(refreshSession, 2500);
      showToast("Sesión preparada. MAXCIM ya puede identificar al alumno.");
    } catch (error) {
      showToast(error.message, true);
    } finally {
      startButton.disabled = false;
      startButton.textContent = "Iniciar reconocimiento";
    }
  });

  if (config.demoMode && simulateFaceButton) {
    simulateFaceButton.addEventListener("click", async () => {
      if (!activeSessionUuid) return;
      simulateFaceButton.disabled = true;
      try {
        const result = await requestJson("/api/integrations/face-recognition/events", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            session_uuid: activeSessionUuid,
            person_id: "ALU-DEMO-1042",
            confidence: 0.97,
          }),
        });
        renderSession(result.session);
        showToast("Rostro de prueba identificado y sesión vinculada.");
      } catch (error) {
        showToast(error.message, true);
      } finally {
        simulateFaceButton.disabled = false;
      }
    });
  }

  async function addDemoTurn(payload) {
    return requestJson(`/api/interactions/sessions/${activeSessionUuid}/turns`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  }

  if (config.demoMode && simulateTurnsButton) {
    simulateTurnsButton.addEventListener("click", async () => {
      if (!activeSessionUuid) return;
      simulateTurnsButton.disabled = true;
      try {
        await addDemoTurn({
          speaker: "MAXCIM",
          transcript: "¿Qué hizo el personaje para ayudar a sus amigos?",
        });
        await addDemoTurn({
          speaker: "ALUMNO",
          transcript: "Escuchó sus ideas y propuso que resolvieran el reto juntos.",
          response_time_ms: 4200,
          is_correct: true,
          needed_help: false,
        });
        await addDemoTurn({
          speaker: "MAXCIM",
          transcript: "¿Por qué es importante escuchar antes de responder?",
        });
        await addDemoTurn({
          speaker: "ALUMNO",
          transcript: "Porque así entendemos lo que la otra persona quiere decir.",
          response_time_ms: 5100,
          is_correct: true,
          needed_help: false,
        });
        showToast("Conversación de prueba registrada.");
      } catch (error) {
        showToast(error.message, true);
      } finally {
        simulateTurnsButton.disabled = false;
      }
    });
  }

  finishButton.addEventListener("click", async () => {
    if (!activeSessionUuid) return;
    finishButton.disabled = true;
    finishButton.textContent = "Evaluando…";
    try {
      const session = await requestJson(`/api/interactions/sessions/${activeSessionUuid}/complete`, {
        method: "POST",
      });
      renderSession(session);
      showToast("Evaluación preparada para revisión docente.");
    } catch (error) {
      finishButton.disabled = false;
      showToast(error.message, true);
    } finally {
      finishButton.textContent = "Finalizar y evaluar";
    }
  });

  approveButton.addEventListener("click", async () => {
    if (!activeSessionUuid) return;
    approveButton.disabled = true;
    approveButton.textContent = "Guardando…";
    try {
      await requestJson(`/api/interactions/sessions/${activeSessionUuid}/evaluation`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          participation_percentage: document.getElementById("participationScore").value,
          comprehension_percentage: document.getElementById("comprehensionScore").value,
          oral_interaction_percentage: document.getElementById("oralScore").value || null,
          overall_percentage: document.getElementById("overallScore").value || null,
          teacher_feedback: teacherFeedback.value.trim(),
        }),
      });
      showToast("Evaluación aprobada correctamente.");
      window.setTimeout(() => window.location.reload(), 700);
    } catch (error) {
      approveButton.disabled = false;
      approveButton.textContent = "Aprobar evaluación";
      showToast(error.message, true);
    }
  });

  document.querySelectorAll(".session-review-btn").forEach((button) => {
    button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        const session = await requestJson(`/api/interactions/sessions/${button.dataset.sessionUuid}`);
        renderSession(session);
        if (["esperando_identificacion", "activa"].includes(session.status)) {
          if (pollTimer) window.clearInterval(pollTimer);
          pollTimer = window.setInterval(refreshSession, 2500);
          livePanel.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      } catch (error) {
        showToast(error.message, true);
      } finally {
        button.disabled = false;
      }
    });
  });
});
