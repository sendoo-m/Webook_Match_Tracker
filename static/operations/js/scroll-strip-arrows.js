/* The two arrow buttons above the Teams strip (club logos) scroll it left
   or right instead of relying on the native scrollbar/trackpad drag. Reused
   by any future ".scroll-strip-arrows" + ".team-scroll-strip" pair inside
   the same ".dashboard-section" card - matched by DOM position, not an id,
   so this works the same way on both the staff and viewer dashboards.

   Delegated on document (not the buttons themselves) for the same reason
   round-strip.js is: the dashboard's auto-refresh replaces
   #dashboard-content-root via outerHTML periodically, which would silently
   detach a listener bound directly to a button that gets replaced. */
(function () {
    document.addEventListener('click', function (event) {
        const button = event.target.closest('.scroll-arrow-btn');
        if (!button) return;
        const section = button.closest('.dashboard-section');
        const strip = section && section.querySelector('.team-scroll-strip');
        if (!strip) return;
        const direction = parseInt(button.dataset.scrollDir, 10) || 1;
        strip.scrollBy({ left: direction * Math.round(strip.clientWidth * 0.8), behavior: 'smooth' });
    });
})();
