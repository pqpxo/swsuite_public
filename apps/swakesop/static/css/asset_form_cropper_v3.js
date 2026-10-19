// ## version 3
(function () {
  const input = document.getElementById('photo-upload');
  const modal = document.getElementById('image-crop-modal');
  const canvas = document.getElementById('crop-preview-canvas');
  const closeBtn = document.getElementById('crop-close-btn');
  const applyBtn = document.getElementById('crop-apply-btn');
  const useOriginalBtn = document.getElementById('crop-use-original-btn');
  const zoomInput = document.getElementById('crop-zoom');
  const offsetXInput = document.getElementById('crop-offset-x');
  const offsetYInput = document.getElementById('crop-offset-y');
  const previewWrap = document.getElementById('selected-photo-preview');
  const previewList = document.getElementById('selected-photo-preview-list');

  if (!input || !modal || !canvas || !applyBtn || !useOriginalBtn || !zoomInput || !offsetXInput || !offsetYInput) {
    return;
  }

  const ctx = canvas.getContext('2d');
  const outputSize = 1200;
  let currentFile = null;
  let currentImage = null;
  let activeResolver = null;

  function resetControls() {
    zoomInput.value = '1';
    offsetXInput.value = '0';
    offsetYInput.value = '0';
  }

  function openModal() {
    modal.hidden = false;
    modal.classList.add('is-open');
    document.body.style.overflow = 'hidden';
  }

  function closeModal() {
    modal.hidden = true;
    modal.classList.remove('is-open');
    document.body.style.overflow = '';
  }

  function loadImage(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.onerror = reject;
        img.src = reader.result;
      };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  function drawPreview() {
    if (!currentImage) return;

    const zoom = parseFloat(zoomInput.value || '1');
    const offsetXPct = parseFloat(offsetXInput.value || '0') / 100;
    const offsetYPct = parseFloat(offsetYInput.value || '0') / 100;
    const cw = canvas.width;
    const ch = canvas.height;

    ctx.clearRect(0, 0, cw, ch);
    ctx.save();

    if ((currentFile?.type || '').toLowerCase() === 'image/png' || /\.png$/i.test(currentFile?.name || '')) {
      ctx.clearRect(0, 0, cw, ch);
    } else {
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, cw, ch);
    }

    const imgRatio = currentImage.width / currentImage.height;
    const canvasRatio = cw / ch;

    let baseWidth;
    let baseHeight;

    if (imgRatio > canvasRatio) {
      baseWidth = cw;
      baseHeight = baseWidth / imgRatio;
    } else {
      baseHeight = ch;
      baseWidth = baseHeight * imgRatio;
    }

    const drawWidth = baseWidth * zoom;
    const drawHeight = baseHeight * zoom;

    const maxOffsetX = Math.max(0, (cw - drawWidth) / 2);
    const minOffsetX = Math.min(0, (cw - drawWidth) / 2);
    const maxOffsetY = Math.max(0, (ch - drawHeight) / 2);
    const minOffsetY = Math.min(0, (ch - drawHeight) / 2);

    const dx = ((cw - drawWidth) / 2) + ((maxOffsetX - minOffsetX) * offsetXPct);
    const dy = ((ch - drawHeight) / 2) + ((maxOffsetY - minOffsetY) * offsetYPct);

    ctx.drawImage(currentImage, dx, dy, drawWidth, drawHeight);
    ctx.restore();

    ctx.save();
    ctx.strokeStyle = 'rgba(92, 130, 255, 0.8)';
    ctx.lineWidth = 4;
    ctx.strokeRect(2, 2, cw - 4, ch - 4);
    ctx.restore();
  }

  function exportCanvasToFile(sourceFile) {
    return new Promise((resolve) => {
      const exportCanvas = document.createElement('canvas');
      exportCanvas.width = outputSize;
      exportCanvas.height = outputSize;
      const exportCtx = exportCanvas.getContext('2d');

      if ((sourceFile.type || '').toLowerCase() === 'image/png' || /\.png$/i.test(sourceFile.name || '')) {
        exportCtx.clearRect(0, 0, outputSize, outputSize);
      } else {
        exportCtx.fillStyle = '#ffffff';
        exportCtx.fillRect(0, 0, outputSize, outputSize);
      }

      exportCtx.drawImage(canvas, 0, 0, outputSize, outputSize);

      const isPng = (sourceFile.type || '').toLowerCase() === 'image/png' || /\.png$/i.test(sourceFile.name || '');
      const mimeType = isPng ? 'image/png' : 'image/jpeg';
      const extension = isPng ? '.png' : '.jpg';
      const cleanName = (sourceFile.name || 'image').replace(/\.[^.]+$/, '');

      exportCanvas.toBlob((blob) => {
        const file = new File([blob], `${cleanName}_cropped${extension}`, {
          type: mimeType,
          lastModified: Date.now(),
        });
        resolve(file);
      }, mimeType, isPng ? undefined : 0.92);
    });
  }

  function renderSelectedFiles(files) {
    if (!previewWrap || !previewList) return;
    previewList.innerHTML = '';

    if (!files.length) {
      previewWrap.hidden = true;
      return;
    }

    previewWrap.hidden = false;

    files.forEach((file) => {
      const chip = document.createElement('div');
      chip.className = 'selected-photo-chip';

      const img = document.createElement('img');
      const label = document.createElement('span');
      label.textContent = file.name;

      chip.appendChild(img);
      chip.appendChild(label);
      previewList.appendChild(chip);

      const reader = new FileReader();
      reader.onload = () => { img.src = reader.result; };
      reader.readAsDataURL(file);
    });
  }

  function replaceInputFiles(files) {
    const dt = new DataTransfer();
    files.forEach((file) => dt.items.add(file));
    input.files = dt.files;
    renderSelectedFiles(files);
  }

  async function editFile(file) {
    currentFile = file;
    currentImage = await loadImage(file);
    resetControls();
    drawPreview();
    openModal();

    return new Promise((resolve) => {
      activeResolver = resolve;
    });
  }

  async function processQueue(fileList) {
    const queue = Array.from(fileList || []).filter((file) => file.type.startsWith('image/'));
    if (!queue.length) return;

    const output = [];
    for (const file of queue) {
      const result = await editFile(file);
      output.push(result);
    }
    replaceInputFiles(output);
  }

  input.addEventListener('change', async (event) => {
    const files = event.target.files;
    if (!files || !files.length) return;

    try {
      await processQueue(files);
    } catch (error) {
      console.error('Crop workflow failed:', error);
      renderSelectedFiles(Array.from(files));
    } finally {
      closeModal();
    }
  });

  [zoomInput, offsetXInput, offsetYInput].forEach((el) => el.addEventListener('input', drawPreview));

  applyBtn.addEventListener('click', async () => {
    if (!activeResolver || !currentFile) return;
    const resolver = activeResolver;
    activeResolver = null;
    const cropped = await exportCanvasToFile(currentFile);
    closeModal();
    resolver(cropped);
  });

  useOriginalBtn.addEventListener('click', () => {
    if (!activeResolver || !currentFile) return;
    const resolver = activeResolver;
    activeResolver = null;
    closeModal();
    resolver(currentFile);
  });

  closeBtn.addEventListener('click', () => {
    if (!activeResolver || !currentFile) {
      closeModal();
      return;
    }
    const resolver = activeResolver;
    activeResolver = null;
    closeModal();
    resolver(currentFile);
  });

  modal.addEventListener('click', (event) => {
    if (event.target === modal) closeBtn.click();
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && modal.classList.contains('is-open')) {
      closeBtn.click();
    }
  });
})();
