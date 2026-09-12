/* CMS Status Control progressive disclosure (Hick's Law) - the "this goes
   live immediately" warning and the button's warning styling only show up
   once "Published" is the value actually selected, instead of always-on
   text next to a routine dropdown. Also requires a confirm() step before
   actually submitting a change to Published (Von Restorff: this action
   needs to feel different from every other routine save on the page).
   Delegated on document since this partial gets replaced wholesale by its
   own hx-swap-oob after every CMS-status/webook-link/send-to-cms update. */
(function () {
    function isPublishSelected(select) {
        return select.value === select.dataset.publishValue;
    }

    function syncControl(select) {
        const form = select.closest("form");
        if (!form) return;
        const warning = form.querySelector(".cms-control-warning");
        const button = form.querySelector("[data-cms-submit]");
        const publishing = isPublishSelected(select);
        if (warning) warning.hidden = !publishing;
        if (button) button.classList.toggle("btn-cms-publish-warning", publishing);
    }

    document.addEventListener("change", function (event) {
        const select = event.target.closest("[data-cms-status-select]");
        if (!select) return;
        syncControl(select);
    });

    document.addEventListener("submit", function (event) {
        const form = event.target.closest(".cms-control-form");
        if (!form) return;
        const select = form.querySelector("[data-cms-status-select]");
        if (select && isPublishSelected(select)) {
            const message = form.dataset.publishConfirm || "This will make the match visible on the public dashboard immediately. Continue?";
            if (!confirm(message)) {
                event.preventDefault();
            }
        }
    });

    document.querySelectorAll("[data-cms-status-select]").forEach(syncControl);
})();
