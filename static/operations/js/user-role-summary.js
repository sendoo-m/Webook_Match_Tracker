// Client-side only presentation layer for the Add/Edit User form - reads
// the same <select>/checkboxes the form already submits and mirrors them
// back as plain language (Tesler's Law: explain the real effect instead
// of hiding it) plus a live review summary (Peak-End Rule) before Save.
// Never changes what gets submitted; purely descriptive.
//
// All displayed text comes from the server (json_script blocks rendered
// by accounts/views/users.py's RoleSummaryContextMixin, via
// django.utils.translation.gettext) rather than being hardcoded here -
// a string baked directly into a .js file bypasses Django's i18n system
// entirely and would show identically regardless of the active language.
(function () {
    function readJsonScript(id) {
        var el = document.getElementById(id);
        if (!el) {
            return {};
        }
        try {
            return JSON.parse(el.textContent);
        } catch (e) {
            return {};
        }
    }

    var ROLE_INFO = readJsonScript("role-info-data");
    var UI_STRINGS = readJsonScript("ui-strings-data");

    function byId(id) {
        return document.getElementById(id);
    }

    function checkedCount(name) {
        return document.querySelectorAll('input[name="' + name + '"]:checked').length;
    }

    function checkedLabels(name, limit) {
        var boxes = document.querySelectorAll('input[name="' + name + '"]:checked');
        var names = [];
        boxes.forEach(function (box) {
            var label = box.closest("label");
            if (label) {
                names.push(label.textContent.trim());
            }
        });
        var separator = UI_STRINGS.listSeparator || ", ";
        if (limit && names.length > limit) {
            var extra = names.length - limit;
            var andOthers = (UI_STRINGS.andOthers || "and {count} others").replace("{count}", extra);
            return names.slice(0, limit).join(separator) + " " + andOthers;
        }
        return names.join(separator);
    }

    function updateRoleBox() {
        var select = byId("id_group");
        var box = byId("role-description-box");
        if (!select || !box) {
            return;
        }
        var selectedText = select.options[select.selectedIndex]
            ? select.options[select.selectedIndex].text.trim()
            : "";
        var info = ROLE_INFO[selectedText];
        var textEl = byId("role-description-text");
        if (info && textEl) {
            textEl.textContent = info.description;
            box.hidden = false;
        } else if (box) {
            box.hidden = true;
        }
        updateSensitiveBox(info);
    }

    function updateSensitiveBox(info) {
        var box = byId("sensitive-permissions-box");
        var list = byId("sensitive-permissions-list");
        if (!box || !list) {
            return;
        }
        if (info && info.sensitive) {
            list.innerHTML = "";
            (info.reasons || []).forEach(function (reason) {
                var li = document.createElement("li");
                li.textContent = reason;
                list.appendChild(li);
            });
            box.hidden = false;
        } else {
            box.hidden = true;
        }
    }

    function updateReviewSummary() {
        var none = UI_STRINGS.none || "—";

        var select = byId("id_group");
        var summaryRole = byId("review-role");
        if (select && summaryRole) {
            summaryRole.textContent = select.options[select.selectedIndex]
                ? select.options[select.selectedIndex].text.trim()
                : none;
        }

        var summaryClubs = byId("review-clubs");
        if (summaryClubs) {
            var count = checkedCount("owned_clubs");
            summaryClubs.textContent = count ? count + " (" + checkedLabels("owned_clubs", 3) + ")" : none;
        }

        var summaryClubAccount = byId("review-club-account");
        var clubAccountSelect = byId("id_club_account");
        if (summaryClubAccount && clubAccountSelect) {
            var opt = clubAccountSelect.options[clubAccountSelect.selectedIndex];
            summaryClubAccount.textContent = opt && opt.value ? opt.text.trim() : none;
        }

        var summaryCompetitions = byId("review-competitions");
        if (summaryCompetitions) {
            var compCount = checkedCount("competitions");
            summaryCompetitions.textContent = compCount ? String(compCount) : none;
        }

        var summaryStatus = byId("review-status");
        var activeCheckbox = byId("id_is_active");
        if (summaryStatus && activeCheckbox) {
            summaryStatus.textContent = activeCheckbox.checked
                ? (UI_STRINGS.active || "Active")
                : (UI_STRINGS.inactive || "Inactive");
        }
    }

    function updateAll() {
        updateRoleBox();
        updateReviewSummary();
    }

    document.addEventListener("DOMContentLoaded", function () {
        var form = document.getElementById("user-form");
        if (!form) {
            return;
        }
        updateAll();
        form.addEventListener("change", updateAll);
        form.addEventListener("input", updateReviewSummary);
    });
})();
