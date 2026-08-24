/* Dark/light mode toggle button in the sidebar footer. */
(function () {
    const root = document.documentElement;
    const themeButton = document.getElementById('theme-toggle');

    function renderThemeButton() {
        if (!themeButton) return;
        const isDark = root.dataset.theme === 'dark';
        themeButton.querySelector('i').className = isDark ? 'ti ti-sun' : 'ti ti-moon';
        themeButton.querySelector('span').textContent = isDark ? 'Light mode' : 'Dark mode';
    }

    themeButton?.addEventListener('click', function () {
        root.dataset.theme = root.dataset.theme === 'dark' ? 'light' : 'dark';
        localStorage.setItem('operations-theme', root.dataset.theme);
        renderThemeButton();
    });

    renderThemeButton();
})();
