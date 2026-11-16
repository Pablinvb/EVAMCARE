import { spawnSync } from "node:child_process";

let connection;
const databaseUrl = process.env.DATABASE_URL_UNPOOLED || process.env.DATABASE_URL;
try {
  connection = new URL(databaseUrl || "");
} catch {
  console.error("Neon startup requires a valid DATABASE_URL.");
  process.exit(1);
}
if (!["postgres:", "postgresql:"].includes(connection.protocol) ||
    !connection.hostname.endsWith(".neon.tech") ||
    connection.hostname.includes("-pooler.")) {
  console.error("Use a direct Neon PostgreSQL DATABASE_URL for this app's schema initialization.");
  process.exit(1);
}
const python = process.env.PYTHON || "python";
const ca = spawnSync(python, ["-c", "import certifi; print(certifi.where())"], { encoding: "utf8" });
if (ca.status !== 0 || !ca.stdout?.trim()) {
  console.error("Install the Python dependencies from requirements.txt before starting.");
  process.exit(1);
}
const run = spawnSync(python, [
  "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", process.env.PORT || "8000",
], {
  stdio: "inherit",
  env: {
    ...process.env,
    DATABASE_URL: databaseUrl,
    DERMASCAN_POSTGRES_SCHEMA: "evamcare_neon",
    DERMASCAN_POSTGRES_SSLMODE: "verify-full",
    PGSSLROOTCERT: ca.stdout.trim(),
    DERMASCAN_REAL_PATIENTS_ENABLED: "false",
  },
});
if (run.error) console.error("Could not start Python. Install requirements.txt or set PYTHON.");
process.exit(run.status ?? 1);
