/* Sidebar collapse/expand toggle - shrinks the sidebar to icons only,
   clicking the same button again brings it back to full size. State
   persists across page loads (see sidebar-init.js). */
(function () {
    const root = document.documentElement;
    const toggleButton = document.getElementById('sidebar-toggle');

    function renderToggleButton() {
        if (!toggleButton) return;
        const collapsed = root.dataset.sidebar === 'collapsed';
        toggleButton.setAttribute('aria-expanded', String(!collapsed));
        toggleButton.setAttribute('aria-label', collapsed ? 'Expand sidebar' : 'Collapse sidebar');
    }

    toggleButton?.addEventListener('click', function () {
        root.dataset.sidebar = root.dataset.sidebar === 'collapsed' ? 'expanded' : 'collapsed';
        localStorage.setItem('operations-sidebar', root.dataset.sidebar);
        renderToggleButton();
    });

    renderToggleButton();
})();
