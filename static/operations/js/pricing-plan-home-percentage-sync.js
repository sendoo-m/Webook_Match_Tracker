// Two jobs on the pricing-plan upload page (see clubs/templates/operations/
// club_pricing_plan_upload.html):
//
// 1. Home/Away are shown as two boxes so a club can read its own split at a
//    glance, but only Home is a real, submitted form field - Away is a
//    read-only mirror kept at (100 - Home), never posted on its own.
// 2. The Home field is asked once but is required by two independent
//    <form>s on the page (manual entry and Excel import) - every
//    [data-home-percentage-mirror] hidden input is kept in sync with it so
//    either form submits the same value without showing the field twice.
(function () {
    var homeField = document.getElementById("id_home_percentage");
    if (!homeField) {
        return;
    }

    var awayDisplays = document.querySelectorAll("[data-away-percentage-display]");

    function syncFromHome() {
        var home = parseInt(homeField.value, 10);
        var away = isNaN(home) ? "" : Math.max(0, Math.min(100, 100 - home));
        awayDisplays.forEach(function (display) {
            display.value = away;
        });
        document.querySelectorAll("[data-home-percentage-mirror]").forEach(function (mirror) {
            mirror.value = homeField.value;
        });
    }

    homeField.addEventListener("input", syncFromHome);

    awayDisplays.forEach(function (display) {
        display.addEventListener("input", function () {
            var away = parseInt(display.value, 10);
            homeField.value = isNaN(away) ? "" : Math.max(0, Math.min(100, 100 - away));
            syncFromHome();
        });
    });

    syncFromHome();
})();
