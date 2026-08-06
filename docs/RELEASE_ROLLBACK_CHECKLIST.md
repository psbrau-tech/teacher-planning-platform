# TPP Pilot Release and Rollback Checklist

## Release evidence

Record before each production-affecting action:

- accepted commit SHA;
- immutable ECR image digest;
- current and candidate ECS task-definition ARNs;
- CloudFormation stack status;
- ALB DNS name and target-health state;
- ACM certificate ARN and status;
- current Cloudflare records relevant to `planner.guidedscholar.ai`;
- Supabase migration history;
- approved staff-access record count, without publishing staff addresses.

## Application rollback

Use when the new task definition is unhealthy or a verified application regression exists.

1. Stop additional deployment actions.
2. Preserve logs and the failed task-definition ARN.
3. Confirm the prior known-good task definition and immutable image digest.
4. Update the ECS service to the prior task definition through the governed rollback procedure.
5. Wait for service stability and matching desired/running counts.
6. Verify ALB target health and `/health`.
7. Repeat authentication and authorization smoke checks.
8. Record the rollback disposition and defect link.

Application rollback does not reverse database migrations.

## Database response

Database migrations are reviewed separately and are not automatically rolled back.

- Do not run an ad hoc down migration.
- Preserve the exact migration history and failure evidence.
- Determine whether the corrective action is a forward migration, data repair, or application rollback.
- Require explicit review and protected-environment approval before any database correction.
- Preserve the teacher-and-curriculum-only boundary.

## TLS and application DNS rollback

If HTTPS or the new application CNAME fails:

1. Keep the ACM validation CNAME in place.
2. Confirm certificate status and listener configuration.
3. If necessary, remove or restore only the `planner` application record to its previous value.
4. Do not change registrar nameservers as part of an application rollback.
5. Revalidate Guided Scholar records before touching the parent zone.

## Route 53 delegation rollback

Use only after a coordinated nameserver migration has been attempted.

1. Preserve both the former Cloudflare zone and the Route 53 hosted zone.
2. Confirm the registrar's current nameserver set.
3. If required, restore the complete former Cloudflare nameserver delegation.
4. Monitor authoritative responses from multiple resolvers.
5. Recheck Guided Scholar, TPP, OAuth callbacks, email records, and ACM validation.
6. Do not delete either zone until propagation and operational acceptance are complete.

## Authentication rollback

- Do not weaken the school-domain or database allowlist controls.
- Restore the last known-good Supabase Site URL, allowed redirects, and Google OAuth origin/callback configuration as one coordinated set.
- Test Platform Owner, administrator, teacher, unapproved-school-account, and non-school-account behavior.
- Never grant access merely because Google authentication succeeded.

## Stop conditions

Stop and require human authorization when a correction would:

- mutate Supabase or production AWS resources;
- alter Cloudflare, Route 53, registrar, ACM, or OAuth configuration;
- change the approved staff access list;
- reduce Platform Owner dual-role access;
- introduce student data or student accounts;
- execute a migration, deployment, rollback, or DNS cutover.
