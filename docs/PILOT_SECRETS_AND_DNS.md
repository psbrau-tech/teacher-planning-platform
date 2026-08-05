# Teacher Planning Platform Pilot Secrets and DNS

This document is the controlled setup checklist for `planner.guidedscholar.ai` while DNS remains in Cloudflare and the application is deployed in the existing AWS account in `us-east-2`.

## Do not commit secrets

Never place real keys in GitHub source files, `.env` files committed to the repository, screenshots, issues, pull-request comments, or chat messages.

Store production-preclearance and pilot secrets in **AWS Secrets Manager** in `us-east-2`. The ECS task definition should reference the secret ARNs and inject them as environment variables at runtime.

## Required runtime values

The backend uses the `TPP_` prefix.

| Environment variable | Source | AWS storage |
|---|---|---|
| `TPP_ENVIRONMENT` | literal value `pilot` | ECS environment variable, not secret |
| `TPP_PUBLIC_BASE_URL` | `https://planner.guidedscholar.ai` | ECS environment variable, not secret |
| `TPP_DATA_BOUNDARY` | `teacher-and-curriculum-only` | ECS environment variable, not secret |
| `TPP_SUPABASE_URL` | Supabase Project Settings → API → Project URL | ECS environment variable; may also be stored with the Supabase secret bundle |
| `TPP_SUPABASE_ANON_KEY` | Supabase Project Settings → API → publishable/anon key | AWS Secrets Manager |
| `TPP_SUPABASE_SERVICE_ROLE_KEY` | Supabase Project Settings → API → service-role key | AWS Secrets Manager; backend only |
| `TPP_DATABASE_URL` | Supabase Project Settings → Database → connection string | AWS Secrets Manager |
| `TPP_OPENAI_API_KEY` | New dedicated OpenAI project key | AWS Secrets Manager |
| `TPP_GOOGLE_OAUTH_CLIENT_ID` | Google Cloud OAuth web client | AWS Secrets Manager |
| `TPP_GOOGLE_OAUTH_CLIENT_SECRET` | Google Cloud OAuth web client | AWS Secrets Manager |
| `TPP_ALLOWED_EMAIL_DOMAINS` | approved district domains, comma-separated | ECS environment variable |
| `TPP_ALLOWED_PILOT_EMAILS` | individually approved pilot accounts, comma-separated | ECS environment variable |

Recommended secret names:

- `tpp/pilot/supabase`
- `tpp/pilot/openai`
- `tpp/pilot/google-oauth`
- `tpp/pilot/database`

Each secret may be stored as JSON with clear keys, for example:

```json
{
  "TPP_SUPABASE_ANON_KEY": "...",
  "TPP_SUPABASE_SERVICE_ROLE_KEY": "..."
}
```

## Supabase setup

1. Record the project URL, publishable/anon key, service-role key, and database connection string.
2. Keep the service-role key server-side only.
3. Apply the SQL migrations in `supabase/migrations` in filename order.
4. Configure Google as an authentication provider only after the Google OAuth client exists.
5. Add the eventual application callback URL required by the chosen authentication flow.

The exact callback path must match the deployed implementation. Do not guess it in Google or Supabase before the application route is finalized.

## OpenAI setup

Create a dedicated OpenAI project for TPP rather than reusing the Guided Scholar project. Create one restricted API key for the backend and store it in AWS Secrets Manager as `TPP_OPENAI_API_KEY`.

Do not place the key in frontend code. OpenAI requests must originate from the backend.

## Temporary Cloudflare subdomain

Because the `guidedscholar.ai` authoritative DNS is still hosted in Cloudflare, create the subdomain in **Cloudflare DNS** for now.

1. Open Cloudflare → `guidedscholar.ai` → DNS → Records.
2. Add a `CNAME` record.
3. Name: `planner`.
4. Target: the AWS Application Load Balancer DNS name created for TPP.
5. Initially set Proxy status to **DNS only** while TLS, redirects, health checks, and host routing are validated directly against AWS.
6. After AWS validation, Cloudflare proxying may be enabled only if it is intentionally retained for the interim period and no authentication or websocket behavior is disrupted.

Do not create the record until the AWS ALB target and certificate are ready. A premature record will only point users to an incomplete service.

## TLS certificate

Request or extend an AWS Certificate Manager certificate in `us-east-2` for:

- `planner.guidedscholar.ai`

While DNS remains in Cloudflare, ACM DNS validation records must be added to Cloudflare. Keep those validation CNAME records when the application CNAME is later migrated to Route 53.

## Final DNS migration

When `guidedscholar.ai` moves to Route 53, recreate the `planner` record in the Route 53 hosted zone and validate resolution before removing the Cloudflare zone from the production path.

## Manual handoff values

The developer needs the following values entered into AWS, not posted in GitHub or chat:

- Supabase project URL
- Supabase anon/publishable key
- Supabase service-role key
- Supabase database URL
- OpenAI API key
- Google OAuth client ID and secret
- approved district email domain and/or pilot email allowlist
- final AWS ALB DNS target for the Cloudflare `planner` CNAME
