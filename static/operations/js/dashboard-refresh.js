/* Auto-refresh for the home dashboards (Admin, Coordinator, SPL viewer).
   Each dashboard template marks its own polling root with
   id="dashboard-content-root" and hx-trigger="auto-refresh-tick" instead of
   a hardcoded "every Ns" - this file is the only place that actually owns
   the interval, so the sidebar control below can change it live on every
   dashboard without a page reload. */
(function () {
    var STORAGE_KEY = 'operations-refresh-interval-seconds';
    var DEFAULT_SECONDS = 180;

    function getStoredSeconds() {
        var stored = parseInt(localStorage.getItem(STORAGE_KEY), 10);
        return Number.isFinite(stored) && stored >= 0 ? stored : DEFAULT_SECONDS;
    }

    var root = document.getElementById('dashboard-content-root');
    var badgeRoot = document.getElementById('notification-badge-root');
    var select = document.getElementById('refresh-interval-select');
    var timerId = null;

    function startTimer() {
        if (timerId) {
            clearInterval(timerId);
            timerId = null;
        }
        if (!root && !badgeRoot) return;
        var seconds = getStoredSeconds();
        if (seconds <= 0) return;
        timerId = setInterval(function () {
            if (!window.htmx) return;
            if (root) window.htmx.trigger(root, 'auto-refresh-tick');
            if (badgeRoot) window.htmx.trigger(badgeRoot, 'auto-refresh-tick');
        }, seconds * 1000);
    }

    if (select) {
        select.value = String(getStoredSeconds());
        select.addEventListener('change', function () {
            localStorage.setItem(STORAGE_KEY, select.value);
            startTimer();
        });
    }

    startTimer();
})();
