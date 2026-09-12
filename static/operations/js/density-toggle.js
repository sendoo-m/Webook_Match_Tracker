/* Simple/Advanced view toggle for the SPL viewer dashboard - simple mode
   (the default) hides the heavier sections so the page reads as light at
   a glance; advanced mode brings everything back. Optional: the page
   works the same either way, this just controls how much of it shows. */
(function () {
    const root = document.documentElement;
    const toggleButton = document.getElementById('viewer-density-toggle');
    if (!toggleButton) return;

    function renderToggleButton() {
        const advanced = root.dataset.density === 'advanced';
        toggleButton.setAttribute('aria-pressed', String(advanced));
        toggleButton.querySelector('i').className = advanced ? 'ti ti-layout-grid' : 'ti ti-adjustments';
        toggleButton.querySelector('span').textContent = advanced ? toggleButton.dataset.simpleLabel : toggleButton.dataset.advancedLabel;
    }

    toggleButton.addEventListener('click', function () {
        root.dataset.density = root.dataset.density === 'advanced' ? 'simple' : 'advanced';
        localStorage.setItem('operations-viewer-density', root.dataset.density);
        renderToggleButton();
    });

    renderToggleButton();
})();
