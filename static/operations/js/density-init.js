/* Runs before first paint to avoid a flash of the wrong density on the
   SPL viewer dashboard. Keep this file tiny and dependency-free - it must
   finish before CSS applies. Harmless on other pages (nothing reads the
   attribute unless a .viewer-advanced-only element exists). */
(function () {
    const savedDensity = localStorage.getItem('operations-viewer-density');
    document.documentElement.dataset.density = savedDensity || 'simple';
})();
