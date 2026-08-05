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

- `Dockerfile` — combined React/FastAPI production image, non-root runtime, application health check
- `infra/pilot-stack.yml` — isolated AWS pilot stack
- `.github/workflows/apply-pilot-database.yml` — reviewed Supabase migration preview/application
- `.github/workflows/provision-pilot-access.yml` — transaction-safe school, academic-year, and staff-access provisioning
- `.github/workflows/bootstrap-pilot.yml` — first infrastructure and exact-image deployment plus ACM request
- `.github/workflows/enable-pilot-tls.yml` — issued-certificate attachment and DNS handoff
- `.github/workflows/deploy-pilot.yml` — subsequent exact-digest ECS deployments with rollback evidence

All mutating workflows use the protected `tpp-pilot` GitHub environment. No application, database, DNS, or certificate mutation occurs merely because code is pushed or a pull request is opened.

## Controlled release sequence

1. Review CI, the pull-request diff, and the approved Anniston PDF artifacts.
2. Approve and merge the release pull request.
3. Preview and then apply the Supabase migrations through the protected migration workflow.
4. Provision Anniston High School, the active academic year, and the approved staff allowlist through the protected provisioning workflow.
5. Bootstrap the AWS stack and first exact image.
6. Add the returned ACM validation CNAME to Cloudflare.
7. When ACM is `ISSUED`, attach TLS through the protected TLS workflow.
8. Add Cloudflare CNAME `planner` to the returned ALB DNS target, initially DNS only.
9. Complete Supabase Site URL / redirect configuration and Google OAuth origin / callback configuration.
10. Perform owner, administrator, and volunteer-teacher browser acceptance.
11. Retain the exact deployed image digest and task-definition revision in the acceptance record.

## Monday volunteer-teacher acceptance

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

The platform-owner account must separately confirm that it retains both Platform Owner and Teacher capabilities in the same authenticated session.

## Operational acceptance

Before volunteer access:

- ALB `/health` returns HTTP 200;
- ECS desired and running counts match;
- the active task definition references the exact ECR digest produced from the accepted commit;
- the container serves the authenticated React application and governed API from one origin;
- Supabase migration history matches the repository migration set;
- the approved access list is active and no unapproved school account receives a profile;
- application logs are present in the dedicated 30-day CloudWatch log group;
- no secret value appears in workflow logs, task-definition plaintext environment variables, issues, or pull-request comments;
- no student table, roster, student account, or student-specific field is used in the pilot.

## Rollback

Each subsequent deployment records the prior ECS task-definition ARN before mutation. A failed ECS deployment uses the service deployment circuit breaker; a manual rollback uses the recorded prior task definition. Database migrations require separate review and are not automatically rolled back by an application rollback.

## Human-controlled gates

The following are intentionally not automated from source control:

- pull-request merge approval;
- protected-environment approval for database, provisioning, infrastructure, TLS, and application deployment workflows;
- the actual staff access-list secret and academic-year dates;
- ACM DNS-validation record creation in Cloudflare;
- the final Cloudflare application CNAME;
- Supabase and Google console redirect/origin changes;
- live browser acceptance with approved school accounts;
- the later coordinated Route 53 nameserver migration.

## Rollout boundary

The Monday exercise is a controlled volunteer-teacher pilot. Full-school rollout remains a separate decision at the end of the following week and is contingent on pilot acceptance, defect resolution, administrator validation, monitoring, and explicit authorization.
