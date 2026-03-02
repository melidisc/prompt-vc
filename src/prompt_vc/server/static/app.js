/* prompt-vc UI JavaScript */

// Flash message auto-dismiss (only targets new messages)
document.addEventListener("htmx:afterSwap", function () {
    dismissFlashMessages();
    // Auto-close sidebar on mobile after boosted navigation
    if (window.innerWidth < 768) {
        var sb = document.getElementById("sidebar");
        if (sb) sb.classList.add("-translate-x-full");
    }
});
document.addEventListener("DOMContentLoaded", function () {
    dismissFlashMessages();
    initHighlightJs();
});

function dismissFlashMessages() {
    document.querySelectorAll(".flash-msg:not([data-dismiss-scheduled])").forEach(function (el) {
        el.setAttribute("data-dismiss-scheduled", "1");
        setTimeout(function () {
            el.style.opacity = "0";
            el.style.transform = "translateY(-0.5rem)";
            el.style.transition = "opacity 0.3s, transform 0.3s";
            setTimeout(function () { el.remove(); }, 300);
        }, 4000);
    });
}

// Re-init highlight.js after HTMX swaps
document.addEventListener("htmx:afterSettle", function () {
    initHighlightJs();
});

function initHighlightJs() {
    if (typeof hljs !== "undefined") {
        document.querySelectorAll("pre code:not(.hljs)").forEach(function (block) {
            hljs.highlightElement(block);
        });
    }
}

// Manual flash dismiss
function dismissFlash(el) {
    el.closest(".flash-msg").remove();
}

// SVG pan/zoom for graph page — returns a controller for reset
function initGraphPanZoom(container) {
    var svg = container.querySelector("svg");
    if (!svg) return null;

    var state = { scale: 1, panX: 0, panY: 0, isPanning: false, startX: 0, startY: 0 };
    var abortCtrl = new AbortController();
    var signal = abortCtrl.signal;

    svg.style.transformOrigin = "0 0";

    function applyTransform() {
        svg.style.transform = "translate(" + state.panX + "px, " + state.panY + "px) scale(" + state.scale + ")";
    }

    container.addEventListener("wheel", function (e) {
        e.preventDefault();
        var delta = e.deltaY > 0 ? 0.9 : 1.1;
        state.scale *= delta;
        state.scale = Math.max(0.1, Math.min(5, state.scale));
        applyTransform();
    }, { passive: false, signal: signal });

    container.addEventListener("mousedown", function (e) {
        state.isPanning = true;
        state.startX = e.clientX - state.panX;
        state.startY = e.clientY - state.panY;
        container.style.cursor = "grabbing";
    }, { signal: signal });

    document.addEventListener("mousemove", function (e) {
        if (!state.isPanning) return;
        state.panX = e.clientX - state.startX;
        state.panY = e.clientY - state.startY;
        applyTransform();
    }, { signal: signal });

    document.addEventListener("mouseup", function () {
        state.isPanning = false;
        container.style.cursor = "grab";
    }, { signal: signal });

    return {
        reset: function () {
            state.scale = 1;
            state.panX = 0;
            state.panY = 0;
            svg.style.transform = "";
        },
        destroy: function () {
            abortCtrl.abort();
        }
    };
}

// Clean up graph listeners when navigating away via hx-boost
document.addEventListener("htmx:beforeSwap", function () {
    if (window._graphPanZoom) {
        window._graphPanZoom.destroy();
        window._graphPanZoom = null;
    }
});

// Annotation line marker — toggle inline annotation panel
document.addEventListener("click", function (e) {
    var marker = e.target.closest(".ann-marker");
    if (!marker) return;
    var lineNum = marker.dataset.line;
    var inlinePanel = document.querySelector('.ann-inline[data-ann-line="' + lineNum + '"]');
    if (inlinePanel) {
        inlinePanel.classList.toggle("hidden");
    }
});

// Also handle keyboard activation of ann-markers
document.addEventListener("keydown", function (e) {
    if ((e.key === "Enter" || e.key === " ") && e.target.classList.contains("ann-marker")) {
        e.preventDefault();
        e.target.click();
    }
});

// Mobile sidebar: toggle overlay visibility with sidebar
var sidebar = document.getElementById("sidebar");
var overlay = document.getElementById("sidebar-overlay");
if (sidebar && overlay) {
    var observer = new MutationObserver(function () {
        if (sidebar.classList.contains("-translate-x-full")) {
            overlay.classList.add("hidden");
        } else {
            overlay.classList.remove("hidden");
        }
    });
    observer.observe(sidebar, { attributes: true, attributeFilter: ["class"] });
}
