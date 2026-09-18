document.addEventListener("DOMContentLoaded", () => {
    initRefreshButton();
    initNewsChart();
});

function initRefreshButton() {
    const button = document.getElementById("refreshNews");

    if (!button) return;

    const defaultContent = button.innerHTML;

    button.addEventListener("click", async () => {
        button.disabled = true;
        button.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Tarama başlatılıyor';

        try {
            const response = await fetch(button.dataset.refreshUrl, {
                method: "POST",
                headers: { "X-Requested-With": "XMLHttpRequest" },
            });

            if (!response.ok) {
                throw new Error("Haber taraması başlatılamadı.");
            }

            showToast("Tarama başladı", "Kaynaklar arka planda kontrol ediliyor. Yeni sonuçlar için kısa süre sonra sayfayı yenileyin.", "success");
        } catch (error) {
            showToast("Tarama başlatılamadı", error.message, "danger");
        } finally {
            button.disabled = false;
            button.innerHTML = defaultContent;
        }
    });
}

function initNewsChart() {
    const canvas = document.getElementById("newsChart");

    if (!canvas || typeof Chart === "undefined") return;

    const chart = JSON.parse(canvas.dataset.chart || "{}");

    new Chart(canvas, {
        type: "line",
        data: {
            labels: chart.labels || [],
            datasets: [{
                label: "Haber",
                data: chart.values || [],
                borderColor: "#2563eb",
                backgroundColor: "rgba(37, 99, 235, 0.12)",
                borderWidth: 3,
                tension: 0.35,
                fill: true,
                pointRadius: 3,
                pointHoverRadius: 5,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { precision: 0 },
                    grid: { color: "rgba(148, 163, 184, 0.16)" },
                },
                x: { grid: { display: false } },
            },
        },
    });
}
