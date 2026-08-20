export type ImportedPacingRow = {
  unit: string;
  lesson: string;
  targets: string;
  assessment: string;
};

type ZipEntry = {
  compression: number;
  compressedSize: number;
  localOffset: number;
};

const XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

function u16(view: DataView, offset: number): number {
  return view.getUint16(offset, true);
}

function u32(view: DataView, offset: number): number {
  return view.getUint32(offset, true);
}

function findEndOfCentralDirectory(bytes: Uint8Array): number {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const floor = Math.max(0, bytes.length - 65_557);
  for (let offset = bytes.length - 22; offset >= floor; offset -= 1) {
    if (u32(view, offset) === 0x06054b50) return offset;
  }
  throw new Error("This file is not a readable Excel .xlsx workbook.");
}

function centralEntries(bytes: Uint8Array): Map<string, ZipEntry> {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const decoder = new TextDecoder();
  const eocd = findEndOfCentralDirectory(bytes);
  const count = u16(view, eocd + 10);
  let offset = u32(view, eocd + 16);
  const entries = new Map<string, ZipEntry>();

  for (let index = 0; index < count; index += 1) {
    if (u32(view, offset) !== 0x02014b50) throw new Error("The Excel workbook ZIP directory is invalid.");
    const compression = u16(view, offset + 10);
    const compressedSize = u32(view, offset + 20);
    const nameLength = u16(view, offset + 28);
    const extraLength = u16(view, offset + 30);
    const commentLength = u16(view, offset + 32);
    const localOffset = u32(view, offset + 42);
    const name = decoder.decode(bytes.slice(offset + 46, offset + 46 + nameLength));
    entries.set(name, { compression, compressedSize, localOffset });
    offset += 46 + nameLength + extraLength + commentLength;
  }
  return entries;
}

async function inflateRaw(data: Uint8Array): Promise<Uint8Array> {
  if (typeof DecompressionStream === "undefined") {
    throw new Error("This browser cannot import Excel workbooks. Use the current Chrome or Edge browser for the pilot.");
  }
  const buffer = Uint8Array.from(data).buffer;
  const stream = new Blob([buffer]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

async function extract(bytes: Uint8Array, entry: ZipEntry): Promise<Uint8Array> {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const offset = entry.localOffset;
  if (u32(view, offset) !== 0x04034b50) throw new Error("The Excel workbook contains an invalid ZIP entry.");
  const nameLength = u16(view, offset + 26);
  const extraLength = u16(view, offset + 28);
  const start = offset + 30 + nameLength + extraLength;
  const compressed = bytes.slice(start, start + entry.compressedSize);
  if (entry.compression === 0) return compressed;
  if (entry.compression === 8) return await inflateRaw(compressed);
  throw new Error("This Excel workbook uses an unsupported compression method.");
}

function parseXml(text: string, label: string): Document {
  const document = new DOMParser().parseFromString(text, "application/xml");
  if (document.querySelector("parsererror")) throw new Error(`${label} in the Excel workbook is invalid.`);
  return document;
}

function elementsByLocalName(root: Document | Element, localName: string): Element[] {
  return Array.from(root.getElementsByTagNameNS("*", localName));
}

function columnIndex(reference: string): number {
  const letters = reference.match(/^[A-Za-z]+/)?.[0]?.toUpperCase() ?? "";
  let value = 0;
  for (const character of letters) value = value * 26 + character.charCodeAt(0) - 64;
  return Math.max(0, value - 1);
}

function sharedStrings(document: Document | null): string[] {
  if (!document) return [];
  return elementsByLocalName(document, "si").map((item) =>
    elementsByLocalName(item, "t").map((text) => text.textContent ?? "").join(""),
  );
}

function cellValue(cell: Element, shared: string[]): string {
  const type = cell.getAttribute("t") ?? "";
  if (type === "inlineStr") {
    return elementsByLocalName(cell, "t").map((item) => item.textContent ?? "").join("").trim();
  }
  const raw = elementsByLocalName(cell, "v")[0]?.textContent ?? "";
  if (type === "s") {
    const index = Number(raw);
    return Number.isInteger(index) && index >= 0 ? (shared[index] ?? "").trim() : "";
  }
  return raw.trim();
}

function normalizedHeader(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

function findColumn(headers: string[], candidates: string[]): number {
  return headers.findIndex((header) => candidates.some((candidate) => header.includes(candidate)));
}

export async function readPacingWorkbook(file: File): Promise<ImportedPacingRow[]> {
  if (!file.name.toLowerCase().endsWith(".xlsx") && file.type !== XLSX_MIME) {
    throw new Error("Choose an Excel .xlsx pacing workbook.");
  }
  const bytes = new Uint8Array(await file.arrayBuffer());
  const entries = centralEntries(bytes);
  const sheetEntry = entries.get("xl/worksheets/sheet1.xml");
  if (!sheetEntry) throw new Error("The workbook does not contain the expected first worksheet.");

  const decoder = new TextDecoder();
  const sheet = parseXml(decoder.decode(await extract(bytes, sheetEntry)), "The first worksheet");
  const sharedEntry = entries.get("xl/sharedStrings.xml");
  const sharedDocument = sharedEntry
    ? parseXml(decoder.decode(await extract(bytes, sharedEntry)), "Shared strings")
    : null;
  const shared = sharedStrings(sharedDocument);

  const rows = elementsByLocalName(sheet, "row").map((row) => {
    const values: string[] = [];
    for (const cell of elementsByLocalName(row, "c")) {
      const index = columnIndex(cell.getAttribute("r") ?? "A1");
      values[index] = cellValue(cell, shared);
    }
    return values;
  }).filter((row) => row.some((value) => value?.trim()));

  if (!rows.length) throw new Error("The workbook does not contain pacing rows.");
  const headers = rows[0].map((value) => normalizedHeader(value ?? ""));
  const unitColumn = findColumn(headers, ["unit topic", "unit"]);
  const lessonColumn = findColumn(headers, ["lesson focus", "lesson"]);
  const targetColumn = findColumn(headers, ["learning target", "target"]);
  const assessmentColumn = findColumn(headers, ["assessment evidence", "assessment"]);
  if (unitColumn < 0 || lessonColumn < 0) {
    throw new Error("The workbook must include Unit / Topic and Lesson / Focus columns. Download the current TPP template and try again.");
  }

  const imported = rows.slice(1).map((row) => ({
    unit: row[unitColumn]?.trim() ?? "",
    lesson: row[lessonColumn]?.trim() ?? "",
    targets: targetColumn >= 0 ? row[targetColumn]?.trim() ?? "" : "",
    assessment: assessmentColumn >= 0 ? row[assessmentColumn]?.trim() ?? "" : "",
  })).filter((row) => row.unit || row.lesson || row.targets || row.assessment);

  if (!imported.length) throw new Error("No pacing lessons were found below the workbook header row.");
  return imported;
}
