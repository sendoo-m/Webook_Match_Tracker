/* Expand/collapse controls for the Rounds strip (Hick's Law: 34 chips is a
   lot to scan at once, so it opens collapsed to a small window around the
   active round - see round_window in build_viewer_context). Delegated on
   document since the dashboard's HTMX refresh can replace the whole
   content root wholesale. */
(function () {
    document.addEventListener("click", function (event) {
        const button = event.target.closest("[data-round-expand]");
        if (!button) return;

        const toggles = button.closest(".round-strip-toggles");
        if (!toggles) return;
        const strip = toggles.previousElementSibling;
        if (!strip || !strip.classList.contains("round-scroll-strip")) return;

        const mode = button.dataset.roundExpand;
        strip.dataset.expanded = mode;

        toggles.querySelectorAll("[data-round-expand]").forEach(function (btn) {
            btn.hidden = btn.dataset.roundExpand === mode;
        });
    });
})();
