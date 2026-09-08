document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-period-filter]").forEach((filter) => {
    const yearSelect = filter.querySelector("[data-period-year]");
    const periodSelect = filter.querySelector("[data-period-select]");
    // Los filtros de listados navegan al elegir periodo (?periodo=<id> en la
    // URL). El selector del modal de subir material es un campo de
    // formulario más: solo debe acotar las opciones por año, sin navegar.
    const shouldNavigate = filter.dataset.periodNav !== "false";

    if (!yearSelect || !periodSelect) return;

    const periodOptions = Array.from(periodSelect.options).filter((option) => option.value);

    function filterPeriods() {
      const selectedYear = yearSelect.value;

      periodOptions.forEach((option) => {
        const isVisible = !selectedYear || option.dataset.anio === selectedYear;
        option.hidden = !isVisible;
        option.disabled = !isVisible;
      });
    }

    filterPeriods();

    yearSelect.addEventListener("change", () => {
      periodSelect.value = "";
      filterPeriods();
    });

    if (shouldNavigate) {
      periodSelect.addEventListener("change", () => {
        const url = new URL(window.location.href);

        if (periodSelect.value) {
          url.searchParams.set("periodo", periodSelect.value);
        } else {
          url.searchParams.delete("periodo");
        }

        window.location.assign(url.toString());
      });
    }
  });
});
