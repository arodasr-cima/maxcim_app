document.addEventListener("DOMContentLoaded", () => {
  const sidebar = document.getElementById("sidebar");
  const sidebarToggle = document.getElementById("sidebarToggle");
  const profileTrigger = document.getElementById("profileTrigger");
  const profileMenu = document.getElementById("profileMenu");

  sidebarToggle.addEventListener("click", () => {
    sidebar.classList.toggle("is-collapsed");
  });

  profileTrigger.addEventListener("click", (event) => {
    event.stopPropagation();
    profileMenu.classList.toggle("is-open");
  });

  document.addEventListener("click", (event) => {
    if (!profileMenu.contains(event.target) && !profileTrigger.contains(event.target)) {
      profileMenu.classList.remove("is-open");
    }
  });
});
