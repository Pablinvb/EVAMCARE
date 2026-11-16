import { cpSync, mkdirSync } from "node:fs";

mkdirSync("dist", { recursive: true });
for (const entry of ["index.html", "styles.css", "app.js", "config.js", "assets"]) {
  cpSync(entry, `dist/${entry}`, { recursive: true });
}
console.log("EVAMCARE frontend built in dist/");
