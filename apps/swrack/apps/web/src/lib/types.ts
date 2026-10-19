// version 7
export type PrimitiveSpec = string | number | boolean;

export type ColumnPosition =
  | 'FULL'
  | 'LEFT'
  | 'RIGHT'
  | 'QUARTER_1'
  | 'QUARTER_2'
  | 'QUARTER_3'
  | 'QUARTER_4';

export type EquipmentTemplateWidth =
  | 'FULL'
  | 'HALF'
  | 'QUARTER'
  // Legacy values from v5 remain recognised so existing templates keep working.
  | 'LEFT'
  | 'RIGHT'
  | 'QUARTER_1'
  | 'QUARTER_2'
  | 'QUARTER_3'
  | 'QUARTER_4';

export interface CabinetSummary {
  id: string;
  slug: string;
  name: string;
  location?: string | null;
  heightU: number;
  _count?: { equipmentInstances: number };
}

export interface EquipmentTemplate {
  id: string;
  slug: string;
  name: string;
  manufacturer?: string | null;
  model?: string | null;
  category: string;
  heightU: number;
  widthRatio: EquipmentTemplateWidth;
  frontAssetId?: string | null;
  specifications: Record<string, PrimitiveSpec>;
}

export interface NetworkEndpoint {
  id: string;
  label: string;
  ipAddress?: string | null;
  port?: number | null;
  protocol?: string | null;
  url?: string | null;
  isPrimary: boolean;
}

export interface EquipmentInstance {
  id: string;
  cabinetId: string;
  templateId?: string | null;
  name: string;
  rackStartU: number;
  heightU: number;
  columnPosition: ColumnPosition;
  face: 'FRONT' | 'REAR';
  specifications: Record<string, PrimitiveSpec>;
  notes?: string | null;
  status: 'ONLINE' | 'OFFLINE' | 'PLANNED' | 'RETIRED';
  imageAssetId?: string | null;
  template?: EquipmentTemplate | null;
  networkEndpoints: NetworkEndpoint[];
}

export interface CabinetDetail extends CabinetSummary {
  equipmentInstances: EquipmentInstance[];
}

export interface ImageAsset {
  id: string;
  originalName: string;
  storageKey: string;
  mimeType: string;
  width?: number | null;
  height?: number | null;
  fileSizeBytes: number;
  createdAt: string;
  url?: string;
  thumbnailUrl?: string;
}


export interface PingResult {
  ipAddress: string;
  reachable: boolean;
  latencyMs?: number | null;
  checkedAt: string;
  message: string;
}
