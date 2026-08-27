document.addEventListener("DOMContentLoaded", () => {
  const sidebar = document.getElementById("sidebar");
  const sidebarToggle = document.getElementById("sidebarToggle");
  const profileTrigger = document.getElementById("profileTrigger");
  const profileMenu = document.getElementById("profileMenu");

  if (sidebar && sidebarToggle) {
    sidebarToggle.addEventListener("click", () => {
      const collapsed = sidebar.classList.toggle("is-collapsed");
      sidebarToggle.setAttribute("aria-expanded", String(!collapsed));
    });
  }

  if (profileTrigger && profileMenu) {
    profileTrigger.addEventListener("click", (event) => {
      event.stopPropagation();
      const open = profileMenu.classList.toggle("is-open");
      profileTrigger.setAttribute("aria-expanded", String(open));
    });

    document.addEventListener("click", (event) => {
      if (!profileMenu.contains(event.target) && !profileTrigger.contains(event.target)) {
        profileMenu.classList.remove("is-open");
        profileTrigger.setAttribute("aria-expanded", "false");
      }
    });
  }
});
