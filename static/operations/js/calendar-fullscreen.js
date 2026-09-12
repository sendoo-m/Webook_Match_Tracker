/* Fullscreen/focus toggle for the Match Calendar - uses the native
   Fullscreen API on the calendar card itself, so the sidebar and page
   chrome disappear automatically (the browser only paints the fullscreen
   element), leaving just the grid on screen. Optional: nothing here runs
   unless the user clicks the icon. */
(function () {
    const target = document.getElementById('calendar-fullscreen-target');
    const toggleButton = document.getElementById('calendar-fullscreen-toggle');
    if (!target || !toggleButton) return;

    function isFullscreen() {
        return document.fullscreenElement === target;
    }

    function renderToggleButton() {
        const active = isFullscreen();
        toggleButton.querySelector('i').className = active ? 'ti ti-arrows-minimize' : 'ti ti-arrows-maximize';
        toggleButton.setAttribute('aria-pressed', String(active));
        const label = active ? toggleButton.dataset.exitLabel : toggleButton.dataset.enterLabel;
        toggleButton.title = label;
        toggleButton.setAttribute('aria-label', label);
    }

    toggleButton.addEventListener('click', function () {
        if (isFullscreen()) {
            document.exitFullscreen();
        } else if (target.requestFullscreen) {
            target.requestFullscreen();
        }
    });

    document.addEventListener('fullscreenchange', renderToggleButton);
})();
