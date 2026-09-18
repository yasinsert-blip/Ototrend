function initEditor() {

    const form = document.getElementById("bulkForm");

    /*
     * =========================================================
     * BULK FORM
     * =========================================================
     */

    if (form) {

        const selectAll =
            document.getElementById("selectAll");

        const checkboxes =
            document.querySelectorAll(".news-check");

        const selectedCount =
            document.getElementById("selectedCount");

        const bulkButtons =
            document.querySelectorAll(".bulk-action");


        function getSelectedIds() {

            return [...checkboxes]
                .filter(cb => cb.checked)
                .map(cb => cb.value);

        }


        function updateCount() {

            const count =
                getSelectedIds().length;

            if (selectedCount) {
                selectedCount.textContent = count;
            }

            bulkButtons.forEach(btn => {

                btn.disabled = (count === 0);

            });

        }


        /*
         * =====================================================
         * BULK ACTION EVENTS
         * =====================================================
         */

        bulkButtons.forEach(button => {

            button.addEventListener(
                "click",
                function (event) {

                    event.preventDefault();

                    const ids =
                        getSelectedIds();

                    if (ids.length === 0) {

                        if (typeof showToast === "function") {

                            showToast(
                                "Uyarı",
                                "Lütfen en az bir haber seçin.",
                                "warning"
                            );

                        } else {

                            alert(
                                "Lütfen en az bir haber seçin."
                            );

                        }

                        return;

                    }


                    let title = "";
                    let message = "";


                    switch (button.value) {

                        case "ai":

                            title = "AI İşleme";

                            message =
                                ids.length +
                                " haber AI yeniden işlenecek.<br><br>" +
                                "Devam etmek istiyor musunuz?";

                            break;


                        case "editor_review":

                            title = "Editör İnceleme";

                            message =
                                ids.length +
                                " haber Editör İnceleme durumuna geçirilecek.";

                            break;


                        case "instagram_ready":

                            title = "Editör Onayı";

                            message =
                                ids.length +
                                " Instagram taslağı onaylanacak ve Instagram Hazır durumuna geçirilecek.";

                            break;


                        case "instagram_generate":

                            title = "Instagram Taslağı";

                            message =
                                ids.length +
                                " haber için kaynak fotoğrafı, başlık ve açıklama oluşturulacak.<br><br>" +
                                "İşlem birkaç dakika sürebilir; en fazla 3 haber seçilebilir.";

                            break;


                        case "scheduled":

                            title = "Planla";

                            message =
                                ids.length +
                                " Instagram içeriği Planlandı durumuna geçirilecek.";

                            break;


                        case "published":

                            title = "Yayınla";

                            message =
                                ids.length +
                                " haber yayınlanacak.";

                            break;


                        case "archived":

                            title = "Arşivle";

                            message =
                                ids.length +
                                " haber arşivlenecek.";

                            break;


                        case "delete":

                            title = "Sil";

                            message =
                                "<span class='text-danger fw-bold'>" +
                                ids.length +
                                " haber silinecek.</span><br><br>" +
                                "Bu işlem geri alınamaz.";

                            break;


                        default:

                            title = "Onay";

                            message =
                                "İşleme devam edilsin mi?";

                    }


                    const confirmFunction =
                        typeof showConfirm === "function"
                            ? showConfirm
                            : function (
                                title,
                                message,
                                callback
                            ) {

                                if (confirm(
                                    message.replace(
                                        /<br\s*\/?>/gi,
                                        "\n"
                                    )
                                )) {

                                    callback();

                                }

                            };


                    confirmFunction(
                        title,
                        message,
                        async function () {

                            if (
                                typeof showLoading ===
                                "function"
                            ) {

                                showLoading();

                            }


                            try {

                                const formData =
                                    new FormData(form);

                                formData.set(
                                    "action",
                                    button.value
                                );


                                const response =
                                    await fetch(
                                        "/editor/bulk",
                                        {
                                            method: "POST",

                                            headers: {
                                                "X-Requested-With":
                                                    "XMLHttpRequest"
                                            },

                                            body: formData
                                        }
                                    );


                                if (!response.ok) {

                                    throw new Error(
                                        "Sunucu hatası: " +
                                        response.status
                                    );

                                }


                                const data =
                                    await response.json();


                                if (
                                    typeof hideLoading ===
                                    "function"
                                ) {

                                    hideLoading();

                                }


                                if (!data.success) {

                                    throw new Error(
                                        data.message ||
                                        "İşlem başarısız."
                                    );

                                }


                                if (
                                    typeof showToast ===
                                    "function"
                                ) {

                                    showToast(
                                        "Başarılı",
                                        data.message,
                                        "success"
                                    );

                                }


                                setTimeout(
                                    () => {
                                        location.reload();
                                    },
                                    800
                                );

                            }
                            catch (error) {

                                if (
                                    typeof hideLoading ===
                                    "function"
                                ) {

                                    hideLoading();

                                }


                                if (
                                    typeof showToast ===
                                    "function"
                                ) {

                                    showToast(
                                        "Hata",
                                        error.message,
                                        "danger"
                                    );

                                } else {

                                    alert(
                                        error.message
                                    );

                                }

                            }

                        }
                    );

                }
            );

        });


        /*
         * =====================================================
         * SELECT ALL
         * =====================================================
         */

        if (selectAll) {

            selectAll.addEventListener(
                "change",
                function () {

                    checkboxes.forEach(
                        cb => {
                            cb.checked =
                                selectAll.checked;
                        }
                    );

                    updateCount();

                }
            );

        }


        /*
         * =====================================================
         * CHECKBOXES
         * =====================================================
         */

        checkboxes.forEach(
            cb => {

                cb.addEventListener(
                    "change",
                    function () {

                        updateCount();

                        if (selectAll) {

                            const checked =
                                [...checkboxes]
                                .filter(
                                    x => x.checked
                                )
                                .length;

                            selectAll.checked =
                                checked ===
                                checkboxes.length;

                            selectAll.indeterminate =
                                checked > 0 &&
                                checked <
                                checkboxes.length;

                        }

                    }
                );

            }
        );


        updateCount();

    }

/*
 * =========================================================
 * INLINE EDITOR SAVE
 * Event Delegation
 * =========================================================
 */

document.addEventListener("click", async function (event) {

    const button = event.target.closest(".save-editor-news");

    if (!button) {
        return;
    }

    event.preventDefault();
    event.stopPropagation();

    console.log(
        "📝 Kaydet tıklandı:",
        button.dataset.newsId
    );

    const newsId = button.dataset.newsId;

    if (!newsId) {

        if (typeof showToast === "function") {

            showToast(
                "Hata",
                "Haber ID bulunamadı.",
                "danger"
            );

        } else {

            alert("Haber ID bulunamadı.");

        }

        return;
    }


    /*
     * =====================================================
     * EDITOR ALANLARI
     * =====================================================
     */

    const fields = document.querySelectorAll(
        `.editor-field[data-news-id="${newsId}"]`
    );

    console.log(
        "📝 Editör alanları:",
        fields.length
    );


    if (!fields.length) {

        if (typeof showToast === "function") {

            showToast(
                "Hata",
                "Editör alanları bulunamadı.",
                "danger"
            );

        } else {

            alert(
                "Editör alanları bulunamadı."
            );

        }

        return;
    }


    /*
     * =====================================================
     * FORM DATA
     * =====================================================
     */

    const formData = new FormData();

    fields.forEach(field => {

        const fieldName =
            field.dataset.field;

        if (!fieldName) {
            return;
        }

        formData.append(
            fieldName,
            field.value
        );

    });


    /*
     * =====================================================
     * IMPORTANCE
     * =====================================================
     */

    const importanceField =
        document.querySelector(
            `.editor-field[data-news-id="${newsId}"][data-field="importance"]`
        );


    if (importanceField) {

        const importance =
            Number(importanceField.value);


        if (
            !Number.isInteger(importance) ||
            importance < 1 ||
            importance > 10
        ) {

            if (typeof showToast === "function") {

                showToast(
                    "Uyarı",
                    "Önem değeri 1 ile 10 arasında olmalıdır.",
                    "warning"
                );

            } else {

                alert(
                    "Önem değeri 1 ile 10 arasında olmalıdır."
                );

            }

            importanceField.focus();

            return;
        }

    }


    /*
     * =====================================================
     * KAYDETME
     * =====================================================
     */

    const originalHTML =
        button.innerHTML;


    const originalDisabled =
        button.disabled;


    button.disabled = true;


    button.innerHTML =
        '<span class="spinner-border spinner-border-sm me-1"></span>' +
        'Kaydediliyor...';


    try {

        console.log(
            "💾 Kayıt gönderiliyor:",
            `/editor/${newsId}/save`
        );


        const response = await fetch(
            `/editor/${newsId}/save`,
            {
                method: "POST",

                headers: {
                    "X-Requested-With":
                        "XMLHttpRequest"
                },

                body: formData
            }
        );


        console.log(
            "💾 Sunucu cevabı:",
            response.status
        );


        /*
         * =================================================
         * HTTP KONTROLÜ
         * =================================================
         */

        if (!response.ok) {

            let errorMessage =
                `Sunucu hatası (${response.status})`;


            try {

                const errorData =
                    await response.json();


                if (errorData.message) {

                    errorMessage =
                        errorData.message;

                }

            } catch (_) {
            }


            throw new Error(
                errorMessage
            );
        }


        /*
         * =================================================
         * JSON
         * =================================================
         */

        const data =
            await response.json();


        console.log(
            "💾 Kayıt cevabı:",
            data
        );


        if (!data.success) {

            throw new Error(
                data.message ||
                "Kayıt başarısız."
            );

        }


        /*
         * =================================================
         * BAŞARILI
         * =================================================
         */

        if (typeof showToast === "function") {

            showToast(
                "Başarılı",
                data.message ||
                "Değişiklikler kaydedildi.",
                "success"
            );

        }


        button.innerHTML =
            '<i class="bi bi-check-circle me-1"></i>' +
            'Kaydedildi';


        /*
         * =================================================
         * ORIGINAL DEĞERLER
         * =================================================
         */

        fields.forEach(field => {

            field.dataset.originalValue =
                field.value;

        });


        setTimeout(() => {

            button.innerHTML =
                originalHTML;

            button.disabled =
                originalDisabled;

        }, 1500);


    } catch (error) {

        console.error(
            "❌ Editör kayıt hatası:",
            error
        );


        button.innerHTML =
            originalHTML;

        button.disabled =
            originalDisabled;


        if (typeof showToast === "function") {

            showToast(
                "Hata",
                error.message ||
                "Değişiklikler kaydedilemedi.",
                "danger"
            );

        } else {

            alert(
                error.message ||
                "Değişiklikler kaydedilemedi."
            );

        }

    }

});


console.log(
    "✅ Inline editör event delegation hazır."
);


/*
 * =========================================================
 * EDITOR INIT
 * =========================================================
 */

if (document.readyState === "loading") {

    document.addEventListener(
        "DOMContentLoaded",
        initEditor
    );

} else {

    initEditor();

}

}
