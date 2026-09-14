/* Control Venue hub (control_panel/venue_control.html) - client-side tab
   switching between the three sections (Matches/Venue Images/Venue
   Categories), all already rendered in the page. Reads ?tab= on load so a
   redirect back here (after saving from a tab's Add/Edit/Toggle form)
   lands on the right tab instead of always resetting to the first one. */
(function () {
    var VALID_TABS = ['matches', 'images', 'categories'];

    function activateTab(name) {
        if (VALID_TABS.indexOf(name) === -1) return;
        document.querySelectorAll('[data-tab-button]').forEach(function (button) {
            button.classList.toggle('is-active', button.dataset.tabButton === name);
        });
        document.querySelectorAll('[data-tab-panel]').forEach(function (panel) {
            panel.hidden = panel.dataset.tabPanel !== name;
        });
    }

    document.querySelectorAll('[data-tab-button]').forEach(function (button) {
        button.addEventListener('click', function () {
            activateTab(button.dataset.tabButton);
        });
    });

    var params = new URLSearchParams(window.location.search);
    var initialTab = params.get('tab');
    if (initialTab) activateTab(initialTab);
})();
