-- SQLite migration; applied idempotently by initialize_accounts at startup.
CREATE TABLE IF NOT EXISTS user_profiles(id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL, status TEXT NOT NULL, password_hash TEXT, salt TEXT, patient_id TEXT UNIQUE, specialty TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS user_roles(user_id TEXT NOT NULL REFERENCES user_profiles(id), role TEXT NOT NULL CHECK(role IN ('admin','evaluator','patient','professional')), PRIMARY KEY(user_id,role));
CREATE TABLE IF NOT EXISTS account_tokens(hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES user_profiles(id), kind TEXT NOT NULL, expires_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS evaluator_patient_assignments(evaluator_id TEXT NOT NULL REFERENCES user_profiles(id), patient_id TEXT NOT NULL REFERENCES patients(id), PRIMARY KEY(evaluator_id,patient_id));
CREATE TABLE IF NOT EXISTS professional_access_grants(id TEXT PRIMARY KEY, patient_id TEXT NOT NULL REFERENCES patients(id), professional_id TEXT NOT NULL REFERENCES user_profiles(id), scopes_json TEXT NOT NULL, expires_at TEXT NOT NULL, revoked_at TEXT);
CREATE TABLE IF NOT EXISTS professional_follow_up_notes(id TEXT PRIMARY KEY, patient_id TEXT NOT NULL REFERENCES patients(id), professional_id TEXT NOT NULL REFERENCES user_profiles(id), body TEXT NOT NULL, created_at TEXT NOT NULL);
