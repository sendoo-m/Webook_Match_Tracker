/* Runs before first paint to avoid a flash of the wrong theme. Keep this
   file tiny and dependency-free - it must finish before CSS applies. */
(function () {
    const savedTheme = localStorage.getItem('operations-theme');
    const systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    document.documentElement.dataset.theme = savedTheme || (systemDark ? 'dark' : 'light');
})();
