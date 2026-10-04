// Bundles src/ into dist/ with esbuild. Uses local node_modules, falling back to global installs.
import { createRequire } from "node:module";
import { cpSync, mkdirSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { execSync } from "node:child_process";
import path from "node:path";

const require = createRequire(import.meta.url);
let esbuild;
const nodePaths = [path.resolve("node_modules")];
for (const p of ["/opt/npm-tools/node_modules", (() => { try { return execSync("npm root -g").toString().trim(); } catch { return ""; } })()]) {
  if (p && existsSync(p)) nodePaths.push(p);
}
for (const base of nodePaths) {
  try { esbuild = require(path.join(base, "esbuild")); break; } catch {}
}
if (!esbuild) { console.error("esbuild not found — run npm install"); process.exit(1); }

mkdirSync("dist/assets", { recursive: true });
const opts = {
  entryPoints: ["src/main.tsx"], bundle: true, minify: true, sourcemap: true, format: "esm", target: "es2020",
  outfile: "dist/assets/app.js", jsx: "automatic", nodePaths, define: { "process.env.NODE_ENV": '"production"' },
  loader: { ".svg": "text" }, logLevel: "info",
};
cpSync("src/styles.css", "dist/assets/styles.css");
writeFileSync("dist/index.html", readFileSync("index.html", "utf8"));
if (process.argv.includes("--watch")) { const ctx = await esbuild.context(opts); await ctx.watch(); }
else { await esbuild.build(opts); }
