// ## version 2
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

  if (!input || !modal || !canvas || !applyBtn || !useOriginalBtn) {
    return;
  }

  const ctx = canvas.getContext('2d');
  const outputSize = 1200;
  let queue = [];
  let processedFiles = [];
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

  function drawPreview() {
    if (!currentImage) return;

    const zoom = parseFloat(zoomInput.value || '1');
    const offsetXPct = parseFloat(offsetXInput.value || '0') / 100;
    const offsetYPct = parseFloat(offsetYInput.value || '0') / 100;

    const cw = canvas.width;
    const ch = canvas.height;

    ctx.clearRect(0, 0, cw, ch);
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, cw, ch);

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

    let drawWidth;
    let drawHeight;

    if (zoom >= 1) {
      if (imgRatio > canvasRatio) {
        drawHeight = ch * zoom;
        drawWidth = drawHeight * imgRatio;
      } else {
        drawWidth = cw * zoom;
        drawHeight = drawWidth / imgRatio;
      }
    } else {
      drawWidth = baseWidth * zoom;
      drawHeight = baseHeight * zoom;
    }

    const maxOffsetX = Math.max(0, (drawWidth - cw) / 2);
    const maxOffsetY = Math.max(0, (drawHeight - ch) / 2);

    const dx = (cw - drawWidth) / 2 + (maxOffsetX * offsetXPct * 2);
    const dy = (ch - drawHeight) / 2 + (maxOffsetY * offsetYPct * 2);

    ctx.drawImage(currentImage, dx, dy, drawWidth, drawHeight);

    ctx.save();
    ctx.strokeStyle = 'rgba(92,130,255,0.75)';
    ctx.lineWidth = 4;
    ctx.strokeRect(2, 2, cw - 4, ch - 4);
    ctx.restore();
  }

  function canvasToFile(sourceFile) {
    return new Promise((resolve) => {
      const exportCanvas = document.createElement('canvas');
      exportCanvas.width = outputSize;
      exportCanvas.height = outputSize;
      const exportCtx = exportCanvas.getContext('2d');
      exportCtx.drawImage(canvas, 0, 0, outputSize, outputSize);

      exportCanvas.toBlob((blob) => {
        const name = sourceFile.name.replace(/\.[^.]+$/, '') + '_cropped.jpg';
        resolve(new File([blob], name, { type: 'image/jpeg', lastModified: Date.now() }));
      }, 'image/jpeg', 0.92);
    });
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

  function applyFileList(files) {
    const dt = new DataTransfer();
    files.forEach((file) => dt.items.add(file));
    input.files = dt.files;
    renderSelectedFiles(files);
  }

  function renderSelectedFiles(files) {
    previewList.innerHTML = '';
    if (!files.length) {
      previewWrap.hidden = true;
      return;
    }
    previewWrap.hidden = false;

    files.forEach((file) => {
      const item = document.createElement('div');
      item.className = 'selected-photo-chip';

      const img = document.createElement('img');
      const label = document.createElement('span');
      label.textContent = file.name;

      item.appendChild(img);
      item.appendChild(label);
      previewList.appendChild(item);

      const reader = new FileReader();
      reader.onload = () => {
        img.src = reader.result;
      };
      reader.readAsDataURL(file);
    });
  }

  async function processQueue(files) {
    queue = Array.from(files || []).filter((file) => file.type.startsWith('image/'));
    processedFiles = [];

    if (!queue.length) {
      return;
    }

    for (const file of queue) {
      const result = await editFile(file);
      processedFiles.push(result);
    }

    applyFileList(processedFiles);
  }

  input.addEventListener('change', async (event) => {
    const files = event.target.files;
    if (!files || !files.length) return;

    try {
      await processQueue(files);
    } catch (error) {
      console.error('Image crop workflow failed:', error);
      applyFileList(Array.from(files));
    } finally {
      closeModal();
    }
  });

  [zoomInput, offsetXInput, offsetYInput].forEach((control) => {
    control.addEventListener('input', drawPreview);
  });

  applyBtn.addEventListener('click', async () => {
    if (!activeResolver || !currentFile) return;
    const cropped = await canvasToFile(currentFile);
    const resolver = activeResolver;
    activeResolver = null;
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
    if (event.target === modal) {
      closeBtn.click();
    }
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && modal.classList.contains('is-open')) {
      closeBtn.click();
    }
  });
})();
