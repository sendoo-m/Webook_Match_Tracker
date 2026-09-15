/* Auto-refresh for the home dashboards (Admin, Coordinator, SPL viewer).
   Each dashboard template marks its own polling root with
   id="dashboard-content-root" and hx-trigger="auto-refresh-tick" instead of
   a hardcoded "every Ns" - this file is the only place that actually owns
   the interval, so the sidebar control below can change it live on every
   dashboard without a page reload.

   Also drives the visible "Next refresh in mm:ss" / "Last updated" lines
   next to the interval picker (2026-09 system review request) - both stay
   hidden entirely while auto-refresh is Off, per that review's own
   explicit rule. */
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
    var countdownEl = document.getElementById('refresh-countdown');
    var lastUpdatedEl = document.getElementById('refresh-last-updated');

    var tickTimerId = null;
    var displayTimerId = null;
    var nextRefreshAt = null;

    function formatCountdown(ms) {
        var totalSeconds = Math.max(0, Math.ceil(ms / 1000));
        var minutes = Math.floor(totalSeconds / 60);
        var seconds = totalSeconds % 60;
        return (minutes < 10 ? '0' : '') + minutes + ':' + (seconds < 10 ? '0' : '') + seconds;
    }

    function updateCountdownDisplay() {
        if (!countdownEl) return;
        if (getStoredSeconds() <= 0 || !nextRefreshAt) {
            countdownEl.hidden = true;
            return;
        }
        countdownEl.hidden = false;
        countdownEl.textContent = countdownEl.dataset.label + ' ' + formatCountdown(nextRefreshAt - Date.now());
    }

    function markLastUpdated() {
        if (!lastUpdatedEl) return;
        var time = new Date().toLocaleTimeString(document.documentElement.lang || undefined, {
            hour: '2-digit',
            minute: '2-digit',
        });
        lastUpdatedEl.hidden = false;
        lastUpdatedEl.textContent = lastUpdatedEl.dataset.label + ' ' + time;
    }

    function doRefresh() {
        if (!window.htmx) return;
        // A hidden tab has no one watching it refresh - skip the request
        // entirely rather than hammering the server for nothing, and pick
        // back up (see visibilitychange below) once someone returns to it.
        if (document.hidden) return;
        if (root) window.htmx.trigger(root, 'auto-refresh-tick');
        if (badgeRoot) window.htmx.trigger(badgeRoot, 'auto-refresh-tick');
        markLastUpdated();
    }

    function stopTimers() {
        if (tickTimerId) {
            clearInterval(tickTimerId);
            tickTimerId = null;
        }
        if (displayTimerId) {
            clearInterval(displayTimerId);
            displayTimerId = null;
        }
        nextRefreshAt = null;
    }

    function startTimer() {
        stopTimers();
        if (!root && !badgeRoot) {
            updateCountdownDisplay();
            return;
        }
        var seconds = getStoredSeconds();
        if (seconds <= 0) {
            updateCountdownDisplay();
            return;
        }

        nextRefreshAt = Date.now() + seconds * 1000;
        tickTimerId = setInterval(function () {
            doRefresh();
            nextRefreshAt = Date.now() + seconds * 1000;
        }, seconds * 1000);
        displayTimerId = setInterval(updateCountdownDisplay, 1000);
        updateCountdownDisplay();
    }

    if (select) {
        select.value = String(getStoredSeconds());
        select.addEventListener('change', function () {
            localStorage.setItem(STORAGE_KEY, select.value);
            startTimer();
        });
    }

    document.addEventListener('visibilitychange', function () {
        // Catch up rather than firing a burst of missed ticks the instant
        // a long-hidden tab regains focus.
        if (!document.hidden && nextRefreshAt && Date.now() >= nextRefreshAt) {
            startTimer();
        }
    });

    startTimer();
})();
