/* System message toasts (#toast-container) had no removal logic at all -
   they only went away on the next full page load, which is why they could
   sit on screen indefinitely. This gives every toast a fixed lifetime: it
   fades out and is removed from the DOM on its own. */
(function () {
    var DISPLAY_MS = 5000;
    var FADE_MS = 300;

    function armToast(toast) {
        if (toast.dataset.dismissArmed) return;
        toast.dataset.dismissArmed = 'true';
        setTimeout(function () {
            toast.classList.add('page-toast-hide');
            setTimeout(function () {
                toast.remove();
            }, FADE_MS);
        }, DISPLAY_MS);
    }

    document.querySelectorAll('.page-toast').forEach(armToast);

    document.body.addEventListener('htmx:afterSettle', function () {
        document.querySelectorAll('.page-toast').forEach(armToast);
    });
})();
