/* Filters the Teams strip's chips as you type, instead of scanning a flat
   list of 18 - delegated on document since the dashboard's HTMX refresh
   can replace the whole content root wholesale. */
(function () {
    document.addEventListener("input", function (event) {
        const input = event.target.closest("[data-team-search]");
        if (!input) return;

        const strip = document.querySelector(input.dataset.teamSearch);
        if (!strip) return;

        const needle = input.value.trim().toLowerCase();
        let anyVisible = false;
        strip.querySelectorAll(".team-chip").forEach(function (chip) {
            const matches = !needle || chip.dataset.searchText.indexOf(needle) !== -1;
            chip.hidden = !matches;
            if (matches) anyVisible = true;
        });

        const emptyState = strip.parentElement.querySelector(".team-search-empty");
        if (emptyState) emptyState.hidden = anyVisible;
    });
})();
