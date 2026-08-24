/* Quick tour help panel (bottom-right "?" button). */
(function () {
    const trainingButton = document.querySelector('.fab-training');
    const trainingPanel = document.getElementById('training-panel');
    const trainingClose = document.querySelector('.training-panel-close');

    function setTrainingPanel(open) {
        if (!trainingPanel || !trainingButton) return;
        trainingPanel.classList.toggle('is-open', open);
        trainingButton.setAttribute('aria-expanded', String(open));
    }

    trainingButton?.addEventListener('click', () => setTrainingPanel(!trainingPanel.classList.contains('is-open')));
    trainingClose?.addEventListener('click', () => setTrainingPanel(false));
})();
