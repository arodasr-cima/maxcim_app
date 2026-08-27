document.addEventListener("DOMContentLoaded", () => {
  const panel = document.getElementById("demoAccess");
  const button = document.getElementById("demoFillButton");
  if (!panel || !button) return;

  button.addEventListener("click", () => {
    const email = document.getElementById("email");
    const password = document.getElementById("password");
    email.value = panel.dataset.email || "";
    password.value = panel.dataset.password || "";
    button.textContent = "Credenciales completadas";
    email.focus();
  });
});
