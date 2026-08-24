/* Feedback popup modal - open/close wired through the shared OperationsModal
   helper (see modal.js). */
(function () {
    const feedbackButton = document.querySelector('.fab-feedback');
    const feedbackClose = document.getElementById('feedback-modal-close');
    const OVERLAY_ID = 'feedback-modal-overlay';

    function setFeedbackModal(open) {
        if (!feedbackButton) return;
        if (open) {
            OperationsModal.open(OVERLAY_ID);
        } else {
            OperationsModal.close(OVERLAY_ID);
        }
        feedbackButton.setAttribute('aria-expanded', String(open));
    }

    feedbackButton?.addEventListener('click', () => setFeedbackModal(true));
    feedbackClose?.addEventListener('click', () => setFeedbackModal(false));
    document.getElementById(OVERLAY_ID)?.addEventListener('click', function (event) {
        if (event.target.id === OVERLAY_ID) setFeedbackModal(false);
    });

    // The feedback_modal_success.html partial closes the modal from inside
    // via this same global, after a successful HTMX submit.
    window.closeFeedbackModal = () => setFeedbackModal(false);
})();
