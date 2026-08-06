# Guided Scholar and TPP DNS Record Inventory

Use this worksheet before any coordinated migration from Cloudflare to Route 53. Do not place secret values in it.

## Zone metadata

| Item | Cloudflare | Route 53 candidate | Verified |
|---|---|---|---|
| Zone | `guidedscholar.ai` | `guidedscholar.ai` | |
| DNSSEC status | | | |
| Registrar nameservers | | Not changed during preparation | |
| SOA minimum/negative TTL | | | |
| Default record TTL policy | | | |

## Record inventory

Copy every active record. Add rows as needed.

| Name | Type | Cloudflare value/target | TTL | Proxy status | Route 53 value/target | Purpose | Owner | Verified |
|---|---|---|---:|---|---|---|---|---|
| `@` | | | | | | Apex/site | | |
| `www` | | | | | | Public website | | |
| `app` | | | | | | Guided Scholar app | | |
| `planner` | CNAME | | | DNS only during pilot acceptance | | TPP pilot | | |
| ACM validation name | CNAME | | | DNS only | | TPP certificate validation | | |

## Email and domain-authentication records

Inventory all records even when no application uses email directly.

| Name | Type | Current value | TTL | Route 53 value | Purpose | Verified |
|---|---|---|---:|---|---|---|
| `@` | MX | | | | Mail routing | |
| `@` | TXT | | | | SPF and other verification | |
| `_dmarc` | TXT | | | | DMARC | |
| DKIM selectors | CNAME/TXT | | | | DKIM | |

## Service-verification and authentication records

Include every Google, Microsoft, Supabase, AWS, vendor, and ownership-verification record.

| Name | Type | Current value | TTL | Route 53 value | Service | Verified |
|---|---|---|---:|---|---|---|
| | | | | | | |

## Cloudflare-only behavior review

Route 53 provides authoritative DNS but does not reproduce Cloudflare proxy behavior. Record every proxied hostname and its replacement design.

| Hostname | Cloudflare proxied? | Current Cloudflare behavior | Direct AWS behavior accepted? | Replacement required? | Verified |
|---|---|---|---|---|---|
| | | | | | |

Review WAF, CDN/caching, redirects, page rules, transform rules, origin certificates, Access policies, rate limits, and analytics separately from DNS records.

## Pre-cutover comparison

- [ ] Every Cloudflare record is represented or deliberately retired.
- [ ] Guided Scholar and TPP records are both present.
- [ ] MX, SPF, DKIM, and DMARC are preserved.
- [ ] ACM validation CNAME records are preserved.
- [ ] OAuth and domain-verification records are preserved.
- [ ] Alias/CNAME differences at the zone apex are resolved correctly.
- [ ] No Route 53 record contains a Cloudflare-proxied IP copied as if it were an origin.
- [ ] DNSSEC migration sequence is reviewed before nameserver changes.
- [ ] Monitoring and rollback checks are ready.
- [ ] Cloudflare will remain intact until post-cutover acceptance is complete.

## Cutover evidence

Record the approved window, previous and new nameservers, TTL preparation time, registrar change time, resolver checks, application checks, email checks, authentication checks, and final acceptance decision.
