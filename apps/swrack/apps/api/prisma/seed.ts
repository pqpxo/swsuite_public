// version 24
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

const templates = [
  {
    slug: 'generic-1u-switch',
    name: '24-port Network Switch',
    manufacturer: 'Generic',
    model: '1U Managed Switch',
    category: 'Networking',
    heightU: 1,
    widthRatio: 'FULL',
    specifications: { ports: '24 × 1GbE', poe: 'Optional', cpu: 'Embedded switching ASIC' }
  },
  {
    slug: 'generic-2u-server',
    name: '2U Rack Server',
    manufacturer: 'Generic',
    model: '2U Virtualisation Host',
    category: 'Server',
    heightU: 2,
    widthRatio: 'FULL',
    specifications: { cpu: 'Dual Xeon / EPYC', ram: '128 GB', storage: '4 TB SSD / RAID' }
  },
  {
    slug: 'generic-2u-nas',
    name: '2U Storage Server',
    manufacturer: 'Generic',
    model: '2U NAS',
    category: 'Storage',
    heightU: 2,
    widthRatio: 'FULL',
    specifications: { cpu: 'Intel Xeon', ram: '32 GB ECC', storage: '24 TB RAID-Z' }
  },
  {
    slug: 'generic-1u-patch-panel',
    name: '24-port Patch Panel',
    manufacturer: 'Generic',
    model: 'Cat6 Patch Panel',
    category: 'Cabling',
    heightU: 1,
    widthRatio: 'FULL',
    specifications: { ports: '24 × Cat6', type: 'Keystone' }
  },
  {
    slug: 'generic-1u-pdu',
    name: '1U Rack PDU',
    manufacturer: 'Generic',
    model: 'Power Distribution Unit',
    category: 'Power',
    heightU: 1,
    widthRatio: 'FULL',
    specifications: { outlets: '8 × UK sockets', input: '230V / 13A' }
  },
  {
    slug: 'generic-blank-panel-1u',
    name: 'Blank Panel 1U',
    manufacturer: 'Generic',
    model: '1U Blank Panel',
    category: 'Panels',
    heightU: 1,
    widthRatio: 'FULL',
    specifications: { isBlankPanel: true, icon: 'blank-panel' }
  },
  {
    slug: 'generic-blank-panel-2u',
    name: 'Blank Panel 2U',
    manufacturer: 'Generic',
    model: '2U Blank Panel',
    category: 'Panels',
    heightU: 2,
    widthRatio: 'FULL',
    specifications: { isBlankPanel: true, icon: 'blank-panel' }
  },
  {
    slug: 'generic-blank-panel-3u',
    name: 'Blank Panel 3U',
    manufacturer: 'Generic',
    model: '3U Blank Panel',
    category: 'Panels',
    heightU: 3,
    widthRatio: 'FULL',
    specifications: { isBlankPanel: true, icon: 'blank-panel' }
  },
  {
    slug: 'generic-blank-panel-4u',
    name: 'Blank Panel 4U',
    manufacturer: 'Generic',
    model: '4U Blank Panel',
    category: 'Panels',
    heightU: 4,
    widthRatio: 'FULL',
    specifications: { isBlankPanel: true, icon: 'blank-panel' }
  }
];

async function main(): Promise<void> {
  // Previous UI versions used generic custom category labels. Consolidate them
  // into General so they no longer appear in filters or category selectors.
  await prisma.equipmentTemplate.updateMany({
    where: { category: 'Custom' },
    data: { category: 'General' }
  });
  await prisma.equipmentTemplate.updateMany({
    where: { category: 'Custom equipment' },
    data: { category: 'General' }
  });

  const cabinet = await prisma.cabinet.upsert({
    where: { slug: 'office-data-cabinet' },
    update: {},
    create: {
      slug: 'office-data-cabinet',
      name: 'Office Data Cabinet',
      location: 'Office',
      heightU: 24
    }
  });

  for (const template of templates) {
    await prisma.equipmentTemplate.upsert({
      where: { slug: template.slug },
      update: {},
      create: template
    });
  }

  const existingCount = await prisma.equipmentInstance.count({ where: { cabinetId: cabinet.id } });
  if (existingCount > 0) return;

  const switchTemplate = await prisma.equipmentTemplate.findUniqueOrThrow({ where: { slug: 'generic-1u-switch' } });
  const serverTemplate = await prisma.equipmentTemplate.findUniqueOrThrow({ where: { slug: 'generic-2u-server' } });
  const nasTemplate = await prisma.equipmentTemplate.findUniqueOrThrow({ where: { slug: 'generic-2u-nas' } });
  const patchTemplate = await prisma.equipmentTemplate.findUniqueOrThrow({ where: { slug: 'generic-1u-patch-panel' } });

  const switchInstance = await prisma.equipmentInstance.create({
    data: {
      cabinetId: cabinet.id,
      templateId: switchTemplate.id,
      name: 'Core Switch',
      rackStartU: 22,
      heightU: 1,
      specifications: { ports: '24 × 1GbE + 4 × SFP+', management: 'Managed switch' }
    }
  });

  await prisma.networkEndpoint.create({
    data: {
      equipmentInstanceId: switchInstance.id,
      label: 'Primary frontend',
      ipAddress: '192.168.1.2',
      url: 'https://switch.example.local',
      protocol: 'HTTPS',
      isPrimary: true
    }
  });

  const serverInstance = await prisma.equipmentInstance.create({
    data: {
      cabinetId: cabinet.id,
      templateId: serverTemplate.id,
      name: 'Proxmox Host 01',
      rackStartU: 17,
      heightU: 2,
      specifications: { cpu: 'AMD Ryzen 9 7950X', ram: '128 GB DDR5', storage: '4 TB NVMe RAID-1' }
    }
  });

  await prisma.networkEndpoint.create({
    data: {
      equipmentInstanceId: serverInstance.id,
      label: 'Primary frontend',
      ipAddress: '192.168.1.20',
      url: 'https://proxmox.example.local',
      protocol: 'HTTPS',
      isPrimary: true
    }
  });

  const nasInstance = await prisma.equipmentInstance.create({
    data: {
      cabinetId: cabinet.id,
      templateId: nasTemplate.id,
      name: 'NAS 01',
      rackStartU: 13,
      heightU: 2,
      specifications: { cpu: 'Intel Xeon D', ram: '64 GB ECC', storage: '48 TB RAID-Z2' }
    }
  });

  await prisma.networkEndpoint.create({
    data: {
      equipmentInstanceId: nasInstance.id,
      label: 'Primary frontend',
      ipAddress: '192.168.1.30',
      url: 'https://nas.example.local',
      protocol: 'HTTPS',
      isPrimary: true
    }
  });

  await prisma.equipmentInstance.create({
    data: {
      cabinetId: cabinet.id,
      templateId: patchTemplate.id,
      name: 'Patch Panel A',
      rackStartU: 23,
      heightU: 1,
      specifications: { ports: '24 × Cat6', termination: 'Office wall ports' }
    }
  });
}

main()
  .catch((error: unknown) => {
    console.error('Seed failed', error);
    process.exitCode = 1;
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
