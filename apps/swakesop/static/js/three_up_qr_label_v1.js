(() => {
  const openButton = document.getElementById("three-up-qr-open");
  const modal = document.getElementById("three-up-qr-modal");
  if (!openButton || !modal) return;

  const closeTriggers = modal.querySelectorAll("[data-three-up-close]");
  const selectEls = [
    document.getElementById("three-up-asset-1"),
    document.getElementById("three-up-asset-2"),
    document.getElementById("three-up-asset-3"),
  ];
  const resetButton = document.getElementById("three-up-reset");
  const downloadButton = document.getElementById("three-up-download");
  const canvas = document.getElementById("three-up-qr-canvas");
  const ctx = canvas.getContext("2d");

  const LABEL = {
    width: 732,   // 62 mm @ 300 DPI
    height: 343,  // 29 mm @ 300 DPI
    marginX: 18,
    gap: 15,
    qrSize: 222,
  };
  LABEL.top = Math.round((LABEL.height - LABEL.qrSize) / 2);

  let assets = [];
  let assetsLoaded = false;

  function openModal() {
    modal.hidden = false;
    document.body.classList.add("modal-open");
    if (!assetsLoaded) {
      loadAssets();
    } else {
      drawPreview();
    }
  }

  function closeModal() {
    modal.hidden = true;
    document.body.classList.remove("modal-open");
  }

  async function loadAssets() {
    try {
      const response = await fetch("/api/assets/for-three-up-qr", {
        headers: { Accept: "application/json" },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      assets = await response.json();
      assetsLoaded = true;
      populateSelects();
      drawPreview();
    } catch (error) {
      console.error("Failed to load assets for 3-up QR modal:", error);
    }
  }

  function populateSelects() {
    for (const select of selectEls) {
      const currentValue = select.value;
      select.innerHTML = '<option value="">Select an asset</option>';

      for (const asset of assets) {
        const option = document.createElement("option");
        option.value = asset.asset_key;
        option.textContent = asset.name;
        option.dataset.qrUrl = asset.qr_url;
        select.appendChild(option);
      }

      if (currentValue) {
        select.value = currentValue;
      }
    }
  }

  function selectedAssets() {
    return selectEls
      .map((select) => {
        const option = select.options[select.selectedIndex];
        if (!option || !option.value) return null;

        return {
          assetKey: option.value,
          name: option.textContent,
          qrUrl: option.dataset.qrUrl,
        };
      })
      .filter(Boolean);
  }

  function hasThreeUniqueSelections(items) {
    if (items.length !== 3) return false;
    return new Set(items.map((item) => item.assetKey)).size === 3;
  }

  function loadImage(src) {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = reject;
      img.src = src;
    });
  }

  async function drawPreview() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    const items = selectedAssets();
    downloadButton.disabled = !hasThreeUniqueSelections(items);

    for (let i = 0; i < 3; i += 1) {
      const x = LABEL.marginX + i * (LABEL.qrSize + LABEL.gap);

      ctx.strokeStyle = "#d8deeb";
      ctx.lineWidth = 2;
      ctx.strokeRect(x, LABEL.top, LABEL.qrSize, LABEL.qrSize);

      ctx.fillStyle = "#7e8aa6";
      ctx.font = "18px sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(`QR ${i + 1}`, x + LABEL.qrSize / 2, LABEL.top + LABEL.qrSize / 2);
    }

    if (!hasThreeUniqueSelections(items)) return;

    try {
      const images = await Promise.all(items.map((item) => loadImage(item.qrUrl)));

      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = "#ffffff";
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      images.forEach((img, index) => {
        const x = LABEL.marginX + index * (LABEL.qrSize + LABEL.gap);
        ctx.drawImage(img, x, LABEL.top, LABEL.qrSize, LABEL.qrSize);
      });
    } catch (error) {
      console.error("Failed to render 3-up QR preview:", error);
    }
  }

  function resetSelections() {
    selectEls.forEach((select) => {
      select.value = "";
    });
    drawPreview();
  }

  function downloadCanvas() {
    const link = document.createElement("a");
    link.href = canvas.toDataURL("image/png");
    link.download = "three_up_qr_label_62x29mm.png";
    document.body.appendChild(link);
    link.click();
    link.remove();
  }

  openButton.addEventListener("click", openModal);
  closeTriggers.forEach((trigger) => trigger.addEventListener("click", closeModal));
  resetButton.addEventListener("click", resetSelections);
  downloadButton.addEventListener("click", downloadCanvas);
  selectEls.forEach((select) => select.addEventListener("change", drawPreview));

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.hidden) {
      closeModal();
    }
  });
})();
