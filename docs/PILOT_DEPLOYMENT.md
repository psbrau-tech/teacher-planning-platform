# TPP Controlled Pilot Deployment

## Locked pilot decisions

- Hostname: `planner.guidedscholar.ai`
- AWS account: existing Brau Consulting / Guided Scholar AWS account
- AWS region: `us-east-2`
- Isolation: separate TPP pilot VPC, ALB, ECR repository, ECS cluster/service, task roles, and log group
- Supabase: dedicated Teacher Planning Platform project
- Authentication: Google SSO through Supabase Auth using approved `anniston.k12.al.us` accounts
- OpenAI: separate TPP project and key
- Data boundary: teacher and curriculum data only; no student data
- Platform Owner: one governed account must hold concurrent `platform_admin` and `teacher` roles
- DNS: Cloudflare remains authoritative for the pilot; a later Route 53 migration moves the complete `guidedscholar.ai` zone, including `planner.guidedscholar.ai`, as one coordinated action

## Repository release controls

### Mutating workflows

- `.github/workflows/apply-pilot-database.yml` — reviewed Supabase migration preview/application with an exact pinned CLI version and post-apply dry-run verification
- `.github/workflows/provision-pilot-access.yml` — transaction-safe school, academic-year, and staff-access provisioning
- `.github/workflows/bootstrap-pilot.yml` — isolated AWS foundation, first exact-image deployment, health verification, and ACM request; safe to retry only for the same accepted commit
- `.github/workflows/enable-pilot-tls.yml` — issued-certificate attachment with listener, redirect, target-health, and image-preservation verification
- `.github/workflows/deploy-pilot.yml` — subsequent exact-digest ECS deployments with prior-task-definition rollback evidence and no-op verification when the exact image is already active

### Read-only workflows

- `.github/workflows/preflight-pilot.yml` — validates protected GitHub configuration, staff-access JSON, academic-year dates, AWS OIDC, required secret metadata, CloudFormation, and migration inventory before mutation
- `.github/workflows/verify-pilot-deployment.yml` — verifies stack stability, ECS counts, immutable image provenance, target health, log retention, secret mappings, certificate metadata, and optional public HTTPS without changing AWS

### Application and infrastructure

- `Dockerfile` — combined React/FastAPI production image with non-root runtime and application health check
- `infra/pilot-stack.yml` — isolated TPP pilot CloudFormation stack
- `backend/scripts/preflight_pilot.py` — local and workflow validation of staff access and academic-year inputs without connecting to Supabase
- `scripts/build_or_reuse_pilot_image.sh` — shared immutable-ECR helper that reuses a commit-tagged digest after a partial workflow failure rather than attempting to overwrite an immutable tag

### Operational documentation

- `docs/PILOT_PREFLIGHT.md` — preflight use, migration rules, retry boundaries, and failure-specific remediation
- `docs/PILOT_BROWSER_ACCEPTANCE.md` — owner, administrator, volunteer-teacher, negative-authorization, export, and Friday-validation evidence package
- `docs/VOLUNTEER_TEACHER_PILOT_GUIDE.md` — controlled teacher exercise and feedback guide
- `docs/PILOT_ROLLBACK.md` — detailed layered recovery runbook
- `docs/RELEASE_ROLLBACK_CHECKLIST.md` — concise release and rollback checklist
- `docs/ROUTE53_MIGRATION_PREP.md` — coordinated migration preparation while Cloudflare remains authoritative
- `docs/DNS_RECORD_INVENTORY_TEMPLATE.md` — human-readable DNS inventory worksheet
- `docs/ROUTE53_RECORD_INVENTORY.csv` — row-level Cloudflare-to-Route 53 comparison template

All mutating workflows use the protected `tpp-pilot` GitHub environment. The read-only workflows use the same environment so they validate the actual protected values. A code push or pull request does not mutate the application, database, AWS resources, DNS, certificate, or identity-provider configuration.

## Controlled release sequence

1. Review CI, the pull-request diff, and the approved Anniston PDF artifacts.
2. Approve and merge the release pull request.
3. Run **Apply TPP Pilot Database Migrations** with `dry_run_only=true` and review the exact pending migration list.
4. Approve and run migration application with `dry_run_only=false`; the workflow must finish with no migration remaining in its final dry run.
5. Populate or correct the protected `tpp-pilot` variables and `TPP_PILOT_ACCESS_JSON` secret.
6. Run **Preflight TPP Pilot Release** with the approved academic-year dates.
7. Run **Provision TPP Pilot Access** only after preflight passes.
8. Run the preflight again before infrastructure bootstrap if any protected value changed.
9. Run **Bootstrap TPP Pilot** to create the isolated stack and deploy the first exact image.
10. Run **Verify TPP Pilot Deployment** with the deployed commit and public-hostname verification disabled.
11. Add the returned ACM validation CNAME to Cloudflare.
12. After ACM reports `ISSUED`, run **Enable TPP Pilot TLS**.
13. Set the protected GitHub variable `TPP_CERTIFICATE_ARN` to the issued certificate ARN returned by the accepted TLS workflow.
14. Add the Cloudflare CNAME `planner` to the exact ALB DNS target, initially DNS only.
15. Complete Supabase Site URL and allowed redirects plus Google OAuth origin and callback configuration.
16. Run **Verify TPP Pilot Deployment** again with public HTTPS verification enabled.
17. Complete Platform Owner, administrator, volunteer-teacher, unapproved-school-account, and non-school-account browser acceptance.
18. Retain the exact image digest, task-definition revision, verification runs, and browser evidence.

Do not bypass failed validation by weakening checks, broadening access, or moving protected values into repository files.

## Deterministic migration boundary

The migration workflow uses an exact Supabase CLI version rather than `latest`. Every apply run first previews the repository migration set, applies only reviewed pending files in timestamp order, lists migration history, and performs a final dry run. Applied migration files are immutable history; any correction must be a new forward migration.

This release contains a new migration aligning school aggregate reporting with active governed `profile_roles`. Earlier successful migration runs do not satisfy this later migration; it must receive a new protected preview and application after merge.

## Retry and recovery behavior

- **Preflight TPP Pilot Release** is read-only and can be rerun at any time.
- **Provision TPP Pilot Access** validates the complete access list before connecting and applies its changes in one database transaction.
- **Bootstrap TPP Pilot** can resume a new or partially completed stack for the same accepted commit. It will not remove an existing service and will refuse to replace an existing service with a different commit.
- After bootstrap, application changes must use **Deploy TPP Pilot**.
- Bootstrap and deploy reuse the immutable ECR digest already tagged with the same commit after a partial failure.
- Deploy avoids registering or activating a new task-definition revision when the same exact image is already active; it verifies the existing deployment instead.
- **Enable TPP Pilot TLS** preserves and verifies the active exact image and confirms the HTTPS listener, approved certificate, HTTP redirect, and target health.
- Application rollback, database correction, staff-access correction, OAuth restoration, TLS correction, DNS rollback, and future Route 53 delegation rollback remain separate controlled actions.

## Operational acceptance before volunteer access

- The read-only deployment verification passes for the exact accepted commit.
- Public HTTPS `/health` returns HTTP 200 without a certificate warning.
- ECS desired and running counts match, pending count is zero, and rollout is complete.
- The active task definition uses an immutable ECR digest associated with the accepted commit.
- All load-balancer targets are healthy.
- Application logs exist in the dedicated 30-day CloudWatch log group.
- No secret-bearing variable appears in plaintext task-definition environment values.
- All required runtime secrets are mapped through ECS secret references.
- Supabase migration history matches the repository migration set.
- The approved access list is active and unapproved accounts receive no application data.
- Platform Owner retains both `platform_admin` and `teacher` in one session.
- School Administrator reporting is aggregate and school-scoped.
- Platform Administrator cost reporting is restricted to the governed Platform Administrator role.
- No student table, roster, student account, or student-specific field is used.

## Volunteer-teacher acceptance

The volunteer teacher must independently be able to:

1. authenticate with an approved Google school account;
2. see only the approved role set;
3. import or select a sequenced curriculum;
4. configure independent teaching assignments and meeting patterns;
5. generate a week using instructional minutes and calendar exceptions;
6. complete nonblank Literacy Standards and ACT Preparation fields;
7. save and reopen a weekly draft;
8. export each approved Anniston document and the combined packet;
9. validate lessons as completed, modified, missed, or skipped;
10. carry missed instruction forward without changing unrelated curricula;
11. recognize the teacher-and-curriculum-only boundary throughout the workflow.

## Rollback

Use `docs/PILOT_ROLLBACK.md` to identify the failing layer before mutation. Application rollback, database correction, staff-access correction, OAuth restoration, TLS correction, application-record rollback, and future Route 53 delegation rollback are separate controlled actions.

A failed ECS deployment uses the configured deployment circuit breaker. A manual application rollback uses the recorded prior task definition and exact image. Application rollback does not reverse database migrations.

## Human-controlled gates

The following require human action or explicit approval:

- pull-request merge;
- protected-environment approval for database, provisioning, infrastructure, TLS, deployment, preflight, and verification workflows;
- staff access-list contents and academic-year dates;
- ACM validation CNAME creation in Cloudflare;
- setting the accepted certificate ARN in the protected GitHub environment;
- the final `planner` application CNAME;
- Supabase and Google console changes;
- live browser acceptance with approved school accounts;
- any production rollback;
- the later coordinated Route 53 nameserver migration.

## Route 53 preparation boundary

The hosted zone and record inventory may be prepared while Cloudflare remains authoritative. Do not change registrar nameservers until:

- Guided Scholar and TPP are both stable and accepted;
- every Cloudflare record is inventoried and deliberately represented or retired;
- email, OAuth, Supabase, ACM, verification, and application records are validated;
- Cloudflare proxy-only behavior has an approved replacement;
- DNSSEC handling and rollback nameservers are documented;
- an explicit coordinated migration is authorized.

Do not migrate `planner.guidedscholar.ai` independently from the parent `guidedscholar.ai` zone.

## Rollout boundary

The first exercise is a controlled volunteer-teacher pilot. Full-school rollout is a separate decision contingent on pilot acceptance, defect closeout, administrator validation, monitoring review, and explicit authorization.
