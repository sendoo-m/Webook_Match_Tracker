/* SPL Approvals page: generic close-handling for the per-plan approve/reject
   confirmation modals (one pair per match, see spl_approvals.html) - too
   many to wire individually like feedback-modal.js does for its one modal,
   so this delegates from the document instead. Opening is still done
   inline via OperationsModal.open('...') on each trigger button. */
(function () {
    document.addEventListener('click', function (event) {
        var closeTrigger = event.target.closest('[data-modal-close]');
        if (closeTrigger) {
            window.OperationsModal.close(closeTrigger.dataset.modalClose);
            return;
        }
        // Click on the dimmed backdrop itself (not its content) also closes.
        if (event.target.classList.contains('modal-overlay')) {
            window.OperationsModal.close(event.target.id);
        }
    });
})();
