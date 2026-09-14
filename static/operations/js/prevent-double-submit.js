// Opt-in via <form data-prevent-double-submit>: disables the submit
// button(s) the instant the form is submitted, so a slow save request
// (or an impatient double-click) never fires the same POST twice. Does
// not interfere with the browser's own required-field validation, which
// already runs before the "submit" event fires.
(function () {
    document.addEventListener("submit", function (event) {
        var form = event.target;
        if (!form.matches || !form.matches("[data-prevent-double-submit]")) {
            return;
        }
        var buttons = form.querySelectorAll('button[type="submit"], input[type="submit"]');
        buttons.forEach(function (button) {
            if (button.disabled) {
                return;
            }
            button.disabled = true;
            var savingLabel = button.getAttribute("data-saving-label");
            if (savingLabel) {
                button.dataset.originalLabel = button.innerHTML;
                button.innerHTML = savingLabel;
            }
        });
    });
})();
