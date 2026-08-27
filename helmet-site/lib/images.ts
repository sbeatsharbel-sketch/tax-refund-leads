import fs from "node:fs";
import path from "node:path";

/**
 * Resolved once, at build time, because the page is statically prerendered.
 * A missing file is not an error — the chapter renders a placeholder instead.
 */
const dir = path.join(process.cwd(), "public", "img");

export type ImageInfo = { src: string; exists: boolean; file: string };

export function imageInfo(file: string): ImageInfo {
  let exists = false;
  try {
    exists = fs.statSync(path.join(dir, file)).isFile();
  } catch {
    exists = false;
  }
  return { src: `/img/${file}`, exists, file };
}
