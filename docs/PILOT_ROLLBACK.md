# TPP Controlled Pilot Rollback Runbook

## Purpose

This runbook defines controlled recovery for the Teacher Planning Platform pilot. It separates application, database, access, TLS, DNS, and identity-provider rollback so a correction in one layer does not create unnecessary changes in another.

The pilot boundary remains teacher and curriculum data only. No student data may be introduced during recovery or troubleshooting.

## Operating principles

1. Diagnose the failing layer before changing anything.
2. Preserve the exact deployed commit, image digest, task-definition revision, workflow run, and timestamps.
3. Prefer the smallest reversible change that restores the last accepted state.
4. Do not treat application rollback as database rollback.
5. Do not delete retained ECR images, CloudWatch logs, CloudFormation stacks, ACM validation records, or the former DNS zone during an active incident.
6. Do not expose secrets, staff access-list JSON, tokens, or school-account addresses in incident comments.
7. Require explicit approval for every mutating rollback action.

## Severity and immediate response

| Condition | Classification | Immediate action |
|---|---|---|
| Unauthorized account receives application data | Release blocker / security incident | Disable affected access path, stop pilot use, preserve logs, investigate authorization boundary |
| Student-specific data appears or is entered | Release blocker / boundary incident | Stop pilot use, preserve evidence, remove data only through an approved remediation plan |
| Application unavailable for all users | Release blocker | Determine DNS, TLS, ALB, ECS, or application layer before rollback |
| Exports silently truncate or contain wrong identifiers | Release blocker | Suspend document submission and revert application if regression is deployment-specific |
| One workflow action fails without user-visible impact | High or lower | Preserve failure logs and correct the isolated layer |
| Cosmetic or instructional issue | Medium/Low | Record defect; rollback normally unnecessary |

## Evidence to capture before mutation

- incident start time in UTC and America/Chicago;
- current Git commit and GitHub workflow run;
- exact ECR image URI and digest;
- current and previous ECS task-definition ARNs;
- ECS desired, running, and pending counts;
- primary deployment rollout state;
- target-group health;
- CloudFormation stack status and recent events;
- ACM certificate status;
- current DNS answers and authoritative nameservers;
- Supabase and Google callback/origin configuration relevant to the failure;
- redacted browser or HTTP evidence;
- application log references without secret values.

Run **Verify TPP Pilot Deployment** when AWS is reachable. It is read-only and can establish most of the operational baseline.

## Decision tree

### Application defect with healthy infrastructure

Indicators:

- ALB targets are healthy;
- ECS service is stable;
- DNS and certificate are correct;
- failure began with a specific application deployment.

Action:

1. Identify the last accepted ECS task definition and exact image digest.
2. Confirm that the prior task definition uses the same governed secrets and data boundary.
3. Update the ECS service to the prior task definition through an explicitly approved rollback action.
4. Wait for service stability.
5. verify target health, `/health`, authentication boundary, and primary workflow.
6. Record the restored task definition and image digest.

Do not rerun database migrations merely because the application was rolled back.

### Failed deployment still rolling out

Indicators:

- ECS primary deployment is `IN_PROGRESS` or `FAILED`;
- running count differs from desired count;
- unhealthy targets correspond to the new task definition.

Action:

1. Allow the configured ECS deployment circuit breaker to complete its automatic rollback when safe.
2. Do not start a competing deployment while rollback is in progress.
3. After stabilization, confirm which task definition is active.
4. Run read-only deployment verification.
5. Correct the root cause in a new PR and release through the normal exact-image workflow.

### Infrastructure or CloudFormation failure

Indicators:

- stack is in a rollback or failed state;
- required outputs are missing;
- ALB, target group, service, or IAM resources were not created or updated successfully.

Action:

1. Review CloudFormation events and identify the first failing resource.
2. Do not delete the stack as the first response.
3. If CloudFormation automatically rolls back, verify retained resources and stack state.
4. Correct the template or permissions through review and CI.
5. Deploy only after the change set or workflow scope is understood.
6. Preserve retained ECR and CloudWatch resources.

### Database migration defect

Indicators:

- application and infrastructure are healthy;
- a schema, policy, function, or data behavior changed after migration;
- migration history confirms the new migration was applied.

Action:

1. Stop application actions that could compound the defect.
2. Preserve the migration history and database evidence.
3. Determine whether a forward corrective migration is safer than reversal.
4. Prefer a reviewed forward migration for PostgreSQL/Supabase schema and policy corrections.
5. Use a destructive reverse migration only with an explicit data-impact review and backup/restore plan.
6. Do not edit an already applied migration file to disguise history.
7. Retest authorization, row-level security, persistence, exports, and Friday carry-forward after correction.

Application rollback does not reverse a database migration.

### Staff access-list defect

Indicators:

- approved user is denied;
- unapproved user is active;
- role set is wrong;
- Platform Owner lost either `platform_admin` or `teacher`.

Action:

1. Preserve the current allowlist count and affected governed record without exposing email addresses publicly.
2. Correct `TPP_PILOT_ACCESS_JSON` in the protected GitHub environment.
3. Run **Preflight TPP Pilot Release** after it is available on `main`.
4. Run **Provision TPP Pilot Access** with reviewed dates and access data.
5. Use `replace_access=true` only when deliberately deactivating records omitted from the approved complete list.
6. Retest approved, unapproved-school, and non-school accounts.

If an unapproved account received access, treat the event as a security incident rather than routine provisioning.

### Google or Supabase authentication defect

Indicators:

- OAuth redirects fail;
- provider callback reports mismatch;
- login succeeds at Google but not Supabase;
- Supabase session exists but application authorization fails unexpectedly.

Action:

1. Separate authentication from application authorization.
2. Compare the configured Supabase callback URL, Site URL, allowed redirects, and Google authorized origins/redirects with the accepted values.
3. Revert only the incorrect console entry to the last accepted configuration.
4. Do not weaken the `anniston.k12.al.us` domain restriction or database allowlist as a workaround.
5. Clear the test browser session and retest approved and unapproved accounts.

### TLS or certificate defect

Indicators:

- certificate warning;
- ACM status is not `ISSUED`;
- HTTPS listener is absent or references the wrong certificate;
- hostname is not covered.

Action:

1. Preserve the ACM validation CNAME.
2. Confirm the certificate region is `us-east-2` and the domain is `planner.guidedscholar.ai`.
3. If the wrong certificate was attached, redeploy the last accepted certificate ARN through the protected TLS workflow.
4. If HTTPS is not accepted, keep the pilot closed; do not direct teachers to an insecure endpoint.
5. Do not delete an ACM certificate until it is confirmed unused and replacement acceptance is complete.

### Cloudflare application-record defect

Indicators:

- `planner.guidedscholar.ai` resolves to the wrong target;
- Cloudflare proxy behavior interferes with direct AWS acceptance;
- ALB is healthy by direct inspection but public hostname is unavailable.

Action:

1. Record the current DNS answer, Cloudflare record value, proxy state, and TTL.
2. Restore the last accepted `planner` CNAME target and DNS-only state.
3. Wait for the configured TTL and verify from multiple resolvers.
4. Retest HTTPS and authentication.
5. Leave the ACM validation CNAME in place.

Do not change the parent-zone nameservers during an application-record rollback.

### Route 53 delegation rollback

This applies only after a future coordinated migration of `guidedscholar.ai` and `planner.guidedscholar.ai`.

Indicators:

- authoritative Route 53 zone is missing required records;
- Guided Scholar, TPP, email, authentication, or certificate validation fails after registrar delegation;
- failures are attributable to delegation rather than application infrastructure.

Action:

1. Confirm the issue from authoritative DNS queries and compare against the pre-cutover inventory.
2. Correct missing or incorrect Route 53 records when the fix is clear and propagation risk is acceptable.
3. If broad service impact remains and rollback criteria are met, restore the former Cloudflare nameservers at the registrar.
4. Keep the former Cloudflare zone complete and unchanged until migration acceptance is closed.
5. Monitor authoritative nameservers and critical services through propagation.
6. Record the rollback time and restore normal TTLs only after stability.

DNSSEC must be handled deliberately. Do not leave a stale DS record that points to keys no longer serving the zone.

## Validation after any rollback

At minimum, verify:

- CloudFormation stack is stable;
- ECS desired and running counts match;
- all registered targets are healthy;
- active task definition and image digest are recorded;
- `/health` succeeds through the accepted public path;
- certificate is valid for the hostname;
- approved account signs in with the correct role set;
- unapproved school account receives no application data;
- direct unauthenticated API request is rejected;
- a saved synthetic weekly draft reopens;
- one Anniston export renders correctly;
- no student-data feature or field is present.

Run the full browser-acceptance package when the rollback affects authentication, persistence, exports, weekly generation, validation, or carry-forward.

## Closeout record

| Field | Value |
|---|---|
| Incident ID | |
| Start/end time | |
| Affected layer | Application / AWS / Database / Access / OAuth / TLS / DNS |
| User impact | |
| Root cause | |
| Prior accepted state | |
| Rollback or correction performed | |
| Approval reference | |
| Restored commit/image/task definition | |
| Verification run | |
| Browser retest | |
| Residual risk | |
| Follow-up PR or migration | |

The pilot may reopen only after the affected layer and its dependent acceptance gates pass.
