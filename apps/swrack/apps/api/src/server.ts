// version 24
import crypto from 'node:crypto';
import { spawn } from 'node:child_process';
import fs from 'node:fs/promises';
import path from 'node:path';
import { isIP } from 'node:net';
import { fileURLToPath } from 'node:url';
import cors from '@fastify/cors';
import multipart from '@fastify/multipart';
import fastifyStatic from '@fastify/static';
import { PrismaClient } from '@prisma/client';
import Fastify, { type FastifyInstance } from 'fastify';
import sharp from 'sharp';
import { z } from 'zod';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const prisma = new PrismaClient();
const storageRoot = process.env.ASSET_STORAGE_PATH ?? path.resolve(__dirname, '../../uploads');
const maxUploadBytes = Number(process.env.MAX_UPLOAD_MB ?? 10) * 1024 * 1024;

const allowedMimeTypes = new Set(['image/png', 'image/jpeg', 'image/webp']);
const pngOnlyMimeTypes = new Set(['image/png']);
const positionValues = [
  'FULL',
  'LEFT',
  'RIGHT',
  'QUARTER_1',
  'QUARTER_2',
  'QUARTER_3',
  'QUARTER_4'
] as const;
const templateWidthValues = [
  'FULL',
  'HALF',
  'QUARTER',
  // Legacy values from v5 remain valid for templates that already exist.
  'LEFT',
  'RIGHT',
  'QUARTER_1',
  'QUARTER_2',
  'QUARTER_3',
  'QUARTER_4'
] as const;
const faceValues = ['FRONT', 'REAR'] as const;
const statusValues = ['ONLINE', 'OFFLINE', 'PLANNED', 'RETIRED'] as const;

type ColumnPosition = (typeof positionValues)[number];
type TemplateWidth = (typeof templateWidthValues)[number];
type CabinetFaceValue = (typeof faceValues)[number];
type EquipmentStatusValue = (typeof statusValues)[number];
type SpecificationMap = Record<string, string | number | boolean>;
type EndpointInput = {
  label: string;
  ipAddress?: string | null;
  url?: string | null;
  protocol?: string | null;
  isPrimary: boolean;
};
type ExistingPlacement = {
  id: string;
  name: string;
  rackStartU: number;
  heightU: number;
  columnPosition: string;
  face: CabinetFaceValue;
};

type ParsedInstance = {
  cabinetId: string;
  templateId?: string | null;
  name: string;
  rackStartU: number;
  heightU: number;
  columnPosition: ColumnPosition;
  face: CabinetFaceValue;
  specifications: SpecificationMap;
  notes?: string | null;
  status: EquipmentStatusValue;
  imageAssetId?: string | null;
  networkEndpoint?: EndpointInput;
};

type PingResponse = {
  ipAddress: string;
  reachable: boolean;
  latencyMs: number | null;
  checkedAt: string;
  message: string;
};

type UploadedImageFile = {
  mimetype: string;
  filename: string;
  toBuffer: () => Promise<Buffer>;
};

type AssetUploadPolicy = {
  allowedMimeTypes: ReadonlySet<string>;
  rejectedMimeTypeMessage: string;
  requiredFormat?: 'png';
};

const cabinetInput = z.object({
  name: z.string().trim().min(2).max(120),
  location: z.string().trim().max(120).optional().nullable(),
  heightU: z.coerce.number().int().min(1).max(64).default(24)
});

const templateInput = z.object({
  name: z.string().trim().min(2).max(120),
  manufacturer: z.string().trim().max(120).optional().nullable(),
  model: z.string().trim().max(120).optional().nullable(),
  category: z.string().trim().min(2).max(60).default('General'),
  heightU: z.coerce.number().multipleOf(0.5).min(0.5).max(12).default(1),
  widthRatio: z.enum(templateWidthValues).default('FULL'),
  frontAssetId: z.string().optional().nullable(),
  specifications: z.record(z.string(), z.union([z.string(), z.number(), z.boolean()])).default({})
});

const endpointInput = z.object({
  label: z.string().trim().min(2).max(80).default('Primary frontend'),
  ipAddress: z.string().trim().max(128).optional().nullable(),
  url: z.string().trim().url().max(500).optional().nullable(),
  protocol: z.string().trim().max(30).optional().nullable(),
  isPrimary: z.boolean().default(true)
});

const instanceInput = z.object({
  cabinetId: z.string().min(1),
  templateId: z.string().optional().nullable(),
  name: z.string().trim().min(2).max(120),
  rackStartU: z.coerce.number().multipleOf(0.5).min(1),
  heightU: z.coerce.number().multipleOf(0.5).min(0.5).max(12),
  columnPosition: z.enum(positionValues).default('FULL'),
  face: z.enum(faceValues).default('FRONT'),
  specifications: z.record(z.string(), z.union([z.string(), z.number(), z.boolean()])).default({}),
  notes: z.string().trim().max(5000).optional().nullable(),
  status: z.enum(statusValues).default('ONLINE'),
  imageAssetId: z.string().optional().nullable(),
  networkEndpoint: endpointInput.optional()
});

const instancePatchInput = instanceInput.partial().omit({ cabinetId: true });

function slugify(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '')
    .slice(0, 70) || 'cabinet';
}

async function uniqueSlug(model: 'cabinet' | 'template', value: string): Promise<string> {
  const base = slugify(value);
  let candidate = base;
  let suffix = 2;

  while (true) {
    const exists = model === 'cabinet'
      ? await prisma.cabinet.findUnique({ where: { slug: candidate }, select: { id: true } })
      : await prisma.equipmentTemplate.findUnique({ where: { slug: candidate }, select: { id: true } });

    if (!exists) return candidate;
    candidate = `${base}-${suffix}`;
    suffix += 1;
  }
}

function isColumnPosition(value: string): value is ColumnPosition {
  return positionValues.includes(value as ColumnPosition);
}

function normaliseColumnPosition(value: string): ColumnPosition {
  return isColumnPosition(value) ? value : 'FULL';
}

function columnSpan(position: ColumnPosition): [number, number] {
  switch (position) {
    case 'LEFT':
      return [0, 2];
    case 'RIGHT':
      return [2, 4];
    case 'QUARTER_1':
      return [0, 1];
    case 'QUARTER_2':
      return [1, 2];
    case 'QUARTER_3':
      return [2, 3];
    case 'QUARTER_4':
      return [3, 4];
    case 'FULL':
    default:
      return [0, 4];
  }
}

function isColumnCollision(candidate: ColumnPosition, existing: ColumnPosition): boolean {
  const [candidateStart, candidateEnd] = columnSpan(candidate);
  const [existingStart, existingEnd] = columnSpan(existing);
  return candidateStart < existingEnd && existingStart < candidateEnd;
}

function formatRackUnits(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1).replace(/\.0$/, '');
}

function rangesOverlap(startA: number, heightA: number, startB: number, heightB: number): boolean {
  // Treat rack placements as half-open physical intervals. This permits two
  // 0.5U components to share a single U without allowing either to overlap.
  return startA < startB + heightB && startB < startA + heightA;
}

async function assertValidPlacement(cabinetId: string, candidate: ParsedInstance, excludedInstanceId?: string): Promise<void> {
  const cabinet = await prisma.cabinet.findUnique({
    where: { id: cabinetId },
    include: { equipmentInstances: true }
  });

  if (!cabinet) throw new Error('Cabinet not found.');
  if (candidate.rackStartU + candidate.heightU - 1 > cabinet.heightU) {
    throw new Error(`This ${formatRackUnits(candidate.heightU)}U item does not fit inside the ${cabinet.heightU}U cabinet.`);
  }

  const collision = cabinet.equipmentInstances.find((item: ExistingPlacement) => {
    if (item.id === excludedInstanceId || item.face !== candidate.face) return false;
    if (!isColumnCollision(candidate.columnPosition, normaliseColumnPosition(item.columnPosition))) return false;
    return rangesOverlap(candidate.rackStartU, candidate.heightU, item.rackStartU, item.heightU);
  });

  if (collision) throw new Error(`Placement collides with ${collision.name}.`);
}

async function ensureStorageDirectories(): Promise<void> {
  await Promise.all([
    fs.mkdir(path.join(storageRoot, 'original'), { recursive: true }),
    fs.mkdir(path.join(storageRoot, 'optimised'), { recursive: true }),
    fs.mkdir(path.join(storageRoot, 'thumbnails'), { recursive: true })
  ]);
}

function errorMessage(error: unknown): string {
  if (error instanceof z.ZodError) return error.issues.map((issue) => issue.message).join('; ');
  if (error instanceof Error) return error.message;
  return 'Unexpected error.';
}

function parseSpecificationJson(value: unknown): SpecificationMap {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
  return Object.fromEntries(
    Object.entries(value).filter(([, item]) => ['string', 'number', 'boolean'].includes(typeof item))
  ) as SpecificationMap;
}

function isCustomTemplateRecord(template: { slug: string; specifications: unknown }): boolean {
  const specifications = parseSpecificationJson(template.specifications);
  return specifications.isCustom === true || !template.slug.startsWith('generic-');
}

async function storeImageAsset(upload: UploadedImageFile, policy: AssetUploadPolicy) {
  if (!policy.allowedMimeTypes.has(upload.mimetype)) {
    throw new Error(policy.rejectedMimeTypeMessage);
  }

  const buffer = await upload.toBuffer();
  if (buffer.byteLength === 0) throw new Error('The uploaded file was empty.');
  if (buffer.byteLength > maxUploadBytes) {
    throw new Error('The uploaded file exceeded the configured size limit.');
  }

  const metadata = await sharp(buffer, { failOn: 'error' }).metadata();
  if (!metadata.width || !metadata.height) throw new Error('Could not read image dimensions.');

  if (policy.requiredFormat && metadata.format !== policy.requiredFormat) {
    throw new Error('Custom rack icons must be valid PNG image files.');
  }

  const assetId = crypto.randomUUID();
  const safeExtension = upload.mimetype === 'image/png' ? 'png' : upload.mimetype === 'image/webp' ? 'webp' : 'jpg';
  const originalKey = `original/${assetId}.${safeExtension}`;
  const optimisedKey = `optimised/${assetId}.webp`;
  const thumbnailKey = `thumbnails/${assetId}.webp`;

  await fs.writeFile(path.join(storageRoot, originalKey), buffer, { flag: 'wx' });
  await sharp(buffer)
    .rotate()
    .resize({ width: 1800, height: 1800, fit: 'inside', withoutEnlargement: true })
    .webp({ quality: 86 })
    .toFile(path.join(storageRoot, optimisedKey));
  await sharp(buffer)
    .rotate()
    .resize({ width: 320, height: 320, fit: 'inside', withoutEnlargement: true })
    .webp({ quality: 82 })
    .toFile(path.join(storageRoot, thumbnailKey));

  const asset = await prisma.imageAsset.create({
    data: {
      id: assetId,
      originalName: upload.filename,
      storageKey: optimisedKey,
      mimeType: upload.mimetype,
      width: metadata.width,
      height: metadata.height,
      fileSizeBytes: buffer.byteLength,
      checksum: crypto.createHash('sha256').update(buffer).digest('hex')
    }
  });

  return {
    ...asset,
    url: `/assets/${optimisedKey}`,
    thumbnailUrl: `/assets/${thumbnailKey}`
  };
}

function parsePingLatency(output: string): number | null {
  const match = output.match(/time[=<]([0-9.]+)\s*ms/i);
  if (!match) return null;

  const latency = Number(match[1]);
  return Number.isFinite(latency) ? latency : null;
}

function pingFailureMessage(output: string): string {
  const flattened = output.replace(/\s+/g, ' ').trim();

  if (/operation not permitted|permission denied/i.test(flattened)) {
    return 'Ping permission is unavailable in the API container.';
  }

  if (/not found|no such file/i.test(flattened)) {
    return 'The ping utility is not available in the API container.';
  }

  if (/unknown host|name or service not known/i.test(flattened)) {
    return 'The saved IP address could not be resolved.';
  }

  return 'No reply within 2 seconds.';
}

function pingHost(ipAddress: string): Promise<PingResponse> {
  const ipVersion = isIP(ipAddress);
  const args = ipVersion === 6
    ? ['-6', '-n', '-c', '1', '-W', '2', ipAddress]
    : ['-n', '-c', '1', '-W', '2', ipAddress];

  return new Promise((resolve) => {
    let completed = false;
    let output = '';
    let timer: NodeJS.Timeout | undefined;

    const finish = (response: PingResponse): void => {
      if (completed) return;
      completed = true;
      if (timer) clearTimeout(timer);
      resolve(response);
    };

    let child;
    try {
      child = spawn('/bin/ping', args, { stdio: ['ignore', 'pipe', 'pipe'] });
    } catch {
      finish({
        ipAddress,
        reachable: false,
        latencyMs: null,
        checkedAt: new Date().toISOString(),
        message: 'Ping could not be started in the API container.'
      });
      return;
    }

    child.stdout.on('data', (chunk: Buffer) => {
      output += chunk.toString();
    });

    child.stderr.on('data', (chunk: Buffer) => {
      output += chunk.toString();
    });

    child.once('error', () => {
      finish({
        ipAddress,
        reachable: false,
        latencyMs: null,
        checkedAt: new Date().toISOString(),
        message: 'The ping utility is not available in the API container.'
      });
    });

    child.once('close', (exitCode) => {
      const reachable = exitCode === 0;
      const latencyMs = reachable ? parsePingLatency(output) : null;
      finish({
        ipAddress,
        reachable,
        latencyMs,
        checkedAt: new Date().toISOString(),
        message: reachable
          ? (latencyMs === null ? 'Reply received.' : `Reply received in ${latencyMs.toFixed(1)} ms.`)
          : pingFailureMessage(output)
      });
    });

    timer = setTimeout(() => {
      child.kill('SIGTERM');
      finish({
        ipAddress,
        reachable: false,
        latencyMs: null,
        checkedAt: new Date().toISOString(),
        message: 'No reply within 2 seconds.'
      });
    }, 3500);
  });
}

export async function buildServer(): Promise<FastifyInstance> {
  await ensureStorageDirectories();

  const app = Fastify({ logger: true });
  await app.register(cors, { origin: process.env.CORS_ORIGIN ?? true });
  await app.register(multipart, { limits: { fileSize: maxUploadBytes, files: 1 } });
  await app.register(fastifyStatic, {
    root: storageRoot,
    prefix: '/assets/',
    decorateReply: false,
    cacheControl: true,
    maxAge: '7d'
  });

  app.get('/health', async () => ({ status: 'ok', service: 'cabinet-canvas-api' }));

  app.get('/api/cabinets', async () => {
    return prisma.cabinet.findMany({
      orderBy: { updatedAt: 'desc' },
      include: { _count: { select: { equipmentInstances: true } } }
    });
  });

  app.post('/api/cabinets', async (request, reply) => {
    try {
      const input = cabinetInput.parse(request.body);
      const slug = await uniqueSlug('cabinet', input.name);
      const cabinet = await prisma.cabinet.create({
        data: { slug, name: input.name, location: input.location, heightU: input.heightU }
      });
      return reply.code(201).send(cabinet);
    } catch (error) {
      return reply.code(400).send({ message: errorMessage(error) });
    }
  });

  app.get('/api/cabinets/:id', async (request, reply) => {
    const params = z.object({ id: z.string().min(1) }).parse(request.params);
    const cabinet = await prisma.cabinet.findUnique({
      where: { id: params.id },
      include: {
        equipmentInstances: {
          include: { template: true, networkEndpoints: { orderBy: [{ isPrimary: 'desc' }, { label: 'asc' }] } },
          orderBy: [{ face: 'asc' }, { rackStartU: 'desc' }]
        }
      }
    });

    if (!cabinet) return reply.code(404).send({ message: 'Cabinet not found.' });
    return cabinet;
  });

  app.patch('/api/cabinets/:id', async (request, reply) => {
    try {
      const params = z.object({ id: z.string().min(1) }).parse(request.params);
      const input = cabinetInput.partial().parse(request.body);
      const cabinet = await prisma.cabinet.update({ where: { id: params.id }, data: input });
      return cabinet;
    } catch (error) {
      return reply.code(400).send({ message: errorMessage(error) });
    }
  });

  app.delete('/api/cabinets/:id', async (request, reply) => {
    try {
      const params = z.object({ id: z.string().min(1) }).parse(request.params);
      await prisma.cabinet.delete({ where: { id: params.id } });
      return reply.code(204).send();
    } catch (error) {
      return reply.code(400).send({ message: errorMessage(error) });
    }
  });

  app.get('/api/equipment-templates', async () => {
    return prisma.equipmentTemplate.findMany({ orderBy: [{ category: 'asc' }, { name: 'asc' }] });
  });

  app.post('/api/equipment-templates', async (request, reply) => {
    try {
      const input = templateInput.parse(request.body);
      const slug = await uniqueSlug('template', input.name);
      const template = await prisma.equipmentTemplate.create({
        data: { ...input, slug, specifications: parseSpecificationJson(input.specifications) }
      });
      return reply.code(201).send(template);
    } catch (error) {
      return reply.code(400).send({ message: errorMessage(error) });
    }
  });

  app.delete('/api/equipment-templates/:id', async (request, reply) => {
    try {
      const params = z.object({ id: z.string().min(1) }).parse(request.params);
      const template = await prisma.equipmentTemplate.findUnique({
        where: { id: params.id },
        include: { _count: { select: { instances: true } } }
      });

      if (!template) return reply.code(404).send({ message: 'Equipment template not found.' });
      if (!isCustomTemplateRecord(template)) {
        return reply.code(403).send({ message: 'Built-in equipment templates cannot be deleted.' });
      }

      await prisma.equipmentTemplate.delete({ where: { id: template.id } });
      return reply.code(204).send();
    } catch (error) {
      return reply.code(400).send({ message: errorMessage(error) });
    }
  });

  app.get('/api/equipment-instances/:id', async (request, reply) => {
    const params = z.object({ id: z.string().min(1) }).parse(request.params);
    const instance = await prisma.equipmentInstance.findUnique({
      where: { id: params.id },
      include: { template: true, networkEndpoints: { orderBy: [{ isPrimary: 'desc' }, { label: 'asc' }] } }
    });
    if (!instance) return reply.code(404).send({ message: 'Equipment not found.' });
    return instance;
  });

  app.post('/api/equipment-instances', async (request, reply) => {
    try {
      const input = instanceInput.parse(request.body) as ParsedInstance;
      await assertValidPlacement(input.cabinetId, input);
      const { networkEndpoint, ...instanceData } = input;
      const instance = await prisma.equipmentInstance.create({
        data: {
          ...instanceData,
          specifications: parseSpecificationJson(instanceData.specifications),
          networkEndpoints: networkEndpoint ? { create: networkEndpoint } : undefined
        },
        include: { template: true, networkEndpoints: true }
      });
      return reply.code(201).send(instance);
    } catch (error) {
      return reply.code(400).send({ message: errorMessage(error) });
    }
  });

  app.patch('/api/equipment-instances/:id', async (request, reply) => {
    try {
      const params = z.object({ id: z.string().min(1) }).parse(request.params);
      const existing = await prisma.equipmentInstance.findUnique({ where: { id: params.id } });
      if (!existing) return reply.code(404).send({ message: 'Equipment not found.' });

      const input = instancePatchInput.parse(request.body) as Partial<ParsedInstance>;
      const proposed: ParsedInstance = {
        cabinetId: existing.cabinetId,
        templateId: input.templateId ?? existing.templateId,
        name: input.name ?? existing.name,
        rackStartU: input.rackStartU ?? existing.rackStartU,
        heightU: input.heightU ?? existing.heightU,
        columnPosition: input.columnPosition ?? normaliseColumnPosition(existing.columnPosition),
        face: input.face ?? existing.face,
        specifications: input.specifications ?? (existing.specifications as unknown as SpecificationMap),
        notes: input.notes ?? existing.notes,
        status: input.status ?? existing.status,
        imageAssetId: input.imageAssetId ?? existing.imageAssetId,
        networkEndpoint: input.networkEndpoint
      };

      await assertValidPlacement(existing.cabinetId, proposed, existing.id);
      const { networkEndpoint, ...instanceData } = input;
      const instance = await prisma.equipmentInstance.update({
        where: { id: existing.id },
        data: {
          ...instanceData,
          specifications: input.specifications ? parseSpecificationJson(input.specifications) : undefined,
          networkEndpoints: networkEndpoint
            ? {
                upsert: {
                  where: { equipmentInstanceId_label: { equipmentInstanceId: existing.id, label: networkEndpoint.label } },
                  create: networkEndpoint,
                  update: networkEndpoint
                }
              }
            : undefined
        },
        include: { template: true, networkEndpoints: { orderBy: [{ isPrimary: 'desc' }, { label: 'asc' }] } }
      });
      return instance;
    } catch (error) {
      return reply.code(400).send({ message: errorMessage(error) });
    }
  });

  app.delete('/api/equipment-instances/:id', async (request, reply) => {
    try {
      const params = z.object({ id: z.string().min(1) }).parse(request.params);
      await prisma.equipmentInstance.delete({ where: { id: params.id } });
      return reply.code(204).send();
    } catch (error) {
      return reply.code(400).send({ message: errorMessage(error) });
    }
  });

  app.get('/api/equipment-instances/:id/ping', async (request, reply) => {
    try {
      const params = z.object({ id: z.string().min(1) }).parse(request.params);
      const instance = await prisma.equipmentInstance.findUnique({
        where: { id: params.id },
        include: {
          networkEndpoints: {
            orderBy: [{ isPrimary: 'desc' }, { label: 'asc' }]
          }
        }
      });

      if (!instance) return reply.code(404).send({ message: 'Equipment not found.' });

      const endpoint = instance.networkEndpoints.find((item: { isPrimary: boolean }) => item.isPrimary) ?? instance.networkEndpoints[0];
      const ipAddress = endpoint?.ipAddress?.trim();

      if (!ipAddress) {
        return reply.code(400).send({ message: 'Add a primary IP address before running a ping check.' });
      }

      if (isIP(ipAddress) === 0) {
        return reply.code(400).send({ message: 'The primary IP address must be a valid IPv4 or IPv6 address.' });
      }

      return pingHost(ipAddress);
    } catch (error) {
      return reply.code(400).send({ message: errorMessage(error) });
    }
  });

  app.get('/api/assets', async () => prisma.imageAsset.findMany({ orderBy: { createdAt: 'desc' } }));

  app.post('/api/assets/upload', async (request, reply) => {
    try {
      const upload = await request.file();
      if (!upload) return reply.code(400).send({ message: 'Select an image file first.' });

      const asset = await storeImageAsset(upload, {
        allowedMimeTypes,
        rejectedMimeTypeMessage: 'Only PNG, JPG, JPEG, and WebP image files are supported.'
      });

      return reply.code(201).send(asset);
    } catch (error) {
      request.log.error(error);
      return reply.code(400).send({ message: errorMessage(error) });
    }
  });

  app.post('/api/assets/upload-icon', async (request, reply) => {
    try {
      const upload = await request.file();
      if (!upload) return reply.code(400).send({ message: 'Select a PNG icon file first.' });

      const asset = await storeImageAsset(upload, {
        allowedMimeTypes: pngOnlyMimeTypes,
        rejectedMimeTypeMessage: 'Custom rack icons must be PNG files.',
        requiredFormat: 'png'
      });

      return reply.code(201).send(asset);
    } catch (error) {
      request.log.error(error);
      return reply.code(400).send({ message: errorMessage(error) });
    }
  });

  app.addHook('onClose', async () => {
    await prisma.$disconnect();
  });

  return app;
}

const app = await buildServer();
const port = Number(process.env.PORT ?? 8080);

try {
  await app.listen({ port, host: '0.0.0.0' });
} catch (error) {
  app.log.error(error);
  process.exit(1);
}
