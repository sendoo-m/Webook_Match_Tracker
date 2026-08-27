/* Filter dropdowns submit automatically as soon as one changes, instead of
   requiring an extra click on "Apply Filters". Opt in per-form with
   data-autosubmit (not every ".filters"-styled form wants this - e.g. an
   export toolbar's dropdowns shouldn't trigger a download on change). */
(function () {
    document.querySelectorAll('form[data-autosubmit]').forEach((form) => {
        form.querySelectorAll('select').forEach((select) => {
            select.addEventListener('change', () => form.submit());
        });
    });
})();
