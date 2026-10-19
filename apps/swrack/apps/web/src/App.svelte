<!-- version 26 -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from './lib/api';
  import RackIcon from './lib/RackIcon.svelte';
  import type { CabinetDetail, CabinetSummary, ColumnPosition, EquipmentInstance, EquipmentTemplate, EquipmentTemplateWidth, ImageAsset, NetworkEndpoint, PingResult } from './lib/types';

  const UNIT_HEIGHT = 42;
  const MIN_ZOOM = 0.65;
  const MAX_ZOOM = 1.4;
  const ZOOM_STEP = 0.1;
  const RACK_HEIGHT_OPTIONS = [0.5, ...Array.from({ length: 12 }, (_, index) => index + 1)];
  const DEFAULT_CATEGORY_OPTIONS = ['General', 'Server', 'Networking', 'Storage', 'Power', 'Cabling', 'Accessory', 'Panels'];
  const EXCLUDED_CATEGORY_KEYS = new Set(['custom', 'custom equipment']);
  const CREATE_NEW_CATEGORY_VALUE = '__create_new_category__';
  const AUTO_PING_INTERVAL_MS = 2 * 60 * 1000;
  const PING_CACHE_PREFIX = 'cabinet-canvas:ping-cache:';
  const RACK_FRAME_VERTICAL_CHROME = 40;
  const EQUIPMENT_ICON_OPTIONS = [
    { key: 'generic', label: 'Generic' },
    { key: 'server', label: 'Server' },
    { key: 'network', label: 'Network' },
    { key: 'switch', label: 'Switch' },
    { key: 'storage', label: 'Storage' },
    { key: 'power', label: 'Power' },
    { key: 'patch-panel', label: 'Patch panel' },
    { key: 'shelf', label: 'Shelf' },
    { key: 'camera', label: 'Camera' },
    { key: 'accessory', label: 'Accessory' },
    { key: 'raspberry-pi', label: 'Raspberry Pi' },
    { key: 'dell', label: 'Dell' },
    { key: 'proxmox', label: 'Proxmox' },
    { key: 'router', label: 'Router' },
    { key: 'firewall', label: 'Firewall' },
    { key: 'wireless-ap', label: 'Wireless AP' },
    { key: 'ups', label: 'UPS' },
    { key: 'pdu', label: 'PDU' },
    { key: 'nas', label: 'NAS' },
    { key: 'desktop', label: 'Desktop' },
    { key: 'laptop', label: 'Laptop' },
    { key: 'kvm', label: 'KVM' },
    { key: 'modem', label: 'Modem' },
    { key: 'cable', label: 'Cable' },
    { key: 'fan', label: 'Fan' },
    { key: 'rack', label: 'Rack' },
    { key: 'blank-panel', label: 'Blank panel' },
    { key: 'virtual-machine', label: 'Virtual machine' },
    { key: 'smart-home', label: 'Smart home' },
    { key: 'printer', label: 'Printer' },
    { key: 'media-player', label: 'Media player' }
  ] as const;

  type RackIconKey = (typeof EQUIPMENT_ICON_OPTIONS)[number]['key'];

  const RACK_WIDTH_OPTIONS: { value: EquipmentTemplateWidth; label: string }[] = [
    { value: 'FULL', label: '1 across — full rack width' },
    { value: 'HALF', label: '2 across — choose side when placing' },
    { value: 'QUARTER', label: '4 across — choose column when placing' }
  ];

  type CustomEquipmentDraft = {
    name: string;
    category: string;
    manufacturer: string;
    model: string;
    heightU: number;
    widthRatio: EquipmentTemplateWidth;
    icon: RackIconKey;
    cpu: string;
    ram: string;
    storage: string;
  };

  type StickyPopupPosition = {
    x: number;
    y: number;
  };

  const STICKY_POPUP_WIDTH = 254;
  const STICKY_POPUP_HEIGHT = 286;
  const STICKY_POPUP_OFFSET = 12;

  const emptyCustomEquipmentDraft = (): CustomEquipmentDraft => ({
    name: '',
    category: 'General',
    manufacturer: '',
    model: '',
    heightU: 1,
    widthRatio: 'FULL',
    icon: 'generic',
    cpu: '',
    ram: '',
    storage: ''
  });

  let cabinets: CabinetSummary[] = [];
  let templates: EquipmentTemplate[] = [];
  type PingState = {
    status: 'idle' | 'checking' | 'reachable' | 'unreachable' | 'error';
    result?: PingResult;
    message?: string;
  };

  type PingCache = {
    states: Record<string, PingState>;
    nextPingAt: number;
  };

  let cabinet: CabinetDetail | null = null;
  let selectedInstance: EquipmentInstance | null = null;
  let pinnedDeviceId: string | null = null;
  let stickyPopupPosition: StickyPopupPosition | null = null;
  let pingStates: Record<string, PingState> = {};
  let nextAutomaticPingAt = 0;
  let nextPingSeconds = 0;
  let automaticPingTimeout: number | null = null;
  let automaticPingCountdownTimer: number | null = null;
  let automaticPingCabinetId: string | null = null;
  let highlightedCategories: string[] = [];
  let isCreatingNewCategory = false;
  let newCategoryName = '';
  let dragging: { type: 'template' | 'instance'; id: string; heightU: number; widthRatio: EquipmentTemplateWidth } | null = null;
  let rackUnitsElement: HTMLDivElement;
  let search = '';
  let zoom = 1;
  let isLoading = true;
  let isSaving = false;
  let isSavingCustomEquipment = false;
  let errorMessage = '';
  let successMessage = '';
  type ManagementDialog = 'create-cabinet' | 'delete-cabinet' | 'remove-device' | null;

  let isCustomEquipmentModalOpen = false;
  let managementDialog: ManagementDialog = null;
  let createCabinetDraft = { name: 'New Data Cabinet', heightU: 24 };
  let cabinetPendingDeletion: CabinetDetail | null = null;
  let devicePendingRemoval: EquipmentInstance | null = null;
  let isCreatingCabinet = false;
  let isDeletingCabinet = false;
  let isRemovingDevice = false;
  let customEquipmentDraft = emptyCustomEquipmentDraft();
  let customEquipmentImage: File | null = null;
  let customEquipmentImageName = '';
  let customEquipmentIcon: File | null = null;
  let customEquipmentIconName = '';

  let deviceDraft = {
    name: '',
    cpu: '',
    ram: '',
    storage: '',
    ipAddress: '',
    url: '',
    notes: ''
  };

  $: filteredTemplates = templates.filter((template) => {
    const query = search.trim().toLowerCase();
    return !query || [template.name, template.category, template.manufacturer, template.model]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()
      .includes(query);
  });
  $: categoryOptions = uniqueCategories([
    ...DEFAULT_CATEGORY_OPTIONS,
    ...templates.map((template) => template.category),
    ...(cabinet?.equipmentInstances ?? []).map((instance) => displayCategory(instance))
  ]);
  $: if (highlightedCategories.some((selectedCategory) => !categoryOptions.some((category) => categoryKey(category) === categoryKey(selectedCategory)))) {
    highlightedCategories = highlightedCategories.filter((selectedCategory) =>
      categoryOptions.some((category) => categoryKey(category) === categoryKey(selectedCategory))
    );
  }
  $: rackHeight = cabinet ? cabinet.heightU * UNIT_HEIGHT + RACK_FRAME_VERTICAL_CHROME : 0;
  $: pinnedInstance = pinnedDeviceId && cabinet
    ? cabinet.equipmentInstances.find((item) => item.id === pinnedDeviceId) ?? null
    : null;

  onMount(() => {
    void initialise();

    return () => {
      stopAutomaticPingMonitoring();
    };
  });

  async function initialise(): Promise<void> {
    isLoading = true;
    try {
      const [loadedCabinets, loadedTemplates] = await Promise.all([api.cabinets(), api.templates()]);
      cabinets = loadedCabinets;
      templates = loadedTemplates;
      if (cabinets.length > 0) await selectCabinet(cabinets[0].id);
    } catch (error) {
      setError(error);
    } finally {
      isLoading = false;
    }
  }

  async function selectCabinet(id: string): Promise<void> {
    stopAutomaticPingMonitoring();

    try {
      const loadedCabinet = await api.cabinet(id);
      cabinet = loadedCabinet;
      selectedInstance = null;
      pinnedDeviceId = null;
      stickyPopupPosition = null;
      highlightedCategories = [];

      const cache = readPingCache(loadedCabinet.id, loadedCabinet.equipmentInstances);
      pingStates = cache.states;
      startAutomaticPingMonitoring(loadedCabinet.id, cache.nextPingAt);
    } catch (error) {
      setError(error);
    }
  }

  function openCreateCabinetDialog(): void {
    createCabinetDraft = { name: 'New Data Cabinet', heightU: 24 };
    managementDialog = 'create-cabinet';
  }

  function requestDeleteCurrentCabinet(): void {
    if (!cabinet) return;

    cabinetPendingDeletion = cabinet;
    managementDialog = 'delete-cabinet';
  }

  function requestDeleteSelectedDevice(): void {
    if (!selectedInstance) return;

    devicePendingRemoval = selectedInstance;
    managementDialog = 'remove-device';
  }

  function closeManagementDialog(): void {
    if (isCreatingCabinet || isDeletingCabinet || isRemovingDevice) return;

    managementDialog = null;
    cabinetPendingDeletion = null;
    devicePendingRemoval = null;
  }

  async function createCabinetFromDialog(): Promise<void> {
    const name = createCabinetDraft.name.trim();
    const units = Number(createCabinetDraft.heightU);

    if (!name) {
      setError(new Error('Enter a cabinet name.'));
      return;
    }

    if (!Number.isInteger(units) || units < 1 || units > 64) {
      setError(new Error('Enter a whole rack height between 1U and 64U.'));
      return;
    }

    isCreatingCabinet = true;
    try {
      const created = await api.createCabinet({ name, heightU: units });
      cabinets = [created, ...cabinets];
      closeManagementDialog();
      await selectCabinet(created.id);
      notify(`Created ${created.name}.`);
    } catch (error) {
      setError(error);
    } finally {
      isCreatingCabinet = false;
    }
  }

  async function confirmDeleteCurrentCabinet(): Promise<void> {
    const deleting = cabinetPendingDeletion;
    if (!deleting) return;

    isDeletingCabinet = true;
    try {
      await api.deleteCabinet(deleting.id);
      stopAutomaticPingMonitoring();
      clearPingCache(deleting.id);

      cabinets = cabinets.filter((item) => item.id !== deleting.id);
      cabinet = null;
      selectedInstance = null;
      pinnedDeviceId = null;
      stickyPopupPosition = null;
      pingStates = {};
      highlightedCategories = [];
      managementDialog = null;
      cabinetPendingDeletion = null;

      if (cabinets.length > 0) {
        await selectCabinet(cabinets[0].id);
      }

      notify(`${deleting.name} was deleted.`);
    } catch (error) {
      setError(error);
    } finally {
      isDeletingCabinet = false;
    }
  }

  function openCustomEquipmentModal(): void {
    customEquipmentDraft = emptyCustomEquipmentDraft();
    customEquipmentImage = null;
    customEquipmentImageName = '';
    customEquipmentIcon = null;
    customEquipmentIconName = '';
    isCreatingNewCategory = false;
    newCategoryName = '';
    isCustomEquipmentModalOpen = true;
  }

  function closeCustomEquipmentModal(): void {
    if (isSavingCustomEquipment) return;
    isCustomEquipmentModalOpen = false;
  }

  function onCustomEquipmentImageSelected(event: Event): void {
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.[0] ?? null;
    input.value = '';

    customEquipmentImage = file;
    customEquipmentImageName = file?.name ?? '';
  }

  function onCustomEquipmentIconSelected(event: Event): void {
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.[0] ?? null;
    input.value = '';

    if (file && file.type !== 'image/png') {
      customEquipmentIcon = null;
      customEquipmentIconName = '';
      setError(new Error('Custom rack icons must be PNG files.'));
      return;
    }

    customEquipmentIcon = file;
    customEquipmentIconName = file?.name ?? '';
  }

  function categoryKey(category: string): string {
    return category.trim().toLowerCase();
  }

  function isExcludedCategory(category: string): boolean {
    return EXCLUDED_CATEGORY_KEYS.has(categoryKey(category));
  }

  function uniqueCategories(values: Array<string | null | undefined>): string[] {
    const categoriesByKey = new Map<string, string>();

    for (const value of values) {
      const category = value?.trim();
      if (!category || isExcludedCategory(category)) continue;

      const key = categoryKey(category);
      if (!categoriesByKey.has(key)) categoriesByKey.set(key, category);
    }

    return Array.from(categoriesByKey.values()).sort((left, right) => left.localeCompare(right));
  }

  function categoryPickerValue(): string {
    if (isCreatingNewCategory) return CREATE_NEW_CATEGORY_VALUE;
    return isExcludedCategory(customEquipmentDraft.category) ? 'General' : customEquipmentDraft.category;
  }

  function selectedCustomCategory(): string {
    const category = (isCreatingNewCategory ? newCategoryName : customEquipmentDraft.category).trim();
    return isExcludedCategory(category) ? 'General' : category;
  }

  function onCustomCategorySelected(event: Event): void {
    const selectedCategory = (event.currentTarget as HTMLSelectElement).value;

    if (selectedCategory === CREATE_NEW_CATEGORY_VALUE) {
      isCreatingNewCategory = true;
      newCategoryName = '';
      return;
    }

    isCreatingNewCategory = false;
    newCategoryName = '';
    customEquipmentDraft.category = selectedCategory;
  }

  function isCategoryHighlighted(category: string): boolean {
    return highlightedCategories.some((selectedCategory) => categoryKey(selectedCategory) === categoryKey(category));
  }

  function selectCategoryHighlight(category: string): void {
    highlightedCategories = isCategoryHighlighted(category)
      ? highlightedCategories.filter((selectedCategory) => categoryKey(selectedCategory) !== categoryKey(category))
      : [...highlightedCategories, category];
  }

  function clearCategoryHighlight(): void {
    highlightedCategories = [];
  }

  function instanceMatchesCategory(instance: EquipmentInstance, category: string): boolean {
    return categoryKey(displayCategory(instance)) === categoryKey(category);
  }

  function instanceMatchesHighlightedCategories(instance: EquipmentInstance): boolean {
    return highlightedCategories.some((category) => instanceMatchesCategory(instance, category));
  }

  function customTemplateSpecifications(iconAssetId?: string | null): Record<string, string | boolean> {
    const specifications: Record<string, string | boolean> = {
      icon: customEquipmentDraft.icon,
      isCustom: true
    };

    if (iconAssetId) specifications.iconAssetId = iconAssetId;

    const cpu = customEquipmentDraft.cpu.trim();
    const ram = customEquipmentDraft.ram.trim();
    const storage = customEquipmentDraft.storage.trim();

    if (cpu) specifications.cpu = cpu;
    if (ram) specifications.ram = ram;
    if (storage) specifications.storage = storage;

    return specifications;
  }

  async function saveCustomEquipment(): Promise<void> {
    const name = customEquipmentDraft.name.trim();
    const category = selectedCustomCategory();

    if (!name) {
      setError(new Error('Enter a name for the custom equipment.'));
      return;
    }

    if (!category) {
      setError(new Error('Enter or select an equipment category.'));
      return;
    }

    isSavingCustomEquipment = true;
    try {
      let frontAssetId: string | null = null;
      let iconAssetId: string | null = null;

      if (customEquipmentImage) {
        const asset: ImageAsset = await api.uploadAsset(customEquipmentImage);
        frontAssetId = asset.id;
      }

      if (customEquipmentIcon) {
        const asset: ImageAsset = await api.uploadIconAsset(customEquipmentIcon);
        iconAssetId = asset.id;
      }

      const template = await api.createTemplate({
        name,
        category,
        manufacturer: customEquipmentDraft.manufacturer.trim() || null,
        model: customEquipmentDraft.model.trim() || null,
        heightU: Number(customEquipmentDraft.heightU),
        widthRatio: customEquipmentDraft.widthRatio,
        frontAssetId,
        specifications: customTemplateSpecifications(iconAssetId)
      });

      templates = [...templates, template].sort((a, b) => a.name.localeCompare(b.name));
      customEquipmentDraft.category = category;
      isCreatingNewCategory = false;
      newCategoryName = '';
      isCustomEquipmentModalOpen = false;
      notify(`${template.name} was added to your equipment library.`);
    } catch (error) {
      setError(error);
    } finally {
      isSavingCustomEquipment = false;
    }
  }

  function beginTemplateDrag(event: DragEvent, template: EquipmentTemplate): void {
    dragging = { type: 'template', id: template.id, heightU: template.heightU, widthRatio: template.widthRatio };
    event.dataTransfer?.setData('text/plain', `template:${template.id}`);
    if (event.dataTransfer) event.dataTransfer.effectAllowed = 'copy';
  }

  function beginInstanceDrag(event: DragEvent, instance: EquipmentInstance): void {
    dragging = {
      type: 'instance',
      id: instance.id,
      heightU: instance.heightU,
      widthRatio: templateWidthFromColumnPosition(instance.columnPosition)
    };
    event.dataTransfer?.setData('text/plain', `instance:${instance.id}`);
    if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move';
  }

  function clearDrag(): void {
    dragging = null;
  }

  function widthSlots(widthRatio: EquipmentTemplateWidth | string): 1 | 2 | 4 {
    switch (widthRatio) {
      case 'HALF':
      case 'LEFT':
      case 'RIGHT':
        return 2;
      case 'QUARTER':
      case 'QUARTER_1':
      case 'QUARTER_2':
      case 'QUARTER_3':
      case 'QUARTER_4':
        return 4;
      case 'FULL':
      default:
        return 1;
    }
  }

  function templateWidthFromColumnPosition(position: ColumnPosition): EquipmentTemplateWidth {
    const slots = widthSlots(position);
    return slots === 4 ? 'QUARTER' : slots === 2 ? 'HALF' : 'FULL';
  }

  function columnPositionFromDrop(event: DragEvent, widthRatio: EquipmentTemplateWidth | string): ColumnPosition {
    if (!rackUnitsElement) return 'FULL';

    const slots = widthSlots(widthRatio);
    if (slots === 1) return 'FULL';

    const rect = rackUnitsElement.getBoundingClientRect();
    const innerLeft = rect.left;
    const innerWidth = Math.max(1, rect.width);
    const relativeX = Math.max(0, Math.min(0.999999, (event.clientX - innerLeft) / innerWidth));
    const targetColumn = Math.floor(relativeX * slots);

    if (slots === 2) return targetColumn === 0 ? 'LEFT' : 'RIGHT';

    return (['QUARTER_1', 'QUARTER_2', 'QUARTER_3', 'QUARTER_4'] as const)[targetColumn];
  }

  function isHalfUHeight(heightU: number): boolean {
    return Math.abs(heightU - 0.5) < 0.001;
  }

  function formatRackUnit(value: number): string {
    return Number.isInteger(value) ? String(value) : value.toFixed(1).replace(/\.0$/, '');
  }

  function rackUnitLabels(instance: EquipmentInstance): string[] {
    if (Number.isInteger(instance.heightU) && Number.isInteger(instance.rackStartU)) {
      return Array.from({ length: Math.round(instance.heightU) }, (_, offset) => `U${formatRackUnit(instance.rackStartU + offset)}`);
    }

    return [`U${formatRackUnit(instance.rackStartU)}`];
  }

  function rackRangeLabel(instance: EquipmentInstance): string {
    const labels = rackUnitLabels(instance);

    if (labels.length <= 1) return labels[0] ?? `U${formatRackUnit(instance.rackStartU)}`;

    return `${labels[0]}–${labels[labels.length - 1].replace(/^U/, '')}`;
  }

  function rackUnitFromEvent(event: DragEvent, heightU: number): number {
    if (!cabinet || !rackUnitsElement) return 1;

    const rect = rackUnitsElement.getBoundingClientRect();
    const scaledUnitHeight = UNIT_HEIGHT * zoom;
    const maximumTop = Math.max(0, cabinet.heightU - heightU);
    const rawTop = Math.max(0, Math.min(maximumTop, (event.clientY - rect.top) / scaledUnitHeight));
    const snapStep = isHalfUHeight(heightU) ? 0.5 : 1;
    const snappedTop = Math.max(0, Math.min(maximumTop, Math.floor(rawTop / snapStep) * snapStep));
    const rackStartU = cabinet.heightU - snappedTop - heightU + 1;

    return Math.round(rackStartU * 2) / 2;
  }

  async function handleRackDrop(event: DragEvent): Promise<void> {
    event.preventDefault();
    if (!cabinet || !dragging) return;

    const rackStartU = rackUnitFromEvent(event, dragging.heightU);
    const drag = dragging;
    const columnPosition = columnPositionFromDrop(event, drag.widthRatio);
    clearDrag();

    try {
      if (drag.type === 'template') {
        const template = templates.find((item) => item.id === drag.id);
        if (!template) return;
        const created = await api.createInstance({
          cabinetId: cabinet.id,
          templateId: template.id,
          name: template.name,
          rackStartU,
          heightU: template.heightU,
          columnPosition,
          face: 'FRONT',
          specifications: template.specifications
        });
        await reloadCabinetAndSelect(created.id);
        notify(`${template.name} installed at U${formatRackUnit(rackStartU)}.`);
      } else {
        const updated = await api.updateInstance(drag.id, { rackStartU, columnPosition });
        await reloadCabinetAndSelect(updated.id);
        notify(`${updated.name} moved to U${formatRackUnit(rackStartU)}.`);
      }
    } catch (error) {
      setError(error);
    }
  }

  async function reloadCabinetAndSelect(instanceId?: string): Promise<void> {
    if (!cabinet) return;

    cabinet = await api.cabinet(cabinet.id);
    retainKnownPingStates(cabinet.equipmentInstances);

    if (instanceId) {
      const found = cabinet.equipmentInstances.find((item) => item.id === instanceId) ?? null;
      if (found) selectInstance(found);
    }

    cabinets = cabinets.map((item) => item.id === cabinet?.id
      ? { ...item, _count: { equipmentInstances: cabinet.equipmentInstances.length } }
      : item);
  }

  function selectInstance(instance: EquipmentInstance): void {
    selectedInstance = instance;
    const endpoint = primaryEndpoint(instance);
    deviceDraft = {
      name: instance.name,
      cpu: valueAsText(instance.specifications.cpu),
      ram: valueAsText(instance.specifications.ram),
      storage: valueAsText(instance.specifications.storage),
      ipAddress: endpoint?.ipAddress ?? '',
      url: endpoint?.url ?? '',
      notes: instance.notes ?? ''
    };
  }

  function stickyPopupPositionFor(event: MouseEvent): StickyPopupPosition {
    const trigger = event.currentTarget instanceof HTMLElement ? event.currentTarget : null;
    const rect = trigger?.getBoundingClientRect();
    const clickX = event.clientX || (rect ? rect.left + rect.width / 2 : window.innerWidth / 2);
    const clickY = event.clientY || (rect ? rect.top + rect.height / 2 : window.innerHeight / 2);

    const maximumX = Math.max(STICKY_POPUP_OFFSET, window.innerWidth - STICKY_POPUP_WIDTH - STICKY_POPUP_OFFSET);
    const maximumY = Math.max(STICKY_POPUP_OFFSET, window.innerHeight - STICKY_POPUP_HEIGHT - STICKY_POPUP_OFFSET);

    return {
      x: Math.round(Math.max(STICKY_POPUP_OFFSET, Math.min(clickX + STICKY_POPUP_OFFSET, maximumX))),
      y: Math.round(Math.max(STICKY_POPUP_OFFSET, Math.min(clickY + STICKY_POPUP_OFFSET, maximumY)))
    };
  }

  function stickyPopupStyle(): string {
    if (!stickyPopupPosition) return '';

    return `left: ${stickyPopupPosition.x}px; top: ${stickyPopupPosition.y}px;`;
  }

  function openDevice(instance: EquipmentInstance, event: MouseEvent): void {
    selectInstance(instance);

    if (isBlankPanel(instance)) {
      pinnedDeviceId = null;
      stickyPopupPosition = null;
      return;
    }

    pinnedDeviceId = instance.id;
    stickyPopupPosition = stickyPopupPositionFor(event);
  }

  function closeDeviceDetails(): void {
    selectedInstance = null;
    pinnedDeviceId = null;
    stickyPopupPosition = null;
  }

  function closePinnedDevice(): void {
    pinnedDeviceId = null;
    stickyPopupPosition = null;
  }

  function handleGlobalPointerDown(event: PointerEvent): void {
    if (!pinnedDeviceId) return;
    const target = event.target;
    if (!(target instanceof Element)) {
      closePinnedDevice();
      return;
    }

    if (target.closest('.rack-device, .device-sticky-popup')) return;
    closePinnedDevice();
  }

  async function saveSelectedDevice(): Promise<void> {
    if (!selectedInstance) return;
    isSaving = true;
    try {
      const endpoint = primaryEndpoint(selectedInstance);
      const updated = await api.updateInstance(selectedInstance.id, {
        name: deviceDraft.name.trim(),
        specifications: {
          ...selectedInstance.specifications,
          cpu: deviceDraft.cpu.trim(),
          ram: deviceDraft.ram.trim(),
          storage: deviceDraft.storage.trim()
        },
        notes: deviceDraft.notes.trim(),
        networkEndpoint: {
          label: endpoint?.label ?? 'Primary frontend',
          ipAddress: deviceDraft.ipAddress.trim() || null,
          url: deviceDraft.url.trim() || null,
          protocol: deviceDraft.url.trim() ? 'HTTPS' : null,
          isPrimary: true
        }
      });
      clearPingState(updated.id);
      await reloadCabinetAndSelect(updated.id);
      notify('Device details saved.');
    } catch (error) {
      setError(error);
    } finally {
      isSaving = false;
    }
  }

  async function confirmDeleteSelectedDevice(): Promise<void> {
    const removing = devicePendingRemoval;
    if (!removing) return;

    isRemovingDevice = true;
    try {
      await api.deleteInstance(removing.id);
      clearPingState(removing.id);

      if (selectedInstance?.id === removing.id) {
        selectedInstance = null;
      }

      if (pinnedDeviceId === removing.id) {
        pinnedDeviceId = null;
        stickyPopupPosition = null;
      }

      managementDialog = null;
      devicePendingRemoval = null;
      await reloadCabinetAndSelect();
      notify('Device removed from cabinet.');
    } catch (error) {
      setError(error);
    } finally {
      isRemovingDevice = false;
    }
  }

  async function deleteCustomTemplate(template: EquipmentTemplate): Promise<void> {
    if (!isCustomTemplate(template)) return;

    try {
      await api.deleteTemplate(template.id);
      templates = templates.filter((item) => item.id !== template.id);

      if (cabinet) {
        await reloadCabinetAndSelect(selectedInstance?.id);
      }

      notify(`${template.name} was deleted from the equipment library.`);
    } catch (error) {
      setError(error);
    }
  }

  function isCustomTemplate(template: EquipmentTemplate): boolean {
    return template.specifications.isCustom === true || valueAsText(template.specifications.isCustom).toLowerCase() === 'true'
      || !template.slug.startsWith('generic-');
  }

  function primaryEndpoint(instance: EquipmentInstance): NetworkEndpoint | undefined {
    return instance.networkEndpoints.find((endpoint) => endpoint.isPrimary) ?? instance.networkEndpoints[0];
  }

  function optimisedAssetUrl(assetId: unknown): string | null {
    const identifier = valueAsText(assetId).trim();
    return identifier ? `${import.meta.env.BASE_URL.replace(/\/+$/, '')}/assets/optimised/${identifier}.webp` : null;
  }

  function assetUrl(instance: EquipmentInstance): string | null {
    return optimisedAssetUrl(instance.imageAssetId ?? instance.template?.frontAssetId);
  }

  function templateAssetUrl(template: EquipmentTemplate): string | null {
    return optimisedAssetUrl(template.frontAssetId);
  }

  function templateIconAssetUrl(template: EquipmentTemplate): string | null {
    return optimisedAssetUrl(template.specifications.iconAssetId);
  }

  function deviceIconAssetUrl(instance: EquipmentInstance): string | null {
    return optimisedAssetUrl(instance.specifications.iconAssetId ?? instance.template?.specifications.iconAssetId);
  }

  function isBlankPanelSpecifications(specifications: Record<string, unknown> | null | undefined): boolean {
    const value = specifications?.isBlankPanel;
    return value === true || valueAsText(value).trim().toLowerCase() === 'true';
  }

  function isBlankPanelTemplate(template: EquipmentTemplate | null | undefined): boolean {
    return isBlankPanelSpecifications(template?.specifications);
  }

  function isBlankPanel(instance: EquipmentInstance): boolean {
    return isBlankPanelSpecifications(instance.specifications) || isBlankPanelTemplate(instance.template);
  }

  function displayCategory(instance: EquipmentInstance): string {
    return instance.template?.category ?? 'General';
  }

  function deviceTop(instance: EquipmentInstance): number {
    if (!cabinet) return 0;
    return (cabinet.heightU - instance.rackStartU - instance.heightU + 1) * UNIT_HEIGHT;
  }

  function deviceStyle(instance: EquipmentInstance): string {
    const top = deviceTop(instance);
    const column = instance.columnPosition as ColumnPosition;
    const dimensions: Record<ColumnPosition, string> = {
      FULL: 'left: 4%; width: 92%;',
      LEFT: 'left: 4%; width: 45%;',
      RIGHT: 'left: 51%; width: 45%;',
      QUARTER_1: 'left: 4%; width: 22.25%;',
      QUARTER_2: 'left: 27.25%; width: 22.25%;',
      QUARTER_3: 'left: 50.5%; width: 22.25%;',
      QUARTER_4: 'left: 73.75%; width: 22.25%;'
    };

    // The button deliberately renders at 105% height. Reducing its containing
    // box keeps a consistent 2px visual gap between adjacent rack devices.
    const deviceShellHeight = (instance.heightU * UNIT_HEIGHT - 2) / 1.05;

    return `top: ${top}px; height: ${deviceShellHeight}px; ${dimensions[column] ?? dimensions.FULL}`;
  }

  function widthRatioLabel(widthRatio: EquipmentTemplateWidth | string): string {
    const slots = widthSlots(widthRatio);
    return slots === 4 ? '4 across' : slots === 2 ? '2 across' : '1 across';
  }

  function valueAsText(value: unknown): string {
    return value === undefined || value === null ? '' : String(value);
  }

  function iconKey(iconKey: string | null | undefined): RackIconKey | null {
    return EQUIPMENT_ICON_OPTIONS.find((icon) => icon.key === iconKey)?.key ?? null;
  }

  function brandedIcon(...values: Array<string | null | undefined>): RackIconKey | null {
    const text = values.filter(Boolean).join(' ').toLowerCase();
    if (text.includes('raspberry pi') || text.includes('raspberrypi')) return 'raspberry-pi';
    if (text.includes('proxmox')) return 'proxmox';
    if (text.includes('dell')) return 'dell';
    return null;
  }

  function deviceIconFromCategory(category: string): RackIconKey {
    const categoryName = category.toLowerCase();
    if (categoryName.includes('network')) return 'network';
    if (categoryName.includes('storage')) return 'storage';
    if (categoryName.includes('power')) return 'power';
    if (categoryName.includes('cabl')) return 'patch-panel';
    if (categoryName.includes('server')) return 'server';
    if (categoryName.includes('access')) return 'accessory';
    return 'generic';
  }

  function templateIcon(template: EquipmentTemplate): RackIconKey {
    return iconKey(valueAsText(template.specifications.icon))
      ?? brandedIcon(template.manufacturer, template.model, template.name)
      ?? deviceIconFromCategory(template.category);
  }

  function deviceIcon(instance: EquipmentInstance): RackIconKey {
    return iconKey(valueAsText(instance.specifications.icon))
      ?? brandedIcon(instance.template?.manufacturer, instance.template?.model, instance.name)
      ?? deviceIconFromCategory(displayCategory(instance));
  }

  function hasPrimaryIp(instance: EquipmentInstance): boolean {
    return Boolean(primaryEndpoint(instance)?.ipAddress?.trim());
  }

  function pingCacheKey(cabinetId: string): string {
    return `${PING_CACHE_PREFIX}${cabinetId}`;
  }

  function readPingCache(cabinetId: string, instances: EquipmentInstance[]): PingCache {
    const fallback: PingCache = { states: {}, nextPingAt: 0 };

    try {
      const rawCache = window.localStorage.getItem(pingCacheKey(cabinetId));
      if (!rawCache) return fallback;

      const parsedCache = JSON.parse(rawCache) as Partial<PingCache>;
      const knownInstanceIds = new Set(instances.map((instance) => instance.id));
      const states: Record<string, PingState> = {};

      for (const [instanceId, state] of Object.entries(parsedCache.states ?? {})) {
        if (!knownInstanceIds.has(instanceId) || !state || typeof state !== 'object') continue;

        const parsedState = state as PingState;
        if (!['reachable', 'unreachable', 'error'].includes(parsedState.status)) continue;
        states[instanceId] = parsedState;
      }

      return {
        states,
        nextPingAt: typeof parsedCache.nextPingAt === 'number' ? parsedCache.nextPingAt : 0
      };
    } catch {
      return fallback;
    }
  }

  function persistPingCache(): void {
    if (!cabinet) return;

    try {
      const stableStates = Object.entries(pingStates).reduce<Record<string, PingState>>((states, [instanceId, state]) => {
        if (state.status !== 'checking' && state.status !== 'idle') {
          states[instanceId] = state;
        }

        return states;
      }, {});

      window.localStorage.setItem(
        pingCacheKey(cabinet.id),
        JSON.stringify({ states: stableStates, nextPingAt: nextAutomaticPingAt } satisfies PingCache)
      );
    } catch {
      // Storage is optional. Automatic pings still continue during this session.
    }
  }

  function clearPingCache(cabinetId: string): void {
    try {
      window.localStorage.removeItem(pingCacheKey(cabinetId));
    } catch {
      // No action needed when browser storage is unavailable.
    }
  }

  function setPingState(instanceId: string, state: PingState, persist = true): void {
    pingStates = { ...pingStates, [instanceId]: state };
    if (persist) persistPingCache();
  }

  function clearPingState(instanceId: string): void {
    const { [instanceId]: _discarded, ...remainingStates } = pingStates;
    pingStates = remainingStates;
    persistPingCache();
  }

  function retainKnownPingStates(instances: EquipmentInstance[]): void {
    const knownInstanceIds = new Set(instances.map((instance) => instance.id));
    pingStates = Object.entries(pingStates).reduce<Record<string, PingState>>((states, [instanceId, state]) => {
      if (knownInstanceIds.has(instanceId)) {
        states[instanceId] = state;
      }

      return states;
    }, {});
    persistPingCache();
  }

  function updatePingCountdown(): void {
    nextPingSeconds = nextAutomaticPingAt
      ? Math.max(0, Math.ceil((nextAutomaticPingAt - Date.now()) / 1000))
      : 0;
  }

  function stopAutomaticPingMonitoring(): void {
    if (automaticPingTimeout !== null) {
      window.clearTimeout(automaticPingTimeout);
      automaticPingTimeout = null;
    }

    if (automaticPingCountdownTimer !== null) {
      window.clearInterval(automaticPingCountdownTimer);
      automaticPingCountdownTimer = null;
    }

    automaticPingCabinetId = null;
    nextAutomaticPingAt = 0;
    nextPingSeconds = 0;
  }

  function scheduleAutomaticPing(cabinetId: string, pingAt: number): void {
    if (!cabinet || cabinet.id !== cabinetId) return;

    if (automaticPingTimeout !== null) {
      window.clearTimeout(automaticPingTimeout);
    }

    automaticPingCabinetId = cabinetId;
    nextAutomaticPingAt = pingAt;
    updatePingCountdown();
    persistPingCache();

    automaticPingTimeout = window.setTimeout(() => {
      automaticPingTimeout = null;
      void runAutomaticPingCycle(cabinetId);
    }, Math.max(0, pingAt - Date.now()));
  }

  function startAutomaticPingMonitoring(cabinetId: string, cachedNextPingAt: number): void {
    stopAutomaticPingMonitoring();

    automaticPingCabinetId = cabinetId;
    automaticPingCountdownTimer = window.setInterval(updatePingCountdown, 1000);

    const pingAt = cachedNextPingAt > Date.now() ? cachedNextPingAt : Date.now();
    scheduleAutomaticPing(cabinetId, pingAt);
  }

  async function runAutomaticPingCycle(cabinetId: string): Promise<void> {
    if (!cabinet || cabinet.id !== cabinetId || automaticPingCabinetId !== cabinetId) return;

    const pingTargets = cabinet.equipmentInstances.filter((instance) => hasPrimaryIp(instance));
    await Promise.all(pingTargets.map((instance) => pingDevice(instance, cabinetId)));

    if (!cabinet || cabinet.id !== cabinetId || automaticPingCabinetId !== cabinetId) return;
    scheduleAutomaticPing(cabinetId, Date.now() + AUTO_PING_INTERVAL_MS);
  }

  function pingStateFor(instance: EquipmentInstance): PingState {
    return pingStates[instance.id] ?? { status: 'idle' };
  }

  function pingLedState(instance: EquipmentInstance): 'ping-idle' | 'ping-checking' | 'ping-reachable' | 'ping-unreachable' {
    const status = pingStateFor(instance).status;

    if (status === 'unreachable' || status === 'error') return 'ping-unreachable';
    if (status === 'checking') return 'ping-checking';
    if (status === 'reachable') return 'ping-reachable';

    return 'ping-idle';
  }

  function formatPingCountdown(totalSeconds: number): string {
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  }

  function nextPingText(instance: EquipmentInstance): string {
    if (pingStateFor(instance).status === 'checking') return 'Automatic check running';
    return `Next ping in ${formatPingCountdown(nextPingSeconds)}`;
  }

  function pingStatusText(instance: EquipmentInstance): string {
    const state = pingStateFor(instance);
    if (state.status === 'checking') return 'Pinging…';
    if (state.status === 'reachable') return state.result?.latencyMs !== null && state.result?.latencyMs !== undefined
      ? `Reachable · ${state.result.latencyMs.toFixed(1)} ms`
      : 'Reachable';
    if (state.status === 'unreachable') return state.result?.message ?? 'No reply';
    if (state.status === 'error') return state.message ?? 'Ping unavailable';
    return 'Waiting for automatic ping';
  }

  async function pingDevice(instance: EquipmentInstance, expectedCabinetId = cabinet?.id): Promise<void> {
    if (!hasPrimaryIp(instance) || !expectedCabinetId || cabinet?.id !== expectedCabinetId) return;

    setPingState(instance.id, { status: 'checking' }, false);

    try {
      const result = await api.pingInstance(instance.id);
      if (cabinet?.id !== expectedCabinetId) return;

      setPingState(instance.id, {
        status: result.reachable ? 'reachable' : 'unreachable',
        result
      });
    } catch (error) {
      if (cabinet?.id !== expectedCabinetId) return;

      setPingState(instance.id, {
        status: 'error',
        message: error instanceof Error ? error.message : 'Ping failed.'
      });
    }
  }

  function setError(error: unknown): void {
    errorMessage = error instanceof Error ? error.message : 'An unexpected error occurred.';
    successMessage = '';
    window.setTimeout(() => { errorMessage = ''; }, 6000);
  }

  function notify(message: string): void {
    successMessage = message;
    errorMessage = '';
    window.setTimeout(() => { successMessage = ''; }, 3500);
  }
</script>

<svelte:head>
  <title>SWRack</title>
</svelte:head>

<svelte:window onpointerdown={handleGlobalPointerDown} />

<div class="app-shell">
  <header class="topbar">
    <div class="brand-lockup">
      <div class="brand-mark">
        <img src="{import.meta.env.BASE_URL}swrack-logo.png?v=27" alt="SWRack logo" />
      </div>
      <div>
        <h1>SWRack</h1>
        <p>Visual rack documentation</p>
      </div>
    </div>

    <div class="topbar-actions">
      <label class="cabinet-picker">
        <span>Cabinet</span>
        <select value={cabinet?.id ?? ''} onchange={(event) => selectCabinet((event.currentTarget as HTMLSelectElement).value)}>
          {#each cabinets as item}
            <option value={item.id}>{item.name} · {item.heightU}U</option>
          {/each}
        </select>
      </label>
      {#if cabinet}
        <button class="button danger" type="button" onclick={requestDeleteCurrentCabinet}>Delete cabinet</button>
      {/if}
      <button class="button secondary" type="button" onclick={openCreateCabinetDialog}>+ New cabinet</button>
    </div>
  </header>

  {#if errorMessage || successMessage}
    <div class:notice-error={Boolean(errorMessage)} class:notice-success={Boolean(successMessage)} class="notice" role="status">
      {errorMessage || successMessage}
    </div>
  {/if}

  <main class="workspace">
    <aside class="library-panel">
      <div class="panel-heading library-heading">
        <div>
          <p class="eyebrow">Equipment library</p>
          <h2>Drag into cabinet</h2>
        </div>
        <button class="button secondary compact-button" onclick={openCustomEquipmentModal}>+ Custom</button>
      </div>

      <p class="library-help">Drag equipment into the rack. For 2- or 4-across items, drop on the side or column you want to use.</p>
      <input class="search-box" bind:value={search} placeholder="Search equipment" aria-label="Search equipment" />

      <div class="library-list">
        {#each filteredTemplates as template}
          <div class="library-item-wrap" class:has-template-delete={isCustomTemplate(template)}>
            <button
              class="library-item"
              draggable="true"
              ondragstart={(event) => beginTemplateDrag(event, template)}
              ondragend={clearDrag}
              title={`Drag ${template.name} into the cabinet`}
            >
              {#if templateAssetUrl(template)}
                <img src={templateAssetUrl(template) ?? ''} alt="" />
              {:else if templateIconAssetUrl(template)}
                <span class="template-glyph"><img class="custom-icon-image library-custom-icon" src={templateIconAssetUrl(template) ?? ''} alt="" /></span>
              {:else}
                <span class="template-glyph"><RackIcon icon={templateIcon(template)} /></span>
              {/if}
              <span class="library-item-copy">
                <strong>{template.name}</strong>
                <small>{template.category} · {template.heightU}U · {widthRatioLabel(template.widthRatio)}</small>
              </span>
              <span class="drag-mark">⠿</span>
            </button>
            {#if isCustomTemplate(template)}
              <button
                class="template-delete-button"
                type="button"
                onclick={() => { void deleteCustomTemplate(template); }}
                aria-label={`Delete ${template.name} from the equipment library`}
                title="Delete custom equipment"
              >
                ×
              </button>
            {/if}
          </div>
        {:else}
          <div class="empty-state">No equipment templates match your search.</div>
        {/each}
      </div>

      <div class="library-footnote">
        <span class="status-dot"></span>
        {templates.length} reusable templates
      </div>
    </aside>

    <section class="canvas-panel">
      <div class="rack-scroll-area">
        {#if cabinet && categoryOptions.length > 0}
          <div class="category-highlight-controls" aria-label="Highlight rack equipment by one or more categories">
            {#each categoryOptions as category}
              <button
                type="button"
                class:category-filter-active={isCategoryHighlighted(category)}
                class="category-filter-button"
                onclick={() => selectCategoryHighlight(category)}
                aria-pressed={isCategoryHighlighted(category)}
              >
                {category}
              </button>
            {/each}
            <button
              type="button"
              class="category-filter-clear"
              disabled={highlightedCategories.length === 0}
              onclick={clearCategoryHighlight}
            >
              Clear
            </button>
          </div>
        {/if}

        <div class="zoom-controls rack-zoom-controls" aria-label="Rack zoom controls">
          <button class="icon-button" onclick={() => zoom = Math.max(MIN_ZOOM, Number((zoom - ZOOM_STEP).toFixed(2)))} aria-label="Zoom out">−</button>
          <span>{Math.round(zoom * 100)}%</span>
          <button class="icon-button" onclick={() => zoom = Math.min(MAX_ZOOM, Number((zoom + ZOOM_STEP).toFixed(2)))} aria-label="Zoom in">+</button>
        </div>

        {#if isLoading}
          <div class="rack-loading">Loading saved cabinet…</div>
        {:else if cabinet}
          <div class="rack-scale" style={`transform: scale(${zoom}); height: ${rackHeight * zoom}px;`}>
            <div
              class:drag-active={Boolean(dragging)}
              class="rack-frame"
              role="application"
              aria-label="Interactive cabinet rack elevation"
              style={`height: ${rackHeight}px;`}
              ondragover={(event) => event.preventDefault()}
              ondrop={handleRackDrop}
            >
              <div class="rack-hole-strip left-hole-strip" aria-hidden="true">
                {#each Array(cabinet.heightU) as _}
                  <div class="rack-hole-slot">
                    <span class="rack-hole"></span>
                    <span class="rack-hole"></span>
                    <span class="rack-hole"></span>
                  </div>
                {/each}
              </div>
              <div class="rack-hole-strip right-hole-strip" aria-hidden="true">
                {#each Array(cabinet.heightU) as _}
                  <div class="rack-hole-slot">
                    <span class="rack-hole"></span>
                    <span class="rack-hole"></span>
                    <span class="rack-hole"></span>
                  </div>
                {/each}
              </div>

              <div class="rack-units" aria-hidden="true" bind:this={rackUnitsElement}>
                {#each Array(cabinet.heightU) as _}
                  <div class="rack-unit"></div>
                {/each}
              </div>

              <div class="device-layer">
                {#each cabinet.equipmentInstances.filter((item) => item.face === 'FRONT') as instance}
                  <div
                    class:blank-panel-device={isBlankPanel(instance)}
                    class:half-u-device={isHalfUHeight(instance.heightU)}
                    class:category-muted={highlightedCategories.length > 0 && !instanceMatchesHighlightedCategories(instance)}
                    class:category-highlighted={highlightedCategories.length > 0 && instanceMatchesHighlightedCategories(instance)}
                    class:selected-device={selectedInstance?.id === instance.id}
                    class={`rack-device status-${instance.status.toLowerCase()}`}
                    style={deviceStyle(instance)}
                  >
                    {#if isBlankPanel(instance)}
                      <button
                        class="device-select-button blank-panel-button"
                        type="button"
                        draggable="true"
                        ondragstart={(event) => beginInstanceDrag(event, instance)}
                        ondragend={clearDrag}
                        onclick={(event) => openDevice(instance, event)}
                        aria-label={`Inspect blank panel at U${formatRackUnit(instance.rackStartU)}`}
                      >
                        <span class="device-u-label" class:multi-u-label={rackUnitLabels(instance).length > 1}>
                          {#each rackUnitLabels(instance) as rackUnitLabel}
                            <span>{rackUnitLabel}</span>
                          {/each}
                        </span>
                      </button>
                    {:else}
                      <button
                        class="device-select-button"
                        type="button"
                        draggable="true"
                        ondragstart={(event) => beginInstanceDrag(event, instance)}
                        ondragend={clearDrag}
                        onclick={(event) => openDevice(instance, event)}
                        aria-label={`Open ${instance.name} details`}
                      >
                        <span class="device-u-label" class:multi-u-label={rackUnitLabels(instance).length > 1}>
                          {#each rackUnitLabels(instance) as rackUnitLabel}
                            <span>{rackUnitLabel}</span>
                          {/each}
                        </span>
                        {#if assetUrl(instance)}
                          <img class="device-image" src={assetUrl(instance) ?? ''} alt="" />
                        {:else}
                          <span class="device-glyph">
                            {#if deviceIconAssetUrl(instance)}
                              <img class="custom-icon-image device-custom-icon" src={deviceIconAssetUrl(instance) ?? ''} alt="" />
                            {:else}
                              <RackIcon icon={deviceIcon(instance)} />
                            {/if}
                          </span>
                        {/if}
                        <span class="device-copy">
                          <strong>{instance.name}</strong>
                          <small>{displayCategory(instance)} · {instance.heightU}U</small>
                        </span>
                        {#if hasPrimaryIp(instance)}
                          <span
                            class="device-led"
                            class:ping-idle={pingLedState(instance) === 'ping-idle'}
                            class:ping-checking={pingLedState(instance) === 'ping-checking'}
                            class:ping-reachable={pingLedState(instance) === 'ping-reachable'}
                            class:ping-unreachable={pingLedState(instance) === 'ping-unreachable'}
                            aria-label={pingStateFor(instance).status === 'unreachable' || pingStateFor(instance).status === 'error'
                              ? 'IP address recorded — ping unreachable'
                              : pingStateFor(instance).status === 'checking'
                                ? 'IP address recorded — ping in progress'
                                : 'IP address recorded'}
                          ></span>
                        {/if}
                      </button>
                    {/if}
                  </div>
                {/each}
              </div>
            </div>
          </div>
        {:else}
          <div class="rack-loading">Create a cabinet to start mapping your data cabinet.</div>
        {/if}
      </div>
    </section>

    <aside class="inspector-panel">
      {#if selectedInstance}
        <div class="panel-heading">
          <div>
            <p class="eyebrow">Device details</p>
            <h2>{selectedInstance.name}</h2>
          </div>
          <button class="icon-button" onclick={closeDeviceDetails} aria-label="Close device details">×</button>
        </div>

        <div class="inspector-device-summary">
          <span class="summary-glyph">
            {#if deviceIconAssetUrl(selectedInstance)}
              <img class="custom-icon-image summary-custom-icon" src={deviceIconAssetUrl(selectedInstance) ?? ''} alt="" />
            {:else}
              <RackIcon icon={deviceIcon(selectedInstance)} />
            {/if}
          </span>
          <div>
            <strong>{rackRangeLabel(selectedInstance)}</strong>
            <span>{displayCategory(selectedInstance)} · {selectedInstance.status.toLowerCase()}</span>
          </div>
        </div>

        {#if hasPrimaryIp(selectedInstance)}
          <div class="inspector-ping-card">
            <div>
              <span class="eyebrow">Network reachability</span>
              <strong>{primaryEndpoint(selectedInstance)?.ipAddress}</strong>
              <div class="ping-status-row">
                <span class={`ping-status ${pingStateFor(selectedInstance).status}`}>{pingStatusText(selectedInstance)}</span>
                <span class="ping-timer">{nextPingText(selectedInstance)}</span>
              </div>
            </div>
            <button
              class="button secondary compact-button"
              type="button"
              disabled={pingStateFor(selectedInstance).status === 'checking'}
              onclick={() => void pingDevice(selectedInstance!)}
            >
              {pingStateFor(selectedInstance).status === 'checking' ? 'Pinging…' : 'Ping device'}
            </button>
          </div>
        {/if}

        <form class="device-form" onsubmit={(event) => { event.preventDefault(); saveSelectedDevice(); }}>
          <label>
            <span>Device name</span>
            <input bind:value={deviceDraft.name} required maxlength="120" />
          </label>
          <div class="form-grid">
            <label>
              <span>CPU</span>
              <input bind:value={deviceDraft.cpu} placeholder="e.g. Ryzen 9 7950X" />
            </label>
            <label>
              <span>RAM</span>
              <input bind:value={deviceDraft.ram} placeholder="e.g. 128 GB" />
            </label>
          </div>
          <label>
            <span>Storage</span>
            <input bind:value={deviceDraft.storage} placeholder="e.g. 4 TB NVMe RAID-1" />
          </label>
          <label>
            <span>Primary IP address</span>
            <input bind:value={deviceDraft.ipAddress} placeholder="e.g. 192.168.1.20" />
          </label>
          <label>
            <span>Web frontend URL</span>
            <input bind:value={deviceDraft.url} type="url" placeholder="https://device.example.local" />
          </label>
          <label>
            <span>Notes</span>
            <textarea bind:value={deviceDraft.notes} rows="5" placeholder="Maintenance, VLAN, warranty, serial number…"></textarea>
          </label>

          <div class="form-actions">
            <button class="button danger-text" type="button" onclick={requestDeleteSelectedDevice}>Remove</button>
            <button class="button primary" type="submit" disabled={isSaving}>{isSaving ? 'Saving…' : 'Save details'}</button>
          </div>
        </form>
      {:else}
        <div class="empty-inspector">
          <div class="inspector-illustration">⌁</div>
          <h2>Inspect equipment</h2>
          <p>Click a device to edit its hardware, IP address, frontend link, and maintenance notes.</p>
          <div class="tip-list">
            <span>+ Create reusable custom equipment</span>
            <span>⇄ Drag library items into a rack position</span>
            <span>◌ Hover over devices for quick details</span>
          </div>
        </div>
      {/if}
    </aside>
  </main>
</div>

{#if pinnedInstance && stickyPopupPosition}
  <div class="device-sticky-popup" style={stickyPopupStyle()} role="dialog" aria-label={`${pinnedInstance.name} quick details`}>
    <div class="tooltip-heading">
      <strong>{pinnedInstance.name}</strong>
      <button class="tooltip-close" type="button" onclick={closePinnedDevice} aria-label={`Close ${pinnedInstance.name} quick details`}>×</button>
    </div>
    <span>{pinnedInstance.template?.manufacturer || displayCategory(pinnedInstance)}{pinnedInstance.template?.model ? ` · ${pinnedInstance.template.model}` : ''}</span>
    <span>CPU: {valueAsText(pinnedInstance.specifications.cpu) || 'Not recorded'}</span>
    <span>RAM: {valueAsText(pinnedInstance.specifications.ram) || 'Not recorded'}</span>
    <span>IP: {primaryEndpoint(pinnedInstance)?.ipAddress || 'Not recorded'}</span>
    {#if hasPrimaryIp(pinnedInstance)}
      <div class="tooltip-ping-row">
        <div class="ping-status-row">
          <span class={`ping-status ${pingStateFor(pinnedInstance).status}`}>{pingStatusText(pinnedInstance)}</span>
          <span class="ping-timer">{nextPingText(pinnedInstance)}</span>
        </div>
        <button
          class="ping-button"
          type="button"
          disabled={pingStateFor(pinnedInstance).status === 'checking'}
          onclick={() => { void pingDevice(pinnedInstance!); }}
        >
          {pingStateFor(pinnedInstance).status === 'checking' ? 'Pinging…' : 'Ping'}
        </button>
      </div>
    {:else}
      <span class="ping-unavailable">Add an IP address to enable ping.</span>
    {/if}
  </div>
{/if}


{#if managementDialog === 'create-cabinet'}
  <div class="modal-backdrop" role="presentation">
    <dialog open class="modal-card management-modal-card" aria-labelledby="create-cabinet-title">
      <div class="modal-heading">
        <div>
          <p class="eyebrow">Cabinets</p>
          <h2 id="create-cabinet-title">Create a cabinet</h2>
          <p class="muted">Add a new cabinet without leaving the current workspace.</p>
        </div>
        <button class="icon-button" type="button" onclick={closeManagementDialog} disabled={isCreatingCabinet} aria-label="Close create cabinet dialog">×</button>
      </div>

      <form class="management-form" onsubmit={(event) => { event.preventDefault(); void createCabinetFromDialog(); }}>
        <label>
          <span>Cabinet name *</span>
          <input bind:value={createCabinetDraft.name} required maxlength="120" placeholder="e.g. Office data cabinet" />
        </label>
        <label>
          <span>Rack height *</span>
          <input bind:value={createCabinetDraft.heightU} type="number" min="1" max="64" step="1" required />
          <small>Choose a whole rack height between 1U and 64U.</small>
        </label>

        <div class="modal-actions">
          <button class="button secondary" type="button" onclick={closeManagementDialog} disabled={isCreatingCabinet}>Cancel</button>
          <button class="button primary" type="submit" disabled={isCreatingCabinet}>
            {isCreatingCabinet ? 'Creating cabinet…' : 'Create cabinet'}
          </button>
        </div>
      </form>
    </dialog>
  </div>
{/if}

{#if managementDialog === 'delete-cabinet' && cabinetPendingDeletion}
  <div class="modal-backdrop" role="presentation">
    <dialog open class="modal-card confirmation-modal-card" aria-labelledby="delete-cabinet-title">
      <div class="modal-heading">
        <div>
          <p class="eyebrow">Cabinets</p>
          <h2 id="delete-cabinet-title">Delete cabinet?</h2>
          <p class="muted">
            <strong>{cabinetPendingDeletion.name}</strong> will be deleted permanently.
            {#if cabinetPendingDeletion.equipmentInstances.length > 0}
              This also removes {cabinetPendingDeletion.equipmentInstances.length} installed {cabinetPendingDeletion.equipmentInstances.length === 1 ? 'item' : 'items'} from this cabinet.
            {/if}
          </p>
        </div>
        <button class="icon-button" type="button" onclick={closeManagementDialog} disabled={isDeletingCabinet} aria-label="Close delete cabinet dialog">×</button>
      </div>

      <div class="confirmation-actions">
        <button class="button secondary" type="button" onclick={closeManagementDialog} disabled={isDeletingCabinet}>Cancel</button>
        <button class="button danger" type="button" onclick={() => { void confirmDeleteCurrentCabinet(); }} disabled={isDeletingCabinet}>
          {isDeletingCabinet ? 'Deleting cabinet…' : 'Delete cabinet'}
        </button>
      </div>
    </dialog>
  </div>
{/if}

{#if managementDialog === 'remove-device' && devicePendingRemoval}
  <div class="modal-backdrop" role="presentation">
    <dialog open class="modal-card confirmation-modal-card" aria-labelledby="remove-device-title">
      <div class="modal-heading">
        <div>
          <p class="eyebrow">Rack equipment</p>
          <h2 id="remove-device-title">Remove device?</h2>
          <p class="muted">
            <strong>{devicePendingRemoval.name}</strong> will be removed from this cabinet.
            Its reusable equipment-library template will remain available.
          </p>
        </div>
        <button class="icon-button" type="button" onclick={closeManagementDialog} disabled={isRemovingDevice} aria-label="Close remove device dialog">×</button>
      </div>

      <div class="confirmation-actions">
        <button class="button secondary" type="button" onclick={closeManagementDialog} disabled={isRemovingDevice}>Cancel</button>
        <button class="button danger" type="button" onclick={() => { void confirmDeleteSelectedDevice(); }} disabled={isRemovingDevice}>
          {isRemovingDevice ? 'Removing device…' : 'Remove device'}
        </button>
      </div>
    </dialog>
  </div>
{/if}

{#if isCustomEquipmentModalOpen}
  <div class="modal-backdrop custom-equipment-modal-backdrop" role="presentation" onclick={(event) => { if (event.target === event.currentTarget) closeCustomEquipmentModal(); }}>
    <dialog open class="modal-card custom-equipment-modal-card" aria-labelledby="custom-equipment-title">
      <div class="modal-heading">
        <div>
          <p class="eyebrow">Equipment library</p>
          <h2 id="custom-equipment-title">Create custom equipment</h2>
          <p class="muted">Save a reusable device, shelf item, panel, or any other cabinet component.</p>
        </div>
        <button class="icon-button" type="button" onclick={closeCustomEquipmentModal} aria-label="Close custom equipment form">×</button>
      </div>

      <form class="custom-equipment-form" onsubmit={(event) => { event.preventDefault(); saveCustomEquipment(); }}>
        <div class="form-grid">
          <label>
            <span>Equipment name *</span>
            <input bind:value={customEquipmentDraft.name} required maxlength="120" placeholder="e.g. Raspberry Pi shelf" />
          </label>
          <label>
            <span>Category *</span>
            <select value={categoryPickerValue()} onchange={onCustomCategorySelected} aria-label="Equipment category">
              {#each categoryOptions as category}
                <option value={category}>{category}</option>
              {/each}
              <option value={CREATE_NEW_CATEGORY_VALUE}>+ Create a new category…</option>
            </select>
            {#if isCreatingNewCategory}
              <input class="new-category-input" bind:value={newCategoryName} required maxlength="60" placeholder="New category name" />
            {/if}
          </label>
        </div>

        <div class="form-grid">
          <label>
            <span>Manufacturer</span>
            <input bind:value={customEquipmentDraft.manufacturer} maxlength="120" placeholder="e.g. Ubiquiti" />
          </label>
          <label>
            <span>Model</span>
            <input bind:value={customEquipmentDraft.model} maxlength="120" placeholder="e.g. USW-24-G2" />
          </label>
        </div>

        <div class="form-grid">
          <label>
            <span>Rack height</span>
            <select bind:value={customEquipmentDraft.heightU}>
              {#each RACK_HEIGHT_OPTIONS as units}
                <option value={units}>{units}U</option>
              {/each}
            </select>
          </label>
          <label>
            <span>Rack width</span>
            <select bind:value={customEquipmentDraft.widthRatio}>
              {#each RACK_WIDTH_OPTIONS as option}
                <option value={option.value}>{option.label}</option>
              {/each}
            </select>
          </label>
        </div>

        <fieldset class="icon-picker">
          <legend>Rack icon</legend>
          <div class="icon-grid" role="group" aria-label="Choose a rack icon">
            {#each EQUIPMENT_ICON_OPTIONS as icon}
              <button
                type="button"
                class:selected-icon={customEquipmentDraft.icon === icon.key}
                class="icon-option"
                onclick={() => customEquipmentDraft.icon = icon.key}
                aria-pressed={customEquipmentDraft.icon === icon.key}
                title={icon.label}
              >
                <span><RackIcon icon={icon.key} /></span>
                <small>{icon.label}</small>
              </button>
            {/each}
          </div>
        </fieldset>

        <label class="image-upload-field custom-icon-upload">
          <span>Custom rack icon</span>
          <span class="file-picker">
            <span>{customEquipmentIconName || 'Choose optional PNG icon'}</span>
            <strong>Browse</strong>
          </span>
          <input type="file" accept="image/png" onchange={onCustomEquipmentIconSelected} />
          <small>PNG only. This is used as the compact rack/library icon when no equipment image is supplied.</small>
        </label>

        <div class="form-grid">
          <label>
            <span>CPU</span>
            <input bind:value={customEquipmentDraft.cpu} maxlength="160" placeholder="Optional" />
          </label>
          <label>
            <span>RAM</span>
            <input bind:value={customEquipmentDraft.ram} maxlength="160" placeholder="Optional" />
          </label>
        </div>

        <label>
          <span>Storage</span>
          <input bind:value={customEquipmentDraft.storage} maxlength="160" placeholder="Optional" />
        </label>

        <label class="image-upload-field">
          <span>Equipment image</span>
          <span class="file-picker">
            <span>{customEquipmentImageName || 'Choose optional PNG, JPG, or WebP image'}</span>
            <strong>Browse</strong>
          </span>
          <input type="file" accept="image/png,image/jpeg,image/webp" onchange={onCustomEquipmentImageSelected} />
          <small>Transparent PNGs work best. Images are optimised and stored in your existing persistent asset volume.</small>
        </label>

        <div class="modal-actions">
          <button class="button secondary" type="button" onclick={closeCustomEquipmentModal} disabled={isSavingCustomEquipment}>Cancel</button>
          <button class="button primary" type="submit" disabled={isSavingCustomEquipment}>
            {isSavingCustomEquipment ? 'Saving equipment…' : 'Save to library'}
          </button>
        </div>
      </form>
    </dialog>
  </div>
{/if}
