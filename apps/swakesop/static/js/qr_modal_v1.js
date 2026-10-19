// version 1
(function () {
  'use strict';

  const QR_TRIGGER_SELECTORS = [
    '[data-qr-trigger]',
    '[data-qr-button]',
    '[data-qr-modal]',
    '.qr-button',
    '.btn-qr',
    '.button-qr',
    '.asset-action-qr',
    '.detail-action-qr',
    'a[href*="/qr.png"]'
  ].join(', ');

  let modalElements = null;

  function isQrLikeButton(element) {
    if (!element) {
      return false;
    }

    if (element.matches(QR_TRIGGER_SELECTORS)) {
      return true;
    }

    const text = (element.textContent || '').trim().toLowerCase();
    const className = (element.className || '').toString().toLowerCase();
    const ariaLabel = (element.getAttribute('aria-label') || '').trim().toLowerCase();
    const title = (element.getAttribute('title') || '').trim().toLowerCase();

    if (text === 'qr' || ariaLabel === 'qr' || title === 'qr') {
      return true;
    }

    return className.includes('qr');
  }

  function inferQrImageUrl() {
    const path = window.location.pathname.replace(/\/+$/, '');
    if (/^\/a\/[^/]+$/i.test(path)) {
      return `${path}/qr.png`;
    }
    return '';
  }

  function absoluteUrl(url) {
    if (!url) {
      return '';
    }
    try {
      return new URL(url, window.location.origin).toString();
    } catch (error) {
      return url;
    }
  }

  function getQrImageUrl(trigger) {
    const datasetUrl =
      trigger.dataset.qrImage ||
      trigger.dataset.qrSrc ||
      trigger.dataset.qrUrl ||
      trigger.dataset.qrPng ||
      trigger.dataset.href ||
      '';

    const href = trigger.getAttribute('href') || '';
    const candidate = datasetUrl || href || inferQrImageUrl();
    return absoluteUrl(candidate);
  }

  function getQrTargetUrl(trigger) {
    const datasetUrl =
      trigger.dataset.qrLink ||
      trigger.dataset.publicUrl ||
      trigger.dataset.assetUrl ||
      trigger.dataset.targetUrl ||
      '';

    if (datasetUrl) {
      return absoluteUrl(datasetUrl);
    }

    return window.location.href;
  }

  function getDownloadFilename(trigger, imageUrl) {
    const explicitName =
      trigger.dataset.qrFilename ||
      trigger.dataset.filename ||
      trigger.dataset.downloadName ||
      '';

    if (explicitName) {
      return explicitName;
    }

    const assetName = (document.querySelector('.detail-hero h1, h1')?.textContent || '').trim();
    const safeAssetName = assetName
      .replace(/[^a-z0-9]+/gi, '_')
      .replace(/^_+|_+$/g, '')
      .toLowerCase();

    if (safeAssetName) {
      return `${safeAssetName}_qr.png`;
    }

    try {
      const pathname = new URL(imageUrl, window.location.origin).pathname;
      const tail = pathname.split('/').filter(Boolean).pop() || 'qr.png';
      return tail.endsWith('.png') ? tail : `${tail}.png`;
    } catch (error) {
      return 'qr.png';
    }
  }

  function ensureModal() {
    if (modalElements) {
      return modalElements;
    }

    const backdrop = document.createElement('div');
    backdrop.className = 'qr-modal-backdrop';
    backdrop.setAttribute('aria-hidden', 'true');

    backdrop.innerHTML = [
      '<div class="qr-modal" role="dialog" aria-modal="true" aria-labelledby="qr-modal-title">',
      '  <div class="qr-modal-header">',
      '    <h2 id="qr-modal-title">QR Code</h2>',
      '    <div class="qr-modal-actions">',
      '      <a class="btn btn-small btn-primary qr-modal-download" href="#" download>Download</a>',
      '      <button type="button" class="btn btn-small btn-secondary qr-modal-close">Close</button>',
      '    </div>',
      '  </div>',
      '  <div class="qr-modal-body">',
      '    <img class="qr-modal-image" alt="QR code">',
      '    <a class="qr-modal-link" href="#" target="_blank" rel="noopener"></a>',
      '  </div>',
      '</div>'
    ].join('');

    document.body.appendChild(backdrop);

    const modal = backdrop.querySelector('.qr-modal');
    const image = backdrop.querySelector('.qr-modal-image');
    const link = backdrop.querySelector('.qr-modal-link');
    const closeButton = backdrop.querySelector('.qr-modal-close');
    const downloadButton = backdrop.querySelector('.qr-modal-download');

    function closeModal() {
      backdrop.classList.remove('open', 'is-open');
      backdrop.setAttribute('aria-hidden', 'true');
      document.body.classList.remove('qr-modal-open');
    }

    function openModal(imageUrl, targetUrl, filename) {
      image.src = imageUrl;
      link.href = targetUrl;
      link.textContent = targetUrl;
      downloadButton.href = imageUrl;
      downloadButton.setAttribute('download', filename || 'qr.png');
      backdrop.classList.add('open');
      backdrop.setAttribute('aria-hidden', 'false');
      document.body.classList.add('qr-modal-open');
    }

    closeButton.addEventListener('click', closeModal);

    backdrop.addEventListener('click', function (event) {
      if (event.target === backdrop) {
        closeModal();
      }
    });

    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && backdrop.getAttribute('aria-hidden') === 'false') {
        closeModal();
      }
    });

    modalElements = {
      backdrop,
      modal,
      image,
      link,
      closeButton,
      downloadButton,
      openModal,
      closeModal
    };

    return modalElements;
  }

  document.addEventListener('click', function (event) {
    const trigger = event.target.closest('a, button');

    if (!trigger) {
      return;
    }

    if (trigger.closest('.qr-modal')) {
      return;
    }

    if (!isQrLikeButton(trigger)) {
      return;
    }

    const imageUrl = getQrImageUrl(trigger);
    if (!imageUrl) {
      return;
    }

    event.preventDefault();

    const targetUrl = getQrTargetUrl(trigger);
    const filename = getDownloadFilename(trigger, imageUrl);
    const modal = ensureModal();
    modal.openModal(imageUrl, targetUrl, filename);
  });
})();
