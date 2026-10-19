// version 20
import type { CabinetDetail, CabinetSummary, EquipmentInstance, EquipmentTemplate, ImageAsset, PingResult } from './types';

// Vite's BASE_URL is the mount path, with a trailing slash ('/' when standalone).
const BASE = import.meta.env.BASE_URL.replace(/\/+$/, '');

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);

  // Only label a request as JSON when it has a JSON body. Fastify correctly
  // rejects an empty request body when Content-Type is application/json.
  if (options.body !== undefined && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(BASE + path, {
    ...options,
    headers
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({ message: `Request failed (${response.status}).` }));
    throw new Error(data.message ?? `Request failed (${response.status}).`);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  cabinets: () => request<CabinetSummary[]>('/api/cabinets'),
  cabinet: (id: string) => request<CabinetDetail>(`/api/cabinets/${id}`),
  createCabinet: (data: { name: string; location?: string; heightU: number }) => request<CabinetSummary>('/api/cabinets', { method: 'POST', body: JSON.stringify(data) }),
  deleteCabinet: (id: string) => request<void>(`/api/cabinets/${id}`, { method: 'DELETE' }),
  templates: () => request<EquipmentTemplate[]>('/api/equipment-templates'),
  createTemplate: (data: Partial<EquipmentTemplate> & Pick<EquipmentTemplate, 'name' | 'category' | 'heightU' | 'widthRatio'>) => request<EquipmentTemplate>('/api/equipment-templates', { method: 'POST', body: JSON.stringify(data) }),
  deleteTemplate: (id: string) => request<void>(`/api/equipment-templates/${id}`, { method: 'DELETE' }),
  createInstance: (data: Record<string, unknown>) => request<EquipmentInstance>('/api/equipment-instances', { method: 'POST', body: JSON.stringify(data) }),
  updateInstance: (id: string, data: Record<string, unknown>) => request<EquipmentInstance>(`/api/equipment-instances/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteInstance: (id: string) => request<void>(`/api/equipment-instances/${id}`, { method: 'DELETE' }),
  pingInstance: (id: string) => request<PingResult>(`/api/equipment-instances/${id}/ping`),
  uploadAsset: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return request<ImageAsset>('/api/assets/upload', { method: 'POST', body: formData });
  },
  uploadIconAsset: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return request<ImageAsset>('/api/assets/upload-icon', { method: 'POST', body: formData });
  }
};
