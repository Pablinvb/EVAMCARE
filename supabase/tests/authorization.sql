-- Integration test for a STAGING Supabase database after applying the migration.
-- Everything is rolled back; run as postgres in SQL Editor or psql.
begin;
insert into auth.users(id,email) values
 ('00000000-0000-4000-8000-000000000001','fictional-admin@example.test'),
 ('00000000-0000-4000-8000-000000000002','fictional-patient@example.test'),
 ('00000000-0000-4000-8000-000000000003','fictional-evaluator@example.test'),
 ('00000000-0000-4000-8000-000000000004','fictional-professional@example.test');
insert into evamcare.patients(id,patient_code,first_name,created_at,updated_at) values('rls-patient','DS-RLSTEST','Fictional RLS Patient',now(),now());
insert into evamcare.user_profiles(id,auth_user_id,email,name,status,patient_id,created_at) values
 ('rls-admin','00000000-0000-4000-8000-000000000001','fictional-admin@example.test','Fictional admin','active',null,now()),
 ('rls-patient-user','00000000-0000-4000-8000-000000000002','fictional-patient@example.test','Fictional patient','active','rls-patient',now()),
 ('rls-evaluator','00000000-0000-4000-8000-000000000003','fictional-evaluator@example.test','Fictional evaluator','active',null,now()),
 ('rls-professional','00000000-0000-4000-8000-000000000004','fictional-professional@example.test','Fictional professional','active',null,now());
insert into evamcare.user_roles values('rls-admin','admin'),('rls-patient-user','patient'),('rls-evaluator','evaluator'),('rls-professional','professional');
insert into evamcare.evaluator_patient_assignments values('rls-evaluator','rls-patient');
insert into evamcare.skin_scans(id,patient_id,scan_date,capture_source,analysis_payload_json,created_at,updated_at) values('rls-scan','rls-patient',now(),'upload','{}',now(),now());
insert into evamcare.scan_images values('rls-photo','rls-scan','face','rls-patient/rls.jpg',now());
insert into storage.objects(bucket_id,name) values('evamcare-photos','rls-patient/rls.jpg');
insert into evamcare.professional_access_grants values('rls-grant','rls-patient','rls-professional','["recommendations"]',now()+interval '1 hour',null);
set local role authenticated;
select set_config('request.jwt.claim.sub','00000000-0000-4000-8000-000000000001',true);
do $$ begin
 if exists(select 1 from evamcare.patients where id='rls-patient') then raise exception 'Admin leaked clinical profile'; end if;
 begin
  insert into evamcare.user_roles values('rls-admin','professional');
  raise exception 'Client role assignment unexpectedly allowed';
 exception when insufficient_privilege then null; end;
end $$;
select set_config('request.jwt.claim.sub','00000000-0000-4000-8000-000000000002',true);
do $$ begin
 if not exists(select 1 from evamcare.skin_scans where id='rls-scan') then raise exception 'Owner cannot read scan'; end if;
 if not exists(select 1 from storage.objects where name='rls-patient/rls.jpg') then raise exception 'Owner cannot read private photo'; end if;
end $$;
select set_config('request.jwt.claim.sub','00000000-0000-4000-8000-000000000003',true);
do $$ begin
 if not exists(select 1 from evamcare.skin_scans where id='rls-scan') then raise exception 'Assigned evaluator cannot read scan'; end if;
end $$;
select set_config('request.jwt.claim.sub','00000000-0000-4000-8000-000000000004',true);
do $$ begin
 if exists(select 1 from evamcare.skin_scans where id='rls-scan') then raise exception 'Scope leaked scans'; end if;
 if evamcare.can_read('rls-patient','photographs') then raise exception 'Scope leaked photos'; end if;
 if exists(select 1 from storage.objects where name='rls-patient/rls.jpg') then raise exception 'Storage leaked private photo'; end if;
 if not evamcare.can_read('rls-patient','recommendations') then raise exception 'Recommendation grant ignored'; end if;
end $$;
insert into evamcare.professional_follow_up_notes values('rls-note','rls-patient','rls-professional','Fictional private note',now());
reset role;
update evamcare.professional_access_grants set scopes_json='["recommendations","photographs"]' where id='rls-grant';
set local role authenticated;
do $$ begin
 if not exists(select 1 from storage.objects where name='rls-patient/rls.jpg') then raise exception 'Authorized private photo unavailable'; end if;
end $$;
reset role;
update evamcare.professional_access_grants set revoked_at=now() where id='rls-grant';
set local role authenticated;
do $$ begin
 if evamcare.active_grant('rls-patient') then raise exception 'Revocation ignored'; end if;
 if exists(select 1 from evamcare.professional_follow_up_notes where id='rls-note') then raise exception 'Revoked user can read notes'; end if;
 if exists(select 1 from storage.objects where name='rls-patient/rls.jpg') then raise exception 'Revoked user can read photo'; end if;
end $$;
reset role;
update evamcare.professional_access_grants set revoked_at=null,expires_at=now()-interval '1 minute' where id='rls-grant';
set local role authenticated;
do $$ begin
 if evamcare.active_grant('rls-patient') then raise exception 'Expiration ignored'; end if;
end $$;
reset role;
rollback;
