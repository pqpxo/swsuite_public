/* ## version 3 */
(function () {
    const categorySelect = document.getElementById('category_id');
    const categoryGroups = Array.from(document.querySelectorAll('.category-field-group'));
    const emptyNotice = document.getElementById('category-field-empty');

    const scopeAliases = {
        'servers': 'servers',
        'server': 'servers',
        'raspberry_pi': 'raspberry_pi',
        'raspberry pi': 'raspberry_pi',
        'single_board_computers': 'raspberry_pi',
        'single board computers': 'raspberry_pi',
        'network_equipment': 'network_equipment',
        'network equipment': 'network_equipment',
        'cameras': 'cameras',
        'camera': 'cameras',
        'power': 'power',
        'storage': 'storage',
        'laptops': 'laptops',
        'laptop': 'laptops',
        'lxc_vms': 'lxc_vms',
        'lxc & vms': 'lxc_vms',
        'lxc_and_vms': 'lxc_vms',
        'vms': 'lxc_vms',
        'vm': 'lxc_vms',
        'cables_adapters': 'cables_adapters',
        'cables & adapters': 'cables_adapters',
        'iot_devices': 'iot_devices',
        'iot devices': 'iot_devices',
        'media_gaming': 'media_gaming',
        'media & gaming': 'media_gaming',
        'mobile_tablets': 'mobile_tablets',
        'mobile & tablets': 'mobile_tablets',
        'pcs_workstations': 'pcs_workstations',
        'pcs & workstations': 'pcs_workstations',
        'pcs': 'pcs_workstations',
        'peripherals': 'peripherals'
    };

    function slugify(value) {
        return String(value || '')
            .trim()
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, '_')
            .replace(/^_+|_+$/g, '');
    }

    function getSelectedScope() {
        if (!categorySelect) return '';
        const option = categorySelect.options[categorySelect.selectedIndex];
        const label = option ? option.textContent : '';
        const slug = slugify(label);
        return scopeAliases[slug] || slug;
    }

    function updateCategoryFieldVisibility() {
        if (!categoryGroups.length) return;

        const activeScope = getSelectedScope();
        let visibleCount = 0;

        categoryGroups.forEach((group) => {
            const scope = group.dataset.fieldScope || '';
            const shouldShow = scope === 'universal' || (activeScope && scope === activeScope);
            group.hidden = !shouldShow;
            group.classList.toggle('is-hidden-by-category', !shouldShow);
            if (shouldShow) {
                visibleCount += 1;
            }
        });

        if (emptyNotice) {
            emptyNotice.hidden = visibleCount > 0 || !activeScope;
        }
    }

    if (categorySelect) {
        categorySelect.addEventListener('change', updateCategoryFieldVisibility);
        window.requestAnimationFrame(updateCategoryFieldVisibility);
    }

    const fileInput = document.getElementById('photo-input');
    const previewWrap = document.getElementById('queued-photo-preview-wrap');
    const previewGrid = document.getElementById('queued-photo-preview-grid');
    const modal = document.getElementById('cropper-modal');
    const stage = document.getElementById('cropper-stage');
    const canvas = document.getElementById('cropper-canvas');
    const zoomInput = document.getElementById('cropper-zoom');
    const panXInput = document.getElementById('cropper-pan-x');
    const panYInput = document.getElementById('cropper-pan-y');
    const closeBtn = document.getElementById('cropper-close');
    const skipBtn = document.getElementById('cropper-skip');
    const applyBtn = document.getElementById('cropper-apply');

    if (!fileInput || !modal || !stage || !canvas || !zoomInput || !panXInput || !panYInput || !closeBtn || !skipBtn || !applyBtn) {
        return;
    }

    const ctx = canvas.getContext('2d');
    if (!ctx) {
        return;
    }

    let pendingFiles = [];
    let croppedFiles = [];
    let currentIndex = -1;
    let currentFile = null;
    let currentImage = null;
    let zoom = 1;
    let baseScale = 1;
    let offsetX = 0;
    let offsetY = 0;
    let dragging = false;
    let dragStartX = 0;
    let dragStartY = 0;
    let startOffsetX = 0;
    let startOffsetY = 0;

    function openModal() {
        modal.hidden = false;
        document.body.style.overflow = 'hidden';
    }

    function closeModal() {
        modal.hidden = true;
        document.body.style.overflow = '';
        stage.classList.remove('dragging');
        dragging = false;
    }

    function resetCropperState() {
        pendingFiles = [];
        croppedFiles = [];
        currentIndex = -1;
        currentFile = null;
        currentImage = null;
        zoom = 1;
        baseScale = 1;
        offsetX = 0;
        offsetY = 0;
        zoomInput.value = '1';
        panXInput.value = '0';
        panYInput.value = '0';
    }

    function clearQueuedFiles() {
        fileInput.value = '';
        previewGrid.innerHTML = '';
        previewWrap.hidden = true;
        resetCropperState();
        closeModal();
    }

    function clampAxis(frameSize, drawnSize, currentOffset) {
        if (drawnSize <= frameSize) {
            return (frameSize - drawnSize) / 2;
        }
        const min = frameSize - drawnSize;
        const max = 0;
        return Math.min(max, Math.max(min, currentOffset));
    }

    function clampOffsets() {
        if (!currentImage) return;
        const drawnWidth = currentImage.width * baseScale * zoom;
        const drawnHeight = currentImage.height * baseScale * zoom;
        offsetX = clampAxis(canvas.width, drawnWidth, offsetX);
        offsetY = clampAxis(canvas.height, drawnHeight, offsetY);
        syncPanSliders();
    }

    function syncPanSliders() {
        if (!currentImage) return;
        const drawnWidth = currentImage.width * baseScale * zoom;
        const drawnHeight = currentImage.height * baseScale * zoom;

        const maxHorizontalTravel = Math.max(0, drawnWidth - canvas.width);
        const maxVerticalTravel = Math.max(0, drawnHeight - canvas.height);

        if (maxHorizontalTravel > 0) {
            const minX = canvas.width - drawnWidth;
            const positionX = (offsetX - minX) / (0 - minX);
            panXInput.value = String((positionX * 2) - 1);
        } else {
            panXInput.value = '0';
        }

        if (maxVerticalTravel > 0) {
            const minY = canvas.height - drawnHeight;
            const positionY = (offsetY - minY) / (0 - minY);
            panYInput.value = String((positionY * 2) - 1);
        } else {
            panYInput.value = '0';
        }
    }

    function applyPanFromSlider(axis) {
        if (!currentImage) return;
        const drawnWidth = currentImage.width * baseScale * zoom;
        const drawnHeight = currentImage.height * baseScale * zoom;

        if (axis === 'x') {
            if (drawnWidth <= canvas.width) {
                offsetX = (canvas.width - drawnWidth) / 2;
            } else {
                const minX = canvas.width - drawnWidth;
                const sliderValue = parseFloat(panXInput.value || '0');
                const normalized = (sliderValue + 1) / 2;
                offsetX = minX + ((0 - minX) * normalized);
            }
        } else {
            if (drawnHeight <= canvas.height) {
                offsetY = (canvas.height - drawnHeight) / 2;
            } else {
                const minY = canvas.height - drawnHeight;
                const sliderValue = parseFloat(panYInput.value || '0');
                const normalized = (sliderValue + 1) / 2;
                offsetY = minY + ((0 - minY) * normalized);
            }
        }

        clampOffsets();
        draw();
    }

    function draw() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        if (!currentImage) return;

        ctx.save();
        ctx.imageSmoothingEnabled = true;
        const drawWidth = currentImage.width * baseScale * zoom;
        const drawHeight = currentImage.height * baseScale * zoom;
        ctx.drawImage(currentImage, offsetX, offsetY, drawWidth, drawHeight);
        ctx.restore();
    }

    function setupImage(img) {
        currentImage = img;
        const scaleX = canvas.width / img.width;
        const scaleY = canvas.height / img.height;
        baseScale = Math.max(scaleX, scaleY);
        zoom = 1;
        zoomInput.value = '1';

        const drawWidth = img.width * baseScale;
        const drawHeight = img.height * baseScale;
        offsetX = (canvas.width - drawWidth) / 2;
        offsetY = (canvas.height - drawHeight) / 2;
        clampOffsets();
        draw();
    }

    function renderQueuedPreviews() {
        previewGrid.innerHTML = '';
        if (!fileInput.files || !fileInput.files.length) {
            previewWrap.hidden = true;
            return;
        }

        Array.from(fileInput.files).forEach((file, index) => {
            const card = document.createElement('article');
            card.className = 'queued-photo-card';

            const img = document.createElement('img');
            img.alt = 'Queued upload ' + (index + 1);
            img.className = 'transparent-preview';

            const meta = document.createElement('div');
            meta.className = 'queued-photo-meta';

            const name = document.createElement('strong');
            name.textContent = file.name;

            const size = document.createElement('span');
            size.className = 'muted-copy';
            size.textContent = Math.max(1, Math.round(file.size / 1024)) + ' KB';

            meta.appendChild(name);
            meta.appendChild(size);
            card.appendChild(img);
            card.appendChild(meta);
            previewGrid.appendChild(card);

            const reader = new FileReader();
            reader.onload = function (event) {
                img.src = event.target.result;
            };
            reader.readAsDataURL(file);
        });

        previewWrap.hidden = false;
    }

    function processNextFile() {
        currentIndex += 1;
        if (currentIndex >= pendingFiles.length) {
            const dt = new DataTransfer();
            croppedFiles.forEach((file) => dt.items.add(file));
            fileInput.files = dt.files;
            renderQueuedPreviews();
            resetCropperState();
            closeModal();
            return;
        }

        currentFile = pendingFiles[currentIndex];
        if (!currentFile.type.startsWith('image/')) {
            croppedFiles.push(currentFile);
            processNextFile();
            return;
        }

        const reader = new FileReader();
        reader.onload = function (event) {
            const img = new Image();
            img.onload = function () {
                setupImage(img);
                openModal();
            };
            img.src = String(event.target.result || '');
        };
        reader.readAsDataURL(currentFile);
    }

    function applyCrop() {
        if (!currentImage || !currentFile) {
            processNextFile();
            return;
        }

        const output = document.createElement('canvas');
        output.width = 1400;
        output.height = 1400;
        const outputCtx = output.getContext('2d');
        if (!outputCtx) {
            croppedFiles.push(currentFile);
            processNextFile();
            return;
        }

        outputCtx.clearRect(0, 0, output.width, output.height);
        outputCtx.imageSmoothingEnabled = true;
        const scaleFactorX = output.width / canvas.width;
        const scaleFactorY = output.height / canvas.height;

        outputCtx.drawImage(
            currentImage,
            offsetX * scaleFactorX,
            offsetY * scaleFactorY,
            currentImage.width * baseScale * zoom * scaleFactorX,
            currentImage.height * baseScale * zoom * scaleFactorY
        );

        const preferredType = currentFile.type && currentFile.type !== 'image/gif' ? currentFile.type : 'image/png';
        const extension = preferredType === 'image/jpeg' ? 'jpg' : (preferredType.split('/')[1] || 'png');
        const outputName = (currentFile.name.replace(/\.[^.]+$/, '') || ('photo_' + (currentIndex + 1))) + '_cropped.' + extension;

        output.toBlob(function (blob) {
            if (!blob) {
                croppedFiles.push(currentFile);
            } else {
                croppedFiles.push(new File([blob], outputName, {
                    type: preferredType,
                    lastModified: Date.now(),
                }));
            }
            processNextFile();
        }, preferredType, preferredType === 'image/jpeg' ? 0.92 : undefined);
    }

    fileInput.addEventListener('change', function () {
        if (!fileInput.files || !fileInput.files.length) {
            previewWrap.hidden = true;
            return;
        }
        pendingFiles = Array.from(fileInput.files);
        croppedFiles = [];
        currentIndex = -1;
        processNextFile();
    });

    zoomInput.addEventListener('input', function () {
        zoom = parseFloat(zoomInput.value || '1');
        clampOffsets();
        draw();
    });

    panXInput.addEventListener('input', function () {
        applyPanFromSlider('x');
    });

    panYInput.addEventListener('input', function () {
        applyPanFromSlider('y');
    });

    stage.addEventListener('pointerdown', function (event) {
        if (!currentImage) return;
        dragging = true;
        stage.classList.add('dragging');
        dragStartX = event.clientX;
        dragStartY = event.clientY;
        startOffsetX = offsetX;
        startOffsetY = offsetY;
        stage.setPointerCapture(event.pointerId);
    });

    stage.addEventListener('pointermove', function (event) {
        if (!dragging) return;
        offsetX = startOffsetX + (event.clientX - dragStartX);
        offsetY = startOffsetY + (event.clientY - dragStartY);
        clampOffsets();
        draw();
    });

    function endDrag(event) {
        if (event && event.pointerId !== undefined) {
            try {
                stage.releasePointerCapture(event.pointerId);
            } catch (err) {
                // ignore
            }
        }
        dragging = false;
        stage.classList.remove('dragging');
    }

    stage.addEventListener('pointerup', endDrag);
    stage.addEventListener('pointercancel', endDrag);
    stage.addEventListener('pointerleave', function (event) {
        if (dragging) {
            endDrag(event);
        }
    });

    closeBtn.addEventListener('click', clearQueuedFiles);
    skipBtn.addEventListener('click', function () {
        if (currentFile) {
            croppedFiles.push(currentFile);
        }
        processNextFile();
    });
    applyBtn.addEventListener('click', applyCrop);

    modal.addEventListener('click', function (event) {
        if (event.target === modal || event.target.classList.contains('cropper-backdrop')) {
            clearQueuedFiles();
        }
    });

    window.addEventListener('keydown', function (event) {
        if (!modal.hidden && event.key === 'Escape') {
            clearQueuedFiles();
        }
    });
})();
