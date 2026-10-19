// version 2
(function () {
  'use strict';

  let modalApi = null;

  function injectModalStyles() {
    if (document.getElementById('qr-modal-runtime-styles')) {
      return;
    }

    const style = document.createElement('style');
    style.id = 'qr-modal-runtime-styles';
    style.textContent = `
      .qr-modal-backdrop {
        position: fixed;
        inset: 0;
        background: rgba(4, 11, 28, 0.72);
        backdrop-filter: blur(4px);
        display: none;
        align-items: center;
        justify-content: center;
        padding: 16px;
        z-index: 9999;
      }

      .qr-modal-backdrop.open {
        display: flex;
      }

      .qr-modal {
        width: min(100%, 500px);
        background: #1f2c4a;
        border: 1px solid rgba(130, 161, 224, 0.22);
        border-radius: 24px;
        box-shadow: 0 20px 50px rgba(0, 0, 0, 0.35);
        overflow: hidden;
      }

      .qr-modal-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        padding: 18px 18px 0 18px;
      }

      .qr-modal-header h2 {
        margin: 0;
        color: #f2f6ff;
        font-size: 1.15rem;
        font-weight: 700;
      }

      .qr-modal-actions {
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
      }

      .qr-modal-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-height: 38px;
        padding: 0 14px;
        border-radius: 12px;
        border: 1px solid rgba(165, 190, 255, 0.16);
        background: rgba(255, 255, 255, 0.06);
        color: #f2f6ff;
        text-decoration: none;
        cursor: pointer;
        font: inherit;
        font-weight: 700;
      }

      .qr-modal-btn:hover {
        text-decoration: none;
        filter: brightness(1.05);
      }

      .qr-modal-body {
        padding: 18px;
        display: grid;
        gap: 14px;
        justify-items: center;
      }

      .qr-modal-image-wrap {
        width: 100%;
        border-radius: 20px;
        background: #ffffff;
        padding: 18px;
        display: flex;
        justify-content: center;
        align-items: center;
      }

      .qr-modal-image {
        width: 280px;
        height: 280px;
        object-fit: contain;
        display: block;
      }

      .qr-modal-link {
        color: #a9c0ff;
        text-decoration: none;
        text-align: center;
        word-break: break-word;
      }

      .qr-modal-link:hover {
        text-decoration: underline;
      }

      body.qr-modal-open {
        overflow: hidden;
      }
    `;

    document.head.appendChild(style);
  }

  function buildModal() {
    if (modalApi) {
      return modalApi;
    }

    injectModalStyles();

    const backdrop = document.createElement('div');
    backdrop.className = 'qr-modal-backdrop';
    backdrop.setAttribute('aria-hidden', 'true');

    backdrop.innerHTML = `
      <div class="qr-modal" role="dialog" aria-modal="true" aria-labelledby="qr-modal-title">
        <div class="qr-modal-header">
          <h2 id="qr-modal-title">QR Code</h2>
          <div class="qr-modal-actions">
            <a class="qr-modal-btn qr-modal-download" href="#" download>Download</a>
            <button type="button" class="qr-modal-btn qr-modal-close">Close</button>
          </div>
        </div>
        <div class="qr-modal-body">
          <div class="qr-modal-image-wrap">
            <img class="qr-modal-image" alt="QR code">
          </div>
          <a class="qr-modal-link" href="#" target="_blank" rel="noopener"></a>
        </div>
      </div>
    `;

    document.body.appendChild(backdrop);

    const image = backdrop.querySelector('.qr-modal-image');
    const link = backdrop.querySelector('.qr-modal-link');
    const download = backdrop.querySelector('.qr-modal-download');
    const close = backdrop.querySelector('.qr-modal-close');

    function closeModal() {
      backdrop.classList.remove('open');
      backdrop.setAttribute('aria-hidden', 'true');
      document.body.classList.remove('qr-modal-open');
      image.removeAttribute('src');
    }

    function openModal(imageUrl, pageUrl, filename) {
      image.src = imageUrl;
      link.href = pageUrl;
      link.textContent = pageUrl;
      download.href = imageUrl;
      download.setAttribute('download', filename || 'qr.png');
      backdrop.classList.add('open');
      backdrop.setAttribute('aria-hidden', 'false');
      document.body.classList.add('qr-modal-open');
    }

    close.addEventListener('click', closeModal);

    backdrop.addEventListener('click', function (event) {
      if (event.target === backdrop) {
        closeModal();
      }
    });

    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && backdrop.classList.contains('open')) {
        closeModal();
      }
    });

    modalApi = { openModal, closeModal };
    return modalApi;
  }

  function toAbsoluteUrl(url) {
    if (!url) {
      return '';
    }
    try {
      return new URL(url, window.location.origin).toString();
    } catch (error) {
      return url;
    }
  }

  function getImageUrl(trigger) {
    return toAbsoluteUrl(
      trigger.dataset.qrImage ||
      trigger.dataset.qrSrc ||
      trigger.getAttribute('href') ||
      ''
    );
  }

  function getPageUrl(trigger) {
    return toAbsoluteUrl(trigger.dataset.qrLink || window.location.href);
  }

  function getFilename(trigger) {
    const explicit = trigger.dataset.qrFilename || '';
    if (explicit) {
      return explicit;
    }

    const title = (document.querySelector('.detail-hero h1, .page-header-row h1, h1')?.textContent || '').trim();
    const safe = title.replace(/[^a-z0-9]+/gi, '_').replace(/^_+|_+$/g, '').toLowerCase();
    return safe ? `${safe}_qr.png` : 'qr.png';
  }

  function shouldHandle(trigger) {
    if (!trigger) {
      return false;
    }

    if (trigger.matches('[data-qr-trigger], .qr-button, .btn-qr, .asset-action-qr')) {
      return true;
    }

    const href = trigger.getAttribute('href') || '';
    const text = (trigger.textContent || '').trim().toLowerCase();
    return href.includes('/qr.png') || text === 'qr';
  }

  function openFromTrigger(trigger, event) {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }

    const imageUrl = getImageUrl(trigger);
    if (!imageUrl) {
      return false;
    }

    buildModal().openModal(imageUrl, getPageUrl(trigger), getFilename(trigger));
    return false;
  }

  window.openQrModalFromLink = openFromTrigger;

  document.addEventListener('click', function (event) {
    const trigger = event.target.closest('a, button');
    if (!shouldHandle(trigger)) {
      return;
    }
    openFromTrigger(trigger, event);
  }, true);
})();
