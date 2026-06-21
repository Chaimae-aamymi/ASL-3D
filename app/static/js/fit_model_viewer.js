/**
 * Cadre automatiquement model-viewer sur le modèle (évite l'effet "tout petit dans un coin").
 */
(function () {
    function fitModelViewer(mv) {
        if (!mv || typeof mv.getBoundingBoxCenter !== 'function') return;

        const apply = () => {
            try {
                const center = mv.getBoundingBoxCenter();
                const size = mv.getDimensions();
                const maxDim = Math.max(size.x, size.y, size.z, 0.001);
                const radius = Math.max(maxDim * 0.42, 0.2);
                mv.cameraTarget = `${center.x}m ${center.y}m ${center.z}m`;
                mv.cameraOrbit = `45deg 62deg ${radius}m`;
                mv.fieldOfView = '28deg';
                if (typeof mv.jumpCameraToGoal === 'function') {
                    mv.jumpCameraToGoal(0);
                }
            } catch (e) {
                console.warn('[fit_model_viewer]', e);
            }
        };

        if (mv.loaded) {
            apply();
        } else {
            mv.addEventListener('load', apply, { once: true });
        }
    }

    function initAll() {
        document.querySelectorAll('model-viewer[data-autofit]').forEach(fitModelViewer);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAll);
    } else {
        initAll();
    }

    window.fitModelViewer = fitModelViewer;
})();
