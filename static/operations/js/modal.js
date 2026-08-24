/* Generic animated modal open/close, shared by any .modal-overlay on the
   page (feedback modal, match quick-view modal, ...). is-open toggles
   display:flex, is-animated (added a frame later so the transition
   actually plays) drives the fade + scale-in transition. */
window.OperationsModal = (function () {
    const ANIMATION_MS = 180;

    function open(overlayId) {
        const overlay = document.getElementById(overlayId);
        if (!overlay) return;
        overlay.classList.add('is-open');
        requestAnimationFrame(() => {
            requestAnimationFrame(() => overlay.classList.add('is-animated'));
        });
    }

    function close(overlayId) {
        const overlay = document.getElementById(overlayId);
        if (!overlay) return;
        overlay.classList.remove('is-animated');
        setTimeout(() => overlay.classList.remove('is-open'), ANIMATION_MS);
    }

    // Elements marked data-modal-trigger open/load via onclick + hx-get
    // attributes already, but only listen for real "click" events - this
    // lets them also respond to Enter/Space when focused via keyboard.
    document.addEventListener('keydown', function (event) {
        if (event.key !== 'Enter' && event.key !== ' ') return;
        const trigger = event.target.closest('[data-modal-trigger]');
        if (!trigger) return;
        event.preventDefault();
        trigger.click();
    });

    return { open, close };
})();
