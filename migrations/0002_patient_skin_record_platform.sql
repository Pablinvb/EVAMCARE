-- EvanCare / DermaScan 2.0 patient skin record foundation.
-- SQLite-compatible reference migration for the MVP. The app also applies
-- these tables safely at startup with CREATE TABLE IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS patients (
  id TEXT PRIMARY KEY,
  patient_code TEXT UNIQUE NOT NULL,
  session_id TEXT UNIQUE NOT NULL,
  first_name TEXT NOT NULL,
  last_name TEXT,
  date_of_birth TEXT,
  email TEXT,
  phone TEXT,
  gender TEXT,
  city TEXT,
  country TEXT,
  skin_goals_json TEXT NOT NULL,
  demo INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS skin_scans (
  id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL,
  scan_date TEXT NOT NULL,
  capture_source TEXT NOT NULL,
  overall_score INTEGER NOT NULL,
  acne_score INTEGER,
  hydration_score INTEGER,
  pigmentation_score INTEGER,
  wrinkles_score INTEGER,
  pores_score INTEGER,
  redness_score INTEGER,
  oiliness_score INTEGER,
  confidence_score INTEGER,
  ai_model TEXT NOT NULL,
  ai_model_version TEXT NOT NULL,
  analysis_status TEXT NOT NULL,
  analysis_payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (patient_id) REFERENCES patients(id)
);

CREATE INDEX IF NOT EXISTS idx_skin_scans_patient_date
  ON skin_scans(patient_id, scan_date DESC);

CREATE TABLE IF NOT EXISTS scan_images (
  id TEXT PRIMARY KEY,
  scan_id TEXT NOT NULL,
  image_type TEXT NOT NULL,
  storage_path TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (scan_id) REFERENCES skin_scans(id)
);

CREATE TABLE IF NOT EXISTS recommendations (
  id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL,
  scan_id TEXT,
  category TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  priority INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (patient_id) REFERENCES patients(id),
  FOREIGN KEY (scan_id) REFERENCES skin_scans(id)
);

CREATE TABLE IF NOT EXISTS shared_records (
  id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL,
  token_hash TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  revoked_at TEXT,
  permissions_json TEXT NOT NULL,
  recipient_type TEXT NOT NULL,
  accessed_at TEXT,
  FOREIGN KEY (patient_id) REFERENCES patients(id)
);

CREATE TABLE IF NOT EXISTS consents (
  id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL,
  consent_type TEXT NOT NULL,
  granted INTEGER NOT NULL,
  granted_at TEXT,
  revoked_at TEXT,
  version TEXT NOT NULL,
  FOREIGN KEY (patient_id) REFERENCES patients(id)
);

CREATE TABLE IF NOT EXISTS audit_logs (
  id TEXT PRIMARY KEY,
  patient_id TEXT,
  actor_id TEXT,
  action TEXT NOT NULL,
  resource_type TEXT NOT NULL,
  resource_id TEXT,
  timestamp TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  FOREIGN KEY (patient_id) REFERENCES patients(id)
);
