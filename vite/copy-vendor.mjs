// Copy the API docs viewers into the Flask static folder.
//
// They stay out of the bundle: flask-vite serves a single JS file to every
// page, and these weigh about 2 MB each for /api/v1/docs and /api/v1/redoc.
// Their versions live in package.json and package-lock.json.
import { cpSync, mkdirSync, rmSync } from "node:fs";
import { basename } from "node:path";

const DEST = "../src/app/static/vendor";

const FILES = {
  "swagger-ui": [
    "swagger-ui-dist/swagger-ui.css",
    "swagger-ui-dist/swagger-ui-bundle.js",
    "swagger-ui-dist/swagger-ui-standalone-preset.js",
  ],
  redoc: ["redoc/bundles/redoc.standalone.js"],
};

for (const [dir, files] of Object.entries(FILES)) {
  const target = `${DEST}/${dir}`;
  rmSync(target, { recursive: true, force: true });
  mkdirSync(target, { recursive: true });
  for (const file of files) {
    cpSync(`node_modules/${file}`, `${target}/${basename(file)}`);
  }
}
