# Teacher Planning Platform — Subprocessor List

**Provider:** Brau Consulting LLC  
**Status:** Pre-Release Draft — Reconciled to Controlled Pilot; Final Verification Required Before Publication  
**Original baseline:** 2026-08-08  
**Post-pilot reconciliation:** 2026-08-14

Brau Consulting LLC uses third-party service providers to operate Teacher Planning Platform (TPP). This list identifies material providers evidenced by the controlled-pilot architecture and source-controlled release direction. It does not authorize TPP to receive student data; the TPP no-student-data boundary applies regardless of provider capability.

| Provider | Purpose | Data potentially processed | Current controlled-pilot evidence / remaining verification |
|---|---|---|---|
| Amazon Web Services (AWS) | Application hosting, networking, load balancing, container registry/runtime, secrets, logging, deployment infrastructure, and professional operational email delivery when the separately governed SES path is activated | Educator/account request metadata, professional planning content transiting the application, operational logs, protected secrets/configuration as applicable; for enabled SES notices, recipient professional email address and the minimized operational email content approved for that notice | Deployed pilot infrastructure is defined in `us-east-2` and includes ECS/Fargate, ALB, ECR, CloudWatch Logs and Secrets Manager/protected secret injection. Application logs are configured for 30-day retention. SES notification infrastructure is source-controlled but remains fail-closed until identity verification, IAM/runtime configuration, privacy/Help review, and controlled activation are completed. Any isolated scheduled-digest worker is also a separate controlled activation. Exact AWS customer-data paths, SES account status/settings, and service-specific contractual settings must be rechecked before publication. |
| Supabase | Database, authentication and related backend platform services | Professional account identifiers, role/authorization records, curriculum/planning content, standards selections/provenance, AI decision metadata, validation/reflection/submission records, professional analytics/notification-delivery records, audit/application records as implemented | Supabase is implemented in the controlled pilot. Source-controlled scheduled-notification design uses a separately isolated service-role worker rather than exposing an elevated credential to the interactive web task/browser. Final project region, backup/restore retention, enabled services, DPA posture and production configuration must be verified before publication. |
| OpenAI | Approved generative-AI planning assistance and post-submission professional Reflection Intelligence | Only the permitted professional context required for an approved AI request, which may include teacher-authored reflection content after explicit submission for Reflection Intelligence; bounded AI usage/operational metadata | OpenAI is implemented in the controlled pilot and the runtime API credential is delivered through the protected AWS secret path. The required Weekly Reflection / PLC Discussion is teacher-authored; OpenAI is not used to suggest, generate, complete, or rewrite those required responses. Student data is prohibited. Current provider terms/data controls and the production account's model-training/data-sharing configuration must be reverified immediately before publication. |

## Development and operational vendors

GitHub is used for source control, pull requests, CI/CD and deployment workflows. TPP customer planning content is not intended to be stored in source control or ordinary CI artifacts. If future logging, support, diagnostics, deployment evidence, issue attachments, or workflow artifacts cause customer personal/content data to be routinely processed by GitHub or another operational provider, that provider must be evaluated for inclusion as a material subprocessor before the change is released.

## Services not automatically treated as subprocessors

DNS, certificate, analytics, monitoring, customer-support, payment, document-conversion, or other services are not listed as production subprocessors merely because they are contemplated or used elsewhere by Brau Consulting. The final list must reflect the actual TPP customer/account data flow.

Professional operational email is treated here as part of the existing AWS relationship because the approved implementation uses Amazon SES. The source-controlled SES path does not establish that email delivery is active in the controlled pilot; activation and final provider/configuration verification remain separate release steps.

The current first-party active-interaction product telemetry and deterministic formative-assessment classification do not introduce a new third-party analytics vendor. If third-party analytics, session replay, advertising, or behavioral tracking is later added, it requires privacy/governance review and subprocessor evaluation before production use.

## Provider-change governance

Before adding or replacing a provider that will process TPP personal or customer content, Brau Consulting will:

1. document the purpose and exact data categories;
2. review the provider's privacy, security, contractual, retention, location, DPA and model-training/data-use terms as applicable;
3. confirm the provider does not undermine the no-student-data boundary;
4. update this list and any affected Privacy Policy, AI Notice, Security & Data Practices, institutional agreement or data-flow documentation;
5. satisfy any customer notice or contractual requirement that applies to the change.

## Final pre-publication verification

Before this list is published as final, verify and record:

- the deployed AWS Region and material customer-data services;
- AWS SES sender identity/account sending status and any relevant service configuration if professional notifications are activated;
- any isolated scheduled-notification task, secret, IAM, and retention path that is activated;
- Supabase project region, backups, retention, enabled services and DPA posture;
- OpenAI production account/project configuration, applicable agreement/DPA and customer-content data-use setting;
- whether any email, support, monitoring, payment, analytics, DNS/security or other provider routinely processes TPP personal/customer content;
- whether institutional contracts require advance notice of additions/replacements.

## Primary-source verification references

- AWS Customer Agreement, AWS Data Processing Addendum, and applicable SES service documentation/terms — current versions and production account configuration must be checked at release.
- Supabase Data Processing Addendum — current version must be checked at release.
- OpenAI Services Agreement, Service Terms, Data Processing Addendum and business/API data-use commitments — current versions must be checked at release.

## Contact

Questions regarding subprocessors: [PRIVACY/SECURITY EMAIL TO BE APPROVED].
