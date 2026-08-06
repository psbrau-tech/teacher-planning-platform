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
- Platform owner: one governed account must hold concurrent `platform_admin` and `teacher` roles
- DNS: Cloudflare remains authoritative for the pilot; a future Route 53 migration moves `guidedscholar.ai` and `planner.guidedscholar.ai` together

## Release artifacts in this repository

### Application and infrastructure

- `Dockerfile` — combined React/FastAPI production image, non-root runtime, application health check
- `infra/pilot-stack.yml` — isolated AWS pilot stack
- `.github/workflows/apply-pilot-database.yml` — reviewed Supabase migration preview/application
- `.github/workflows/provision-pilot-access.yml` — transaction-safe school, academic-year, and staff-access provisioning
- `.github/workflows/bootstrap-pilot.yml` — first infrastructure and exact-image deployment plus ACM request
- `.github/workflows/enable-pilot-tls.yml` — issued-certificate attachment and DNS handoff
- `.github/workflows/deploy-pilot.yml` — subsequent exact-digest ECS deployments with rollback evidence

### Read-only release controls

- `.github/workflows/preflight-pilot.yml` — validates protected configuration, staff-access JSON, AWS OIDC, secret metadata, CloudFormation, and migration inventory before mutation
- `.github/workflows/verify-pilot-deployment.yml` — verifies stack stability, ECS counts, exact image digest, ECR provenance, target health, log retention, certificate metadata, and optional public HTTPS
- `backend/scripts/preflight_pilot.py` — validates the governed staff list and academic-year inputs without connecting to Supabase
- `docs/PILOT_PREFLIGHT.md` — failure-specific preflight remediation

### Acceptance, DNS, and recovery

- `docs/PILOT_BROWSER_ACCEPTANCE.md` — owner, administrator, volunteer-teacher, negative-authorization, export, and Friday-validation evidence package
- `docs/VOLUNTEER_TEACHER_PILOT_GUIDE.md` — controlled teacher exercise and feedback guide
- `docs/PILOT_ROLLBACK.md` — layered application, database, access, OAuth, TLS, DNS, and Route 53 rollback runbook
- `docs/ROUTE53_MIGRATION_PREPARATION.md` — coordinated preparation with Cloudflare retained as the rollback path
- `docs/ROUTE53_RECORD_INVENTORY.csv` — record-by-record Cloudflare-to-Route 53 comparison template

All mutating workflows use the protected `tpp-pilot` GitHub environment. Read-only verification workflows also use that environment so they test the actual protected configuration. No application, database, DNS, or certificate mutation occurs merely because code is pushed or a pull request is opened.

## Controlled release sequence

1. Review CI, the pull-request diff, and the approved Anniston PDF artifacts.
2. Approve and merge the release pull request.
3. Preview and then apply the Supabase migrations through the protected migration workflow.
4. Populate or correct the protected `tpp-pilot` variables and `TPP_PILOT_ACCESS_JSON` secret.
5. Run **Preflight TPP Pilot Release** with the approved academic-year dates.
6. Provision Anniston High School, the active academic year, and the approved staff allowlist.
7. Run the preflight again before infrastructure bootstrap if configuration changed.
8. Bootstrap the AWS stack and first exact image.
9. Run **Verify TPP Pilot Deployment** using the exact deployed commit, with public-hostname verification disabled until DNS and TLS are complete.
10. Add the returned ACM validation CNAME to Cloudflare.
11. When ACM is `ISSUED`, attach TLS through the protected TLS workflow.
12. Add Cloudflare CNAME `planner` to the returned ALB DNS target, initially DNS only.
13. Complete Supabase Site URL / redirect configuration and Google OAuth origin / callback configuration.
14. Run **Verify TPP Pilot Deployment** again with public HTTPS verification enabled.
15. Perform Platform Owner, administrator, volunteer-teacher, and negative-authorization browser acceptance.
16. Retain the exact deployed image digest, task-definition revision, verification runs, and browser evidence in the acceptance record.

Do not bypass a failed preflight by weakening validation or moving protected values into repository files.

## Volunteer-teacher acceptance

The volunteer teacher must be able to:

1. authenticate with an approved Google school account;
2. see only the roles granted by the governed access list;
3. import or select a sequenced curriculum;
4. configure one or more independent teaching assignments;
5. configure period, block, selected-weekday, or custom meeting patterns;
6. generate a week using actual instructional minutes and calendar exceptions;
7. save and reopen a weekly draft;
8. complete nonblank Literacy Standards and ACT Preparation fields;
9. export each approved Anniston document and the combined packet;
10. validate every scheduled lesson as completed, modified, missed, or skipped;
11. carry missed instruction into the next week without changing unrelated curricula;
12. see the teacher-and-curriculum-only boundary throughout the workflow.

The Platform Owner account must separately confirm that it retains both Platform Owner and Teacher capabilities in the same authenticated session. An unapproved school account and a non-school account must receive no application data.

## Operational acceptance

Before volunteer access:

- **Verify TPP Pilot Deployment** passes for the exact accepted commit;
- public HTTPS `/health` returns HTTP 200 without a certificate warning;
- ECS desired and running counts match with no pending task;
- the active task definition references an immutable ECR digest tagged with the accepted commit;
- all load-balancer targets are healthy;
- the container serves the authenticated React application and governed API from one origin;
- Supabase migration history matches the repository migration set;
- the approved access list is active and no unapproved school account receives a profile;
- application logs are present in the dedicated 30-day CloudWatch log group;
- no secret-bearing variable appears in task-definition plaintext environment values;
- all required runtime secrets are mapped through ECS secret references;
- no secret value appears in workflow logs, issues, pull-request comments, or acceptance evidence;
- no student table, roster, student account, or student-specific field is used in the pilot.

## Rollback

Use `docs/PILOT_ROLLBACK.md` to identify and recover the failing layer.

Each subsequent deployment records the prior ECS task-definition ARN before mutation. A failed ECS deployment uses the service deployment circuit breaker; a manual application rollback uses the recorded prior task definition and exact image. Database migrations require separate review and are not automatically reversed by an application rollback. DNS, TLS, OAuth, access-list, and later Route 53 rollback are separate controlled actions.

## Human-controlled gates

The following are intentionally not automated from source control:

- pull-request merge approval;
- protected-environment approval for database, provisioning, infrastructure, TLS, application deployment, preflight, and verification workflows;
- the actual staff access-list secret and academic-year dates;
- ACM DNS-validation record creation in Cloudflare;
- the final Cloudflare application CNAME;
- Supabase and Google console redirect/origin changes;
- live browser acceptance with approved school accounts;
- the later coordinated Route 53 nameserver migration.

## Route 53 preparation boundary

The Route 53 hosted zone and record inventory may be prepared while Cloudflare remains authoritative. Do not change registrar nameservers until:

- Guided Scholar and TPP are both in accepted stable states;
- every Cloudflare record has been inventoried and reproduced;
- email, OAuth, Supabase, ACM, verification, and application records are validated;
- DNSSEC handling and rollback nameservers are documented;
- an explicit coordinated migration is authorized.

Do not migrate `planner.guidedscholar.ai` independently from the `guidedscholar.ai` parent zone.

## Rollout boundary

The first teacher exercise is a controlled volunteer-teacher pilot. Full-school rollout remains a separate decision and is contingent on pilot acceptance, defect resolution, administrator validation, monitoring review, and explicit authorization.
