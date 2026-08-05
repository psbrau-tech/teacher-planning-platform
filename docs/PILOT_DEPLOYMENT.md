# TPP Controlled Pilot Deployment

## Approved pilot decisions

- Hostname: `planner.guidedscholar.ai`
- AWS account: existing Brau Consulting / Guided Scholar AWS account
- AWS region: `us-east-2`
- Environment isolation: separate TPP pilot stack and runtime resources
- Supabase project: `teacher-planning-platform-pilot`
- Authentication: Google SSO using approved school accounts
- OpenAI: separate TPP API project
- Data boundary: teacher and curriculum data only; no student data

## Monday pilot gate

A volunteer teacher must be able to:

1. authenticate with an approved Google school account;
2. configure one or more teaching assignments;
3. configure period, block, or mixed schedules;
4. load or enter curriculum lessons;
5. prepare and edit the following week's plan;
6. validate completed, modified, missed, or skipped instruction;
7. carry missed instruction forward without changing unrelated curricula;
8. export the three Anniston-themed planning documents and combined packet.

## Secret placement

### GitHub Actions environment: `tpp-pilot`

Only deployment identifiers and non-privileged public configuration belong in GitHub:

- `TPP_AWS_REGION`
- `TPP_AWS_ROLE_ARN`
- `TPP_ECR_REPOSITORY`
- `TPP_ECS_CLUSTER`
- `TPP_ECS_SERVICE`
- `TPP_TASK_DEFINITION_FAMILY`
- `TPP_SUPABASE_URL`
- `TPP_SUPABASE_ANON_KEY`

The deployment workflow must use GitHub OIDC. Long-lived AWS access keys are prohibited.

### AWS Secrets Manager

Runtime secrets belong in AWS Secrets Manager under the pilot namespace:

- `tpp/pilot/supabase-url`
- `tpp/pilot/supabase-anon-key`
- `tpp/pilot/supabase-service-role-key`
- `tpp/pilot/database-url`
- `tpp/pilot/openai-api-key`
- `tpp/pilot/google-oauth-client-id`
- `tpp/pilot/google-oauth-client-secret`

The ECS task execution role receives only `secretsmanager:GetSecretValue` access to these exact secret ARNs. Secret values must not be committed, printed in CI logs, placed in task-definition plaintext environment variables, or pasted into issues or pull requests.

## Google SSO configuration

TPP uses a separate OAuth application configuration from Guided Scholar even when the implementation pattern is reused.

Required configuration:

- Supabase Google provider enabled;
- Google OAuth client ID and secret stored in the approved secret locations;
- Supabase callback URL added to the Google OAuth client;
- `https://planner.guidedscholar.ai` added to authorized origins when applicable;
- access restricted to approved school-domain accounts or an explicit pilot allowlist;
- authenticated identity linked to a governed TPP teacher profile before application access is granted.

Authentication alone does not create authorization. A valid Google account without an active TPP teacher or administrator record receives no application data.

## DNS and TLS

DNS is not changed until the pilot service endpoint and certificate validation records are known.

Expected final record:

- name: `planner.guidedscholar.ai`
- type: Alias A/AAAA to the TPP application load balancer, or CNAME when the selected AWS service requires it
- TLS: AWS Certificate Manager certificate covering `planner.guidedscholar.ai`

## Pilot boundary notice

Display during onboarding and in the application footer:

> This controlled pilot is limited to teacher lesson-planning and curriculum data. Do not enter student names, student IDs, grades, IEP information, accommodations tied to named students, or other personally identifiable student information.

## Human-owned prerequisites

- create the Supabase project;
- create the separate OpenAI API project and budget alert;
- obtain the approved ACS/Bulldog logo asset;
- provide the pilot teacher and administrator allowlists;
- identify the school Google Workspace domain;
- approve the final Anniston-themed document samples;
- create DNS records after exact values are supplied;
- approve and merge the release pull request.

## Release boundary

Monday is a controlled volunteer-teacher pilot. Schoolwide deployment is a separate gate after pilot defects, onboarding, administrator controls, and operational monitoring are validated.
