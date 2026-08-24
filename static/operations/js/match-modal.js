/* Match quick-view popup - opened from round preview cards, the Alerts &
   Deadlines table, and the Teams strip (all use data-modal-trigger + hx-get
   into #match-modal-body, see modal.js for the shared open/close helper). */
(function () {
    const OVERLAY_ID = 'match-modal-overlay';
    const close = document.getElementById('match-modal-close');

    close?.addEventListener('click', () => OperationsModal.close(OVERLAY_ID));
    document.getElementById(OVERLAY_ID)?.addEventListener('click', function (event) {
        if (event.target.id === OVERLAY_ID) OperationsModal.close(OVERLAY_ID);
    });
})();
