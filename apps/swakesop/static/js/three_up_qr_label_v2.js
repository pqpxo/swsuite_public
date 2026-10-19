(() => {
  const modal = document.getElementById('three-up-qr-modal');
  if (!modal) return;

  const openBtn = document.getElementById('open-three-up-qr-modal');
  const closeBtn = document.getElementById('close-three-up-qr-modal');
  const overlay = modal.querySelector('.three-up-qr-modal-overlay');
  const form = document.getElementById('three-up-qr-form');

  const generateBtn = document.getElementById('three-up-generate-btn');
  const sendBtn = document.getElementById('three-up-send-btn');
  const downloadBtn = document.getElementById('three-up-download-btn');

  const previewWrap = document.getElementById('three-up-preview-wrap');
  const previewImg = document.getElementById('three-up-preview-image');
  const previewLink = document.getElementById('three-up-image-url');
  const statusBox = document.getElementById('three-up-qr-status');

  const selectIds = ['three-up-asset-1', 'three-up-asset-2', 'three-up-asset-3'];
  const selects = selectIds
    .map((id) => document.getElementById(id))
    .filter(Boolean);

  let latestImageUrl = '';

  function setStatus(message, type = 'info') {
    if (!statusBox) return;
    statusBox.textContent = message || '';
    statusBox.dataset.state = type;
    statusBox.hidden = !message;
  }

  function setBusy(isBusy) {
    if (generateBtn) generateBtn.disabled = isBusy;
    if (sendBtn) sendBtn.disabled = isBusy || !latestImageUrl;
  }

  function openModal() {
    modal.hidden = false;
    document.body.classList.add('modal-open');
    resetPreview();
    setStatus('Select 3 assets, then generate the label image.', 'info');
  }

  function closeModal() {
    modal.hidden = true;
    document.body.classList.remove('modal-open');
  }

  function getSelectedAssetIds() {
    return selects.map((select) => (select?.value || '').trim());
  }

  function validateSelection() {
    const values = getSelectedAssetIds();

    if (values.some((value) => !value)) {
      setStatus('Please select all 3 assets.', 'error');
      return false;
    }

    if (new Set(values).size !== 3) {
      setStatus('Please select 3 different assets.', 'error');
      return false;
    }

    return true;
  }

  function resetPreview() {
    latestImageUrl = '';

    if (previewWrap) {
      previewWrap.hidden = true;
    }

    if (previewImg) {
      previewImg.src = '';
    }

    if (previewLink) {
      previewLink.href = '#';
      previewLink.textContent = '';
    }

    if (downloadBtn) {
      downloadBtn.href = '#';
      downloadBtn.classList.add('is-disabled');
      downloadBtn.setAttribute('aria-disabled', 'true');
    }

    if (sendBtn) {
      sendBtn.disabled = true;
    }
  }

  async function generateLabel() {
    if (!validateSelection()) return;

    resetPreview();
    setBusy(true);
    setStatus('Generating 3-up QR label image...', 'info');

    try {
      const response = await fetch('/api/three-up-qr/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ asset_ids: getSelectedAssetIds() })
      });

      const data = await response.json();

      if (!response.ok || !data.ok) {
        throw new Error(data.error || 'Failed to generate label image.');
      }

      latestImageUrl = data.image_url;

      if (previewImg) {
        previewImg.src = `${latestImageUrl}${latestImageUrl.includes('?') ? '&' : '?'}v=${Date.now()}`;
        previewImg.alt = 'Generated 3-up QR label preview';
      }

      if (previewLink) {
        previewLink.href = latestImageUrl;
        previewLink.textContent = latestImageUrl;
      }

      if (downloadBtn) {
        downloadBtn.href = latestImageUrl;
        downloadBtn.download = latestImageUrl.split('/').pop() || 'three_up_qr.png';
        downloadBtn.classList.remove('is-disabled');
        downloadBtn.removeAttribute('aria-disabled');
      }

      if (previewWrap) {
        previewWrap.hidden = false;
      }

      if (sendBtn) {
        sendBtn.disabled = false;
      }

      setStatus('Label image generated successfully.', 'success');
    } catch (error) {
      latestImageUrl = '';
      setStatus(error.message || 'Failed to generate label image.', 'error');
    } finally {
      setBusy(false);
    }
  }

  async function sendToPrinter() {
    if (!latestImageUrl) {
      setStatus('Generate the label image first.', 'error');
      return;
    }

    setBusy(true);
    setStatus('Sending label to printer...', 'info');

    try {
      const response = await fetch('/api/three-up-qr/print', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_url: latestImageUrl })
      });

      const data = await response.json();

      if (!response.ok || !data.ok) {
        throw new Error(data.error || 'Failed to send label to printer.');
      }

      setStatus('Label sent to printer successfully.', 'success');
    } catch (error) {
      setStatus(error.message || 'Failed to send label to printer.', 'error');
    } finally {
      setBusy(false);
    }
  }

  openBtn?.addEventListener('click', openModal);
  closeBtn?.addEventListener('click', closeModal);
  overlay?.addEventListener('click', closeModal);

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !modal.hidden) {
      closeModal();
    }
  });

  form?.addEventListener('submit', (event) => {
    event.preventDefault();
    generateLabel();
  });

  sendBtn?.addEventListener('click', sendToPrinter);

  resetPreview();
})();
