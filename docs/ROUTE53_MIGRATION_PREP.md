# Guided Scholar and TPP Route 53 Migration Preparation

## Current decision

Prepare the Route 53 hosted zone and migration evidence now, but keep Cloudflare authoritative until both Guided Scholar and the Teacher Planning Platform are stable and the coordinated migration is explicitly approved.

Do not migrate `planner.guidedscholar.ai` independently. The final delegation change must account for the complete `guidedscholar.ai` zone, including Guided Scholar, TPP, authentication, email, certificate validation, and ownership-verification records.

Creating and populating a Route 53 hosted zone does not affect public traffic until the registrar delegation is changed to the Route 53 name servers.

## Phase 1 — Inventory the authoritative Cloudflare zone

Export the Cloudflare DNS zone and retain a dated, access-controlled copy outside the repository when it contains operationally sensitive information.

Create a record inventory covering at least:

- apex `guidedscholar.ai`;
- `www.guidedscholar.ai`;
- Guided Scholar application hostnames, including `app.guidedscholar.ai`;
- `planner.guidedscholar.ai`;
- ACM validation CNAMEs;
- Supabase and Google ownership or callback verification records;
- MX records;
- SPF, DKIM, and DMARC TXT records;
- CAA records;
- wildcard records;
- SRV records;
- any redirects, workers, tunnels, or other behavior that is not represented by ordinary DNS records.

For each record, capture:

- record name;
- type;
- value;
- TTL;
- Cloudflare proxy state;
- purpose or owning service;
- whether the record is production-critical;
- how the record will be represented in Route 53.

Cloudflare proxy state is not a portable DNS-record property. A proxied Cloudflare hostname must be deliberately replaced with direct AWS routing or another approved edge path before Cloudflare is removed.

## Phase 2 — Build the inactive Route 53 zone

1. Create one public hosted zone for `guidedscholar.ai` in the approved AWS account.
2. Retain the Route 53-assigned NS and SOA records.
3. Import or recreate all required Cloudflare records.
4. Normalize provider-specific exports before import:
   - ensure CNAME, MX, NS, PTR, and SRV targets are fully qualified where required;
   - preserve TXT content exactly, including SPF, DKIM, DMARC, and verification strings;
   - review apex behavior because Cloudflare CNAME flattening does not transfer directly;
   - translate eligible AWS endpoints to Route 53 alias records where appropriate;
   - do not copy Cloudflare-specific proxy settings as though they were DNS values.
5. Add the final TPP application and ACM validation records once those values exist.
6. Do not change registrar name servers during this phase.

## Phase 3 — Compare and validate

Compare the Cloudflare and Route 53 zones record by record. Differences must be classified as:

- exact match;
- intentional AWS alias conversion;
- intentional Cloudflare-proxy removal;
- obsolete record approved for retirement;
- unresolved discrepancy blocking migration.

Validate critical names directly against the Route 53 authoritative name servers before delegation. Test at least:

- Guided Scholar apex and application hostnames;
- TPP hostname;
- MX records;
- SPF, DKIM, and DMARC;
- ACM validation records;
- Supabase and Google verification records;
- any API or callback hostname used by either product.

Record the expected answer, actual answer, Route 53 name server queried, and validation timestamp.

## Phase 4 — Prepare the migration window

Before changing delegation:

1. Confirm Guided Scholar is in a stable release state.
2. Complete TPP pilot deployment, TLS, OAuth, and browser acceptance.
3. Ensure no certificate issuance, certificate renewal, OAuth cutover, or other operation depends on concurrent DNS changes.
4. Freeze nonessential DNS edits. Any required change during preparation must be made in both Cloudflare and Route 53.
5. Lower the applicable NS TTLs in advance. AWS recommends a temporary value between 60 and 900 seconds.
6. Wait for the prior TTL period to expire before changing delegation.
7. Determine whether DNSSEC is enabled:
   - if enabled, remove the existing DS record at the parent before migration;
   - enable Route 53 DNSSEC and establish the new chain of trust only after the new zone is authoritative and stable.
8. Capture the current Cloudflare name servers and registrar configuration for rollback.
9. Define explicit rollback thresholds for website availability, authentication, email, and certificate validation.

## Phase 5 — Coordinated delegation cutover

1. Perform one final Cloudflare-to-Route 53 record comparison.
2. Confirm both applications and all critical services are healthy before the change.
3. Change the registrar delegation from the Cloudflare name servers to the four Route 53 name servers.
4. Monitor:
   - `guidedscholar.ai`;
   - `app.guidedscholar.ai`;
   - `planner.guidedscholar.ai`;
   - Google and Microsoft authentication where applicable;
   - Supabase authentication callbacks;
   - inbound and outbound email DNS dependencies;
   - ACM certificate status and validation;
   - application and ALB health.
5. Query multiple public recursive resolvers and the authoritative Route 53 servers.
6. If critical traffic or authentication fails, restore the prior registrar name servers and diagnose before attempting another cutover.

## Phase 6 — Stabilization and closeout

- Keep the Cloudflare zone and records intact for at least 48 hours after delegation changes.
- Continue monitoring through the expected propagation period.
- Restore normal Route 53 NS TTL values after stability is confirmed.
- Re-enable DNSSEC and publish the new DS record if DNSSEC is part of the approved target state.
- Preserve the final zone export, comparison evidence, registrar change record, validation results, and rollback decision log.
- Do not delete the Cloudflare zone until the migration is formally accepted.

## Migration acceptance criteria

The migration is accepted only when:

- Route 53 is authoritative for the complete `guidedscholar.ai` zone;
- Guided Scholar and TPP resolve correctly from multiple networks and resolvers;
- all production application health checks pass;
- authentication callbacks work;
- email DNS records validate;
- ACM validation and renewal records remain present;
- no critical record is dependent on an unrecognized Cloudflare-only feature;
- DNSSEC is either deliberately disabled for the transition or successfully re-established;
- the previous Cloudflare configuration remains available for the required rollback-retention period.

## Reference basis

- AWS Route 53: migrating DNS service for a domain that is in use.
- AWS Route 53: hosted-zone migration preparation, comparison, delegation, TTL, DNSSEC, and rollback retention.
- Cloudflare DNS: zone record export and import behavior.

These references should be rechecked immediately before the migration window because provider procedures and console behavior can change.
