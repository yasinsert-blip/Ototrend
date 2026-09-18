/*
====================================================
 OtoTrend AI Newsroom UI Library
 Version : 1.0
====================================================
*/

(function () {

    "use strict";

    // ============================================
    // Toast
    // ============================================

    window.showToast = function (
        title,
        message,
        type = "success"
    ) {

        const container =
            document.getElementById("toastContainer");

        if (!container) return;

        const icon = {
            success: "bi-check-circle-fill text-success",
            danger: "bi-x-circle-fill text-danger",
            warning: "bi-exclamation-triangle-fill text-warning",
            info: "bi-info-circle-fill text-primary"
        };

        const toast = document.createElement("div");

        toast.className =
            "toast align-items-center border-0 mb-2";

        toast.setAttribute("role", "alert");
        toast.setAttribute("aria-live", "assertive");
        toast.setAttribute("aria-atomic", "true");

        toast.innerHTML = `
            <div class="toast-header">
                <i class="bi ${icon[type] || icon.info} me-2"></i>
                <strong class="me-auto">${title}</strong>
                <small>Şimdi</small>
                <button
                    type="button"
                    class="btn-close"
                    data-bs-dismiss="toast">
                </button>
            </div>

            <div class="toast-body">
                ${message}
            </div>
        `;

        container.appendChild(toast);

        const bsToast =
            new bootstrap.Toast(toast, {
                delay: 3500
            });

        bsToast.show();

        toast.addEventListener(
            "hidden.bs.toast",
            function () {
                toast.remove();
            }
        );

    };


    // ============================================
    // Loading Overlay
    // ============================================

    window.showLoading = function () {

        const overlay =
            document.getElementById("loadingOverlay");

        if (!overlay) return;

        overlay.classList.remove("d-none");

    };

    window.hideLoading = function () {

        const overlay =
            document.getElementById("loadingOverlay");

        if (!overlay) return;

        overlay.classList.add("d-none");

    };


    // ============================================
    // Confirm
    // ============================================

    window.showConfirm = function (

        title,

        message,

        callback

    ) {

        const modal =
            document.getElementById("confirmModal");

        if (!modal) {

            if (confirm(message)) {
                callback();
            }

            return;

        }

        modal.querySelector(".modal-title")
            .innerText = title;

        modal.querySelector(".modal-body")
            .innerHTML = message;

        const confirmButton =
            modal.querySelector("#confirmOk");

        const bsModal =
            new bootstrap.Modal(modal);

        const newButton =
            confirmButton.cloneNode(true);

        confirmButton.parentNode.replaceChild(
            newButton,
            confirmButton
        );

        newButton.addEventListener(
            "click",
            function () {

                bsModal.hide();

                if (callback) {
                    callback();
                }

            }
        );

        bsModal.show();

    };

})();