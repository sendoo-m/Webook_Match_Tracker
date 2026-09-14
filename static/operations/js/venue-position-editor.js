/* Click-to-place editor for VenueSeatingCategory.position_x/position_y -
   one point per block, saved immediately on click (no batch "Save" button,
   so a placement is never lost if the coordinator navigates away). Talks to
   control_panel:venue-category-position-save, one POST per placement/clear. */
(function () {
    var dataEl = document.getElementById('position-editor-categories-data');
    var imageWrap = document.getElementById('position-editor-image-wrap');
    var image = document.getElementById('position-editor-image');
    var listEl = document.getElementById('position-editor-category-list');
    if (!dataEl || !imageWrap || !image || !listEl) return;

    var categories = JSON.parse(dataEl.textContent);
    var categoriesById = {};
    categories.forEach(function (c) { categoriesById[c.id] = c; });

    var selectedCategoryId = null;
    var markerEls = {};

    function getCookie(name) {
        var match = document.cookie.match('(?:^|; )' + name + '=([^;]*)');
        return match ? decodeURIComponent(match[1]) : null;
    }

    function saveUrl(categoryId) {
        return window.POSITION_EDITOR_SAVE_URL_TEMPLATE.replace('__CATEGORY_ID__', categoryId);
    }

    function postPosition(categoryId, x, y) {
        var body = new URLSearchParams();
        if (x !== null && y !== null) {
            body.set('x', x);
            body.set('y', y);
        }
        return fetch(saveUrl(categoryId), {
            method: 'POST',
            headers: { 'X-CSRFToken': getCookie('csrftoken') },
            body: body,
        }).then(function (r) { return r.json(); });
    }

    function setRowStatus(categoryId, placed) {
        var row = listEl.querySelector('[data-category-id="' + categoryId + '"]');
        if (!row) return;
        var status = row.querySelector('[data-role="status"]');
        if (!status) return;
        status.textContent = placed ? status.dataset.placedLabel : status.dataset.unplacedLabel;
        status.classList.toggle('mini-badge-success', placed);
        status.classList.toggle('mini-badge-info', !placed);
    }

    function removeMarker(categoryId) {
        var el = markerEls[categoryId];
        if (el) {
            el.remove();
            delete markerEls[categoryId];
        }
    }

    function renderMarker(categoryId, xPct, yPct) {
        removeMarker(categoryId);
        var category = categoriesById[categoryId];
        var marker = document.createElement('div');
        marker.className = 'position-editor-marker';
        marker.style.left = xPct + '%';
        marker.style.top = yPct + '%';
        marker.innerHTML = '<span class="position-editor-marker-label">' + category.code + '</span>'
            + '<button type="button" class="position-editor-marker-remove" aria-label="Remove">×</button>';
        marker.querySelector('.position-editor-marker-remove').addEventListener('click', function (evt) {
            evt.stopPropagation();
            postPosition(categoryId, null, null).then(function () {
                removeMarker(categoryId);
                setRowStatus(categoryId, false);
            });
        });
        imageWrap.appendChild(marker);
        markerEls[categoryId] = marker;
    }

    categories.forEach(function (category) {
        if (category.placed) {
            renderMarker(category.id, category.x, category.y);
        }
    });

    Array.prototype.forEach.call(listEl.querySelectorAll('.position-editor-category-row'), function (row) {
        row.addEventListener('click', function () {
            selectedCategoryId = row.dataset.categoryId;
            Array.prototype.forEach.call(listEl.querySelectorAll('.position-editor-category-row'), function (r) {
                r.classList.toggle('is-selected', r === row);
            });
        });
    });

    image.addEventListener('click', function (evt) {
        if (!selectedCategoryId) return;
        var rect = image.getBoundingClientRect();
        var xPct = ((evt.clientX - rect.left) / rect.width) * 100;
        var yPct = ((evt.clientY - rect.top) / rect.height) * 100;
        xPct = Math.max(0, Math.min(100, xPct));
        yPct = Math.max(0, Math.min(100, yPct));
        var categoryId = selectedCategoryId;
        postPosition(categoryId, xPct.toFixed(2), yPct.toFixed(2)).then(function (result) {
            if (result && result.ok) {
                renderMarker(categoryId, xPct, yPct);
                setRowStatus(categoryId, true);
            }
        });
    });
})();
