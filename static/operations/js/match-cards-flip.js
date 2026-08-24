/* Matches list - clicking a match card flips it to reveal status, progress,
   venue and discount on the back, instead of a wide table. Delegated on the
   grid since the list can have dozens of cards. */
(function () {
    const grid = document.querySelector('.match-cards-grid');
    if (!grid) return;

    grid.addEventListener('click', function (event) {
        // Let the "Full details" link on the back navigate normally.
        if (event.target.closest('.match-flip-card-link')) return;

        const card = event.target.closest('.match-flip-card');
        if (!card) return;

        const isFlipped = card.classList.toggle('is-flipped');
        card.setAttribute('aria-expanded', String(isFlipped));
    });

    // Keyboard support: Enter/Space flips the focused card.
    grid.addEventListener('keydown', function (event) {
        if (event.key !== 'Enter' && event.key !== ' ') return;
        const card = event.target.closest('.match-flip-card');
        if (!card) return;
        event.preventDefault();
        const isFlipped = card.classList.toggle('is-flipped');
        card.setAttribute('aria-expanded', String(isFlipped));
    });
})();
