# Teacher Planning Platform — Subprocessor List

**Provider:** Brau Consulting LLC  
**Status:** Pre-Release Draft — Must Be Reverified Before Publication  
**Baseline:** 2026-08-08

Brau Consulting LLC uses third-party service providers to operate Teacher Planning Platform (TPP). This list identifies material providers currently evidenced by the TPP architecture. It does not authorize TPP to receive student data; the TPP no-student-data boundary applies regardless of provider capability.

| Provider | Purpose | Data potentially processed | Current evidence / notes |
|---|---|---|---|
| Amazon Web Services (AWS) | Application hosting, networking, container registry/runtime, secrets, infrastructure logging and related cloud services | Educator/account request metadata, professional planning content transiting the application, operational logs, encrypted secrets/configuration as applicable | Pilot runtime is deployed in `us-east-2`; exact production service inventory must be reverified |
| Supabase | Database, authentication and related backend platform services | Professional account identifiers, authorization records, curriculum/planning content, standards selections/provenance, audit/application records as implemented | Project region, backup retention, exact enabled services, and DPA posture must be reverified before publication |
| OpenAI | Teacher-invoked generative AI planning assistance | Only the permitted professional planning context required for an AI request; bounded AI usage metadata | Student data is prohibited. Current OpenAI business/API terms state Customer Content is not used to improve services unless the customer explicitly agrees; production account configuration must be reverified |

## Development and operational vendors

GitHub is used for source control, pull requests, CI/CD and deployment workflows. TPP customer content is not intended to be stored in the source repository or CI artifacts. If future logging, support, diagnostics, or deployment workflows cause customer personal data to be routinely processed by GitHub or another operational provider, that provider must be evaluated for inclusion as a material subprocessor before the change is released.

DNS, certificate, email, analytics, monitoring, customer-support, payment, or other services are not listed as production subprocessors until their actual use and data flow are verified. The final list must reflect deployed reality rather than planned architecture.

## Provider-change governance

Before adding or replacing a provider that will process TPP personal or customer content, Brau Consulting will:
1. document the purpose and data categories;
2. review the provider's privacy, security, contractual, retention, and model-training/data-use terms as applicable;
3. confirm the provider does not undermine the no-student-data boundary;
4. update this list and any affected Privacy Policy or Security & Data Practices language;
5. satisfy any customer notice or contractual requirement that applies to the change.

## Primary-source verification references

- AWS Customer Agreement and AWS Data Processing Addendum — current versions must be checked at release.
- Supabase Data Processing Addendum — current version must be checked at release.
- OpenAI Services Agreement, Service Terms, Data Processing Addendum, and business-data privacy commitments — current versions must be checked at release.

## Contact

Questions regarding subprocessors: [PRIVACY/SECURITY EMAIL TO BE APPROVED].
