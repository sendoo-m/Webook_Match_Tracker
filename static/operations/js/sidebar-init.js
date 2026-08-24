/* Runs before first paint to avoid a flash of the wrong sidebar width, same
   idea as theme-init.js. Keep this file tiny and dependency-free. */
(function () {
    const saved = localStorage.getItem('operations-sidebar');
    document.documentElement.dataset.sidebar = saved === 'collapsed' ? 'collapsed' : 'expanded';
})();
