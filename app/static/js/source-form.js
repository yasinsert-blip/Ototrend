document.addEventListener("DOMContentLoaded", () => {
    const reader = document.getElementById("source-reader");
    const rss = document.getElementById("source-rss");
    if (!reader || !rss) return;
    const updateRequired = () => { rss.required = reader.value === "RSS"; };
    reader.addEventListener("change", updateRequired);
    updateRequired();
});
