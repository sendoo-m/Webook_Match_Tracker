/* Round strip - the clicked chip previously only looked "active" after a
   full page reload, since its hx-get only swaps the round-preview panel
   below it, not the strip itself. Mark it active immediately on click so
   the highlight doesn't lag behind the fetch.

   Delegated on document (not the strip itself) because the dashboard's
   auto-refresh replaces #dashboard-content-root - including the strip -
   via outerHTML every 180s, which would silently detach a listener bound
   directly to it. */
(function () {
    document.addEventListener('click', function (event) {
        const chip = event.target.closest('.round-chip');
        if (!chip) return;
        const strip = chip.closest('.round-scroll-strip');
        if (!strip) return;
        strip.querySelectorAll('.round-chip.is-active').forEach((el) => el.classList.remove('is-active'));
        chip.classList.add('is-active');
    });
})();
