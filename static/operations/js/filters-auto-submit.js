/* Filter dropdowns submit automatically as soon as one changes, instead of
   requiring an extra click on "Apply Filters". Reused on any page with a
   ".filters" form (Matches, Missing Operational Requirements, ...). */
(function () {
    const form = document.querySelector('.filters');
    if (!form) return;

    form.querySelectorAll('select').forEach((select) => {
        select.addEventListener('change', () => form.submit());
    });
})();
