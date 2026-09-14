// Opt-in via <input data-filter-target="#some-checkbox-list">: typing
// filters that .checkbox-list's <label> items by visible text, so a long
// list of clubs/sections stays usable without scrolling through all of
// them (Hick's Law) - checked items are never hidden, so a filter can't
// accidentally look like it cleared a selection.
(function () {
    document.addEventListener("input", function (event) {
        var input = event.target;
        if (!input.matches || !input.matches("[data-filter-target]")) {
            return;
        }
        var targetSelector = input.getAttribute("data-filter-target");
        var target = document.querySelector(targetSelector);
        if (!target) {
            return;
        }
        var query = input.value.trim().toLowerCase();
        var labels = target.querySelectorAll("label");
        var visibleCount = 0;
        labels.forEach(function (label) {
            var checkbox = label.querySelector('input[type="checkbox"]');
            var matches = !query || label.textContent.toLowerCase().indexOf(query) !== -1;
            var isChecked = checkbox && checkbox.checked;
            var show = matches || isChecked;
            var li = label.closest("li") || label;
            li.hidden = !show;
            if (show) {
                visibleCount += 1;
            }
        });
        var emptyMessage = target.parentElement.querySelector("[data-filter-empty]");
        if (emptyMessage) {
            emptyMessage.hidden = visibleCount > 0;
        }
    });
})();
