-- Prepared target schema. Run in a NEW Supabase project, not against SQLite.
-- Existing IDs remain text; auth_user_id maps to Supabase Auth without rewriting IDs.
begin;
create schema if not exists evamcare;
create table evamcare.patients (
 id text primary key, patient_code text unique not null, first_name text not null,
 last_name text, date_of_birth date, email text, phone text, gender text, city text, country text,
 skin_goals_json jsonb not null default '[]', demo boolean not null default false,
 created_at timestamptz not null, updated_at timestamptz not null
);
create table evamcare.user_profiles (
 id text primary key, auth_user_id uuid unique references auth.users(id),
 email text unique not null, name text not null,
 status text not null check(status in ('pending','active','inactive')),
 patient_id text unique references evamcare.patients(id), specialty text,
 created_at timestamptz not null
);
-- Passwords and local account_tokens are deliberately NOT migrated into Auth.
create table evamcare.user_roles (
 user_id text references evamcare.user_profiles(id),
 role text check(role in ('admin','evaluator','patient','professional')),
 primary key(user_id,role)
);
create table evamcare.evaluator_patient_assignments (
 evaluator_id text references evamcare.user_profiles(id), patient_id text references evamcare.patients(id),
 primary key(evaluator_id,patient_id)
);
create table evamcare.skin_scans (
 id text primary key, patient_id text not null references evamcare.patients(id),
 scan_date timestamptz not null, capture_source text not null,
 overall_score integer, acne_score integer, hydration_score integer, pigmentation_score integer,
 wrinkles_score integer, pores_score integer, redness_score integer, oiliness_score integer,
 confidence_score integer, ai_model text, ai_model_version text, analysis_status text,
 analysis_payload_json jsonb not null, created_at timestamptz not null, updated_at timestamptz not null
);
create index on evamcare.skin_scans(patient_id,scan_date desc);
create table evamcare.scan_images (
 id text primary key, scan_id text not null references evamcare.skin_scans(id),
 image_type text not null, storage_path text unique not null, created_at timestamptz not null
);
create table evamcare.recommendations (
 id text primary key, patient_id text not null references evamcare.patients(id),
 scan_id text references evamcare.skin_scans(id), category text, title text, description text,
 priority integer, created_at timestamptz not null
);
create table evamcare.professional_access_grants (
 id text primary key, patient_id text not null references evamcare.patients(id),
 professional_id text not null references evamcare.user_profiles(id),
 scopes_json jsonb not null check(jsonb_typeof(scopes_json)='array' and scopes_json <@ '["profile","scans","photographs","evolution","recommendations"]'::jsonb and jsonb_array_length(scopes_json)>0),
 expires_at timestamptz not null, revoked_at timestamptz
);
create index on evamcare.professional_access_grants(patient_id,professional_id,expires_at);
create table evamcare.professional_follow_up_notes (
 id text primary key, patient_id text not null references evamcare.patients(id),
 professional_id text not null references evamcare.user_profiles(id), body text not null,
 created_at timestamptz not null
);
create table evamcare.consents (
 id text primary key, patient_id text not null references evamcare.patients(id),
 consent_type text not null, granted boolean not null, granted_at timestamptz, revoked_at timestamptz, version text not null
);
create table evamcare.audit_logs (
 id text primary key, patient_id text references evamcare.patients(id), actor_id text,
 action text not null, resource_type text not null, resource_id text,
 timestamp timestamptz not null, metadata_json jsonb not null
);

-- Helpers owned by the migration owner, restricted search_path and no client writes.
create function evamcare.actor_id() returns text language sql stable security definer set search_path='' as $$
 select id from evamcare.user_profiles where auth_user_id=(select auth.uid()) and status='active'
$$;
create function evamcare.has_role(wanted text) returns boolean language sql stable security definer set search_path='' as $$
 select exists(select 1 from evamcare.user_roles where user_id=evamcare.actor_id() and role=wanted)
$$;
create function evamcare.owns_patient(pid text) returns boolean language sql stable security definer set search_path='' as $$
 select evamcare.has_role('patient') and exists(select 1 from evamcare.user_profiles where id=evamcare.actor_id() and patient_id=pid)
$$;
create function evamcare.can_evaluate(pid text) returns boolean language sql stable security definer set search_path='' as $$
 select evamcare.has_role('evaluator') and exists(select 1 from evamcare.evaluator_patient_assignments where evaluator_id=evamcare.actor_id() and patient_id=pid)
$$;
create function evamcare.can_read(pid text, scope text) returns boolean language sql stable security definer set search_path='' as $$
 select evamcare.owns_patient(pid) or evamcare.can_evaluate(pid) or
 (evamcare.has_role('professional') and exists(select 1 from evamcare.professional_access_grants
 where patient_id=pid and professional_id=evamcare.actor_id() and revoked_at is null and expires_at>now() and scopes_json ? scope))
$$;
create function evamcare.active_grant(pid text) returns boolean language sql stable security definer set search_path='' as $$
 select evamcare.has_role('professional') and exists(select 1 from evamcare.professional_access_grants
 where patient_id=pid and professional_id=evamcare.actor_id() and revoked_at is null and expires_at>now())
$$;
create function evamcare.photo_access(path text) returns boolean language sql stable security definer set search_path='' as $$
 select exists(select 1 from evamcare.scan_images i join evamcare.skin_scans s on s.id=i.scan_id
 where i.storage_path=path and evamcare.can_read(s.patient_id,'photographs'))
$$;
create function evamcare.photo_upload(path text) returns boolean language sql stable security definer set search_path='' as $$
 select exists(select 1 from evamcare.scan_images i join evamcare.skin_scans s on s.id=i.scan_id
 where i.storage_path=path and (evamcare.owns_patient(s.patient_id) or evamcare.can_evaluate(s.patient_id))
 and exists(select 1 from evamcare.consents c where c.patient_id=s.patient_id and c.consent_type='photo_storage' and c.granted and c.revoked_at is null))
$$;

alter table evamcare.user_profiles enable row level security;
alter table evamcare.user_roles enable row level security;
alter table evamcare.patients enable row level security;
alter table evamcare.evaluator_patient_assignments enable row level security;
alter table evamcare.skin_scans enable row level security;
alter table evamcare.scan_images enable row level security;
alter table evamcare.recommendations enable row level security;
alter table evamcare.professional_access_grants enable row level security;
alter table evamcare.professional_follow_up_notes enable row level security;
alter table evamcare.consents enable row level security;
alter table evamcare.audit_logs enable row level security;

create policy profiles_read on evamcare.user_profiles for select to authenticated using(id=evamcare.actor_id() or evamcare.has_role('admin'));
create policy roles_read on evamcare.user_roles for select to authenticated using(user_id=evamcare.actor_id() or evamcare.has_role('admin'));
-- No client INSERT/UPDATE on roles or profiles: trusted backend only.
create policy patients_read on evamcare.patients for select to authenticated using(evamcare.can_read(id,'profile'));
create policy assignments_read on evamcare.evaluator_patient_assignments for select to authenticated using(evaluator_id=evamcare.actor_id() or evamcare.owns_patient(patient_id) or evamcare.has_role('admin'));
create policy scans_read on evamcare.skin_scans for select to authenticated using(evamcare.can_read(patient_id,'scans'));
create policy images_read on evamcare.scan_images for select to authenticated using(evamcare.photo_access(storage_path));
create policy recommendations_read on evamcare.recommendations for select to authenticated using(evamcare.can_read(patient_id,'recommendations'));
create policy grants_read on evamcare.professional_access_grants for select to authenticated using(evamcare.owns_patient(patient_id) or professional_id=evamcare.actor_id());
-- Grant creation/revocation goes through backend, validating role, duration and ownership.
create policy notes_read on evamcare.professional_follow_up_notes for select to authenticated using(professional_id=evamcare.actor_id() and evamcare.active_grant(patient_id));
create policy notes_insert on evamcare.professional_follow_up_notes for insert to authenticated with check(professional_id=evamcare.actor_id() and evamcare.active_grant(patient_id));
create policy consents_read on evamcare.consents for select to authenticated using(evamcare.owns_patient(patient_id) or evamcare.can_evaluate(patient_id));
-- audit_logs intentionally has no client policies.

-- Scope-specific evolution RPC does not expose raw analysis payload or profile.
create function evamcare.evolution(pid text) returns table(scan_id text,scan_date timestamptz,overall_score integer,hydration_score integer)
language sql stable security definer set search_path='' as $$
 select s.id,s.scan_date,s.overall_score,s.hydration_score from evamcare.skin_scans s
 where s.patient_id=pid and evamcare.can_read(pid,'evolution') order by s.scan_date
$$;

revoke all on schema evamcare from public,anon;
grant usage on schema evamcare to authenticated,service_role;
revoke all on all tables in schema evamcare from public,anon,authenticated;
grant select on all tables in schema evamcare to authenticated;
grant insert on evamcare.professional_follow_up_notes to authenticated;
grant all on all tables in schema evamcare to service_role;
revoke execute on all functions in schema evamcare from public,anon;
grant execute on all functions in schema evamcare to authenticated,service_role;

insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
values('evamcare-photos','evamcare-photos',false,10485760,array['image/jpeg','image/png','image/webp']);
create policy evamcare_photo_read on storage.objects for select to authenticated
 using(bucket_id='evamcare-photos' and evamcare.photo_access(name));
create policy evamcare_photo_insert on storage.objects for insert to authenticated
 with check(bucket_id='evamcare-photos' and evamcare.photo_upload(name));
-- No public reads, client overwrite, or client deletion.
commit;
