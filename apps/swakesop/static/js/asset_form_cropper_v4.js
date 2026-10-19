/* ## version 4 */
(function () {
  const input = document.getElementById('photo-upload');
  const modal = document.getElementById('image-crop-modal');
  const canvas = document.getElementById('crop-preview-canvas');
  const zoomInput = document.getElementById('crop-zoom');
  const offsetXInput = document.getElementById('crop-offset-x');
  const offsetYInput = document.getElementById('crop-offset-y');
  const closeBtn = document.getElementById('crop-close-btn');
  const useOriginalBtn = document.getElementById('crop-use-original-btn');
  const applyBtn = document.getElementById('crop-apply-btn');
  const previewWrap = document.getElementById('selected-photo-preview');
  const previewList = document.getElementById('selected-photo-preview-list');

  if (!input || !modal || !canvas || !zoomInput || !offsetXInput || !offsetYInput || !closeBtn || !useOriginalBtn || !applyBtn) {
    return;
  }

  const ctx = canvas.getContext('2d');
  if (!ctx) {
    return;
  }

  let sourceFiles = [];
  let outputFiles = [];
  let activeIndex = -1;
  let activeFile = null;
  let activeImage = null;
  let imageUrl = null;
  let baseScale = 1;
  let zoom = 1;
  let offsetX = 0;
  let offsetY = 0;

  function resetSliders() {
    zoom = 1;
    offsetX = 0;
    offsetY = 0;
    zoomInput.value = '1';
    offsetXInput.value = '0';
    offsetYInput.value = '0';
  }

  function openModal() {
    modal.hidden = false;
    document.body.style.overflow = 'hidden';
  }

  function closeModal() {
    modal.hidden = true;
    document.body.style.overflow = '';
  }

  function clearState(clearInput = false) {
    sourceFiles = [];
    outputFiles = [];
    activeIndex = -1;
    activeFile = null;
    activeImage = null;
    baseScale = 1;
    resetSliders();

    if (imageUrl) {
      URL.revokeObjectURL(imageUrl);
      imageUrl = null;
    }

    if (clearInput) {
      input.value = '';
      if (previewList) previewList.innerHTML = '';
      if (previewWrap) previewWrap.hidden = true;
    }
  }

  function updatePreviewList() {
    if (!previewList || !previewWrap) return;

    previewList.innerHTML = '';

    outputFiles.forEach((file, index) => {
      const url = URL.createObjectURL(file);
      const item = document.createElement('div');
      item.className = 'selected-photo-preview-item';

      const img = document.createElement('img');
      img.src = url;
      img.alt = file.name || ('Photo ' + (index + 1));

      const label = document.createElement('span');
      label.textContent = file.name || ('Photo ' + (index + 1));

      item.appendChild(img);
      item.appendChild(label);
      previewList.appendChild(item);

      img.addEventListener('load', () => URL.revokeObjectURL(url), { once: true });
    });

    previewWrap.hidden = outputFiles.length === 0;
  }

  function syncFilesToInput() {
    const dataTransfer = new DataTransfer();
    outputFiles.forEach((file) => dataTransfer.items.add(file));
    input.files = dataTransfer.files;
    updatePreviewList();
  }

  function draw() {
    if (!activeImage) return;

    const width = canvas.width;
    const height = canvas.height;

    ctx.clearRect(0, 0, width, height);

    const drawScale = baseScale * zoom;
    const drawWidth = activeImage.width * drawScale;
    const drawHeight = activeImage.height * drawScale;
    const maxPanX = Math.max(0, (drawWidth - width) / 2);
    const maxPanY = Math.max(0, (drawHeight - height) / 2);
    const clampedX = Math.max(-maxPanX, Math.min(maxPanX, offsetX * maxPanX / 100));
    const clampedY = Math.max(-maxPanY, Math.min(maxPanY, offsetY * maxPanY / 100));

    const x = (width - drawWidth) / 2 + clampedX;
    const y = (height - drawHeight) / 2 + clampedY;

    ctx.clearRect(0, 0, width, height);
    ctx.drawImage(activeImage, x, y, drawWidth, drawHeight);
  }

  function loadCurrentFile() {
    if (imageUrl) {
      URL.revokeObjectURL(imageUrl);
      imageUrl = null;
    }

    activeFile = sourceFiles[activeIndex] || null;
    activeImage = null;
    resetSliders();

    if (!activeFile) {
      closeModal();
      syncFilesToInput();
      return;
    }

    imageUrl = URL.createObjectURL(activeFile);
    const img = new Image();
    img.onload = function () {
      activeImage = img;
      baseScale = Math.max(canvas.width / img.width, canvas.height / img.height);
      draw();
      openModal();
    };
    img.src = imageUrl;
  }

  function moveNext() {
    activeIndex += 1;
    if (activeIndex >= sourceFiles.length) {
      closeModal();
      syncFilesToInput();
      if (imageUrl) {
        URL.revokeObjectURL(imageUrl);
        imageUrl = null;
      }
      return;
    }
    loadCurrentFile();
  }

  function acceptOriginal() {
    if (activeFile) {
      outputFiles.push(activeFile);
    }
    moveNext();
  }

  function applyCrop() {
    if (!activeFile) {
      moveNext();
      return;
    }

    canvas.toBlob(function (blob) {
      if (!blob) {
        moveNext();
        return;
      }

      const originalName = activeFile.name || ('photo-' + (activeIndex + 1) + '.png');
      const cleanName = originalName.replace(/\.[^.]+$/, '') + '.png';
      const croppedFile = new File([blob], cleanName, { type: 'image/png' });
      outputFiles.push(croppedFile);
      moveNext();
    }, 'image/png');
  }

  input.addEventListener('change', function () {
    const files = Array.from(input.files || []).filter((file) => /^image\//i.test(file.type));
    if (!files.length) {
      clearState(true);
      return;
    }

    clearState(false);
    sourceFiles = files;
    outputFiles = [];
    activeIndex = -1;
    moveNext();
  });

  zoomInput.addEventListener('input', function () {
    zoom = parseFloat(zoomInput.value || '1') || 1;
    draw();
  });

  offsetXInput.addEventListener('input', function () {
    offsetX = parseFloat(offsetXInput.value || '0') || 0;
    draw();
  });

  offsetYInput.addEventListener('input', function () {
    offsetY = parseFloat(offsetYInput.value || '0') || 0;
    draw();
  });

  closeBtn.addEventListener('click', function () {
    closeModal();
    clearState(true);
  });

  useOriginalBtn.addEventListener('click', acceptOriginal);
  applyBtn.addEventListener('click', applyCrop);
})();
