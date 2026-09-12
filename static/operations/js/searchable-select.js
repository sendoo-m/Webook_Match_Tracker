/* Progressive enhancement: turns any <select data-searchable> into a
   type-to-filter combobox, while leaving the original <select> in the DOM
   as the real form control - filters-auto-submit.js's change listener and
   normal form submission both keep working completely unchanged, since
   this only ever drives that same <select>'s value programmatically.
   Re-scans after every HTMX swap since a filter form/panel can be
   replaced wholesale by an HTMX response on some pages. */
(function () {
    function labelFor(option) {
        return option.textContent.trim();
    }

    function enhance(select) {
        if (select.dataset.enhanced) return;
        select.dataset.enhanced = "true";

        const options = Array.from(select.options);

        const wrapper = document.createElement("div");
        wrapper.className = "searchable-select";

        const input = document.createElement("input");
        input.type = "text";
        input.className = "searchable-select-input";
        input.setAttribute("role", "combobox");
        input.setAttribute("aria-expanded", "false");
        input.autocomplete = "off";

        const menu = document.createElement("div");
        menu.className = "searchable-select-menu";
        menu.hidden = true;

        function currentLabel() {
            const opt = select.options[select.selectedIndex];
            return opt ? labelFor(opt) : "";
        }

        function renderMenu(filterText) {
            menu.innerHTML = "";
            const needle = (filterText || "").trim().toLowerCase();
            let anyVisible = false;
            options.forEach(function (option) {
                const label = labelFor(option);
                if (needle && label.toLowerCase().indexOf(needle) === -1) return;
                anyVisible = true;
                const item = document.createElement("button");
                item.type = "button";
                item.className = "searchable-select-item";
                if (option.value === select.value) item.classList.add("is-active");
                item.textContent = label;
                item.addEventListener("mousedown", function (event) {
                    // mousedown (fires before the input's blur handler closes
                    // the menu) so the click still lands on this button.
                    event.preventDefault();
                    select.value = option.value;
                    input.value = label;
                    menu.hidden = true;
                    input.setAttribute("aria-expanded", "false");
                    select.dispatchEvent(new Event("change", { bubbles: true }));
                });
                menu.appendChild(item);
            });
            if (!anyVisible) {
                const empty = document.createElement("div");
                empty.className = "searchable-select-empty";
                empty.textContent = select.dataset.noResultsLabel || "";
                menu.appendChild(empty);
            }
        }

        function openMenu() {
            renderMenu(input.value === currentLabel() ? "" : input.value);
            menu.hidden = false;
            input.setAttribute("aria-expanded", "true");
        }

        function closeMenu() {
            menu.hidden = true;
            input.setAttribute("aria-expanded", "false");
            input.value = currentLabel();
        }

        input.addEventListener("focus", openMenu);
        input.addEventListener("click", openMenu);
        input.addEventListener("input", function () {
            renderMenu(input.value);
            menu.hidden = false;
            input.setAttribute("aria-expanded", "true");
        });
        input.addEventListener("keydown", function (event) {
            if (event.key === "Escape") {
                closeMenu();
                input.blur();
            }
        });
        input.addEventListener("blur", function () {
            // Deferred so a menu item's mousedown still lands first.
            setTimeout(closeMenu, 0);
        });

        input.value = currentLabel();

        wrapper.appendChild(input);
        wrapper.appendChild(menu);
        select.insertAdjacentElement("afterend", wrapper);
        select.classList.add("searchable-select-native");
    }

    function enhanceAll() {
        document.querySelectorAll("select[data-searchable]").forEach(enhance);
    }

    document.addEventListener("DOMContentLoaded", enhanceAll);
    document.addEventListener("htmx:afterSwap", enhanceAll);
})();
