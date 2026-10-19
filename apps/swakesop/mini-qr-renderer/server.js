// version 4
const fs = require("fs");
const path = require("path");
const express = require("express");
const { createCanvas, loadImage } = require("canvas");
const { JSDOM } = require("jsdom");

const qrCodeStylingModule = require("qr-code-styling/lib/qr-code-styling.common.js");
const QRCodeStyling =
  qrCodeStylingModule?.default ||
  qrCodeStylingModule?.QRCodeStyling ||
  qrCodeStylingModule;

if (typeof QRCodeStyling !== "function") {
  throw new Error("Unable to resolve QRCodeStyling constructor from qr-code-styling package.");
}

const app = express();
app.use(express.json({ limit: "4mb" }));

const PORT = parseInt(process.env.PORT || "3000", 10);
const QR_TEMPLATE_PATH =
  process.env.QR_TEMPLATE_PATH || path.join(__dirname, "config", "qr-code-config.json");
const DEFAULT_OUTPUT_SIZE = parseInt(process.env.OUTPUT_SIZE || "280", 10);

function readJsonFile(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function deepClone(obj) {
  return JSON.parse(JSON.stringify(obj));
}

function parsePx(value, fallback = 0) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string") {
    const match = value.match(/-?\d+(\.\d+)?/);
    if (match) return parseFloat(match[0]);
  }
  return fallback;
}

function drawRoundedRect(ctx, x, y, width, height, radius) {
  const r = Math.max(0, Math.min(radius, width / 2, height / 2));
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + width, y, x + width, y + height, r);
  ctx.arcTo(x + width, y + height, x, y + height, r);
  ctx.arcTo(x, y + height, x, y, r);
  ctx.arcTo(x, y, x + width, y, r);
  ctx.closePath();
}

function buildQrOptions(template, data) {
  const source = template.props ? deepClone(template.props) : deepClone(template);

  const templateWidth = Number(source.width) > 0 ? Number(source.width) : DEFAULT_OUTPUT_SIZE;
  const templateHeight = Number(source.height) > 0 ? Number(source.height) : DEFAULT_OUTPUT_SIZE;

  const outputWidth = Number.isFinite(DEFAULT_OUTPUT_SIZE) && DEFAULT_OUTPUT_SIZE > 0
    ? DEFAULT_OUTPUT_SIZE
    : templateWidth;
  const outputHeight = Number.isFinite(DEFAULT_OUTPUT_SIZE) && DEFAULT_OUTPUT_SIZE > 0
    ? DEFAULT_OUTPUT_SIZE
    : templateHeight;

  const backgroundColor =
    (template.style && template.style.background) ||
    (source.backgroundOptions && source.backgroundOptions.color) ||
    "#ffffff";

  source.width = outputWidth;
  source.height = outputHeight;
  source.data = data;
  source.type = "canvas";
  source.jsdom = JSDOM;
  source.nodeCanvas = require("canvas");
  source.backgroundOptions = {
    ...(source.backgroundOptions || {}),
    color: backgroundColor,
  };

  return {
    qrOptions: source,
    templateWidth,
    templateHeight,
    outputWidth,
    outputHeight,
    borderRadius: parsePx(template.style && template.style.borderRadius, 0),
    backgroundColor,
  };
}

async function toNodeBuffer(rawData) {
  if (!rawData) {
    throw new Error("Renderer returned no image data.");
  }

  if (Buffer.isBuffer(rawData)) {
    return rawData;
  }

  if (rawData instanceof Uint8Array) {
    return Buffer.from(rawData);
  }

  if (typeof rawData.arrayBuffer === "function") {
    return Buffer.from(await rawData.arrayBuffer());
  }

  return Buffer.from(rawData);
}

async function renderQrPng(data) {
  const template = readJsonFile(QR_TEMPLATE_PATH);
  const {
    qrOptions,
    templateWidth,
    templateHeight,
    outputWidth,
    outputHeight,
    borderRadius,
    backgroundColor,
  } = buildQrOptions(template, data);

  const qr = new QRCodeStyling(qrOptions);
  const raw = await qr.getRawData("png");
  const pngBuffer = await toNodeBuffer(raw);

  const image = await loadImage(pngBuffer);
  const output = createCanvas(outputWidth, outputHeight);
  const ctx = output.getContext("2d");

  const scaledRadius =
    templateWidth > 0 && templateHeight > 0
      ? Math.min(
          (borderRadius / templateWidth) * outputWidth,
          (borderRadius / templateHeight) * outputHeight
        )
      : borderRadius;

  ctx.clearRect(0, 0, output.width, output.height);
  ctx.fillStyle = backgroundColor;
  drawRoundedRect(ctx, 0, 0, output.width, output.height, scaledRadius);
  ctx.fill();

  ctx.save();
  drawRoundedRect(ctx, 0, 0, output.width, output.height, scaledRadius);
  ctx.clip();
  ctx.drawImage(image, 0, 0, output.width, output.height);
  ctx.restore();

  return output.toBuffer("image/png");
}

app.get("/health", (_req, res) => {
  res.json({
    ok: true,
    templatePath: QR_TEMPLATE_PATH,
    outputSize: DEFAULT_OUTPUT_SIZE,
  });
});

app.post("/render", async (req, res) => {
  try {
    const data = String(req.body?.data || "").trim();
    if (!data) {
      return res.status(400).json({ error: "Missing required field: data" });
    }

    const png = await renderQrPng(data);
    res.setHeader("Content-Type", "image/png");
    res.setHeader("Cache-Control", "no-store");
    return res.send(png);
  } catch (error) {
    console.error("Mini QR renderer error:", error);
    return res.status(500).json({
      error: "Failed to render QR code.",
      detail: error && error.message ? error.message : String(error),
    });
  }
});

app.listen(PORT, () => {
  console.log(`Mini QR renderer listening on port ${PORT}`);
});
