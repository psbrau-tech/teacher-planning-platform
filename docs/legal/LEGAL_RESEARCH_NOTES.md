# TPP Legal / Vendor Research Notes

**Status:** Internal research support — not customer-facing legal advice  
**Last verified:** 2026-08-08

This file records primary/current sources used to support the pre-release packet. It exists so future reviews can re-check time-sensitive claims instead of relying on chat memory.

## Alabama data-security / breach law

**Alabama Data Breach Notification Act of 2018 — Ala. Code Title 8, Chapter 38**

Official Alabama Legislature chapter/section access:
- https://alison.legislature.state.al.us/code-of-alabama?section=8-38-12
- https://alison.legislature.state.al.us/code-of-alabama?section=8-38-8

The chapter includes provisions on reasonable security measures, breach investigation, individual notification, Attorney General notification, third-party-agent notification, and disposal of records containing sensitive personally identifying information. Applicability to a particular incident requires factual/legal analysis.

Do not turn the statutory notice periods into a blanket contractual promise without counsel review.

## OpenAI business/API data use

**OpenAI Services Agreement** — current agreement verified 2026-08-08:
- https://openai.com/policies/services-agreement/

The agreement effective January 1, 2026 states, among other things, that as between customer and OpenAI the customer retains ownership rights in Input and owns Output to the extent permitted by law, and that OpenAI will not use Customer Content to develop or improve the Services unless the customer explicitly agrees.

**OpenAI business data privacy/security page:**
- https://openai.com/business-data/

Current page states that business/API inputs and outputs are not used for model training by default.

**OpenAI Service Terms:**
- https://openai.com/policies/service-terms/

Current version observed as updated June 12, 2026.

These sources must be rechecked before publication and after a material provider/account/data-control change.

## AWS

**AWS Customer Agreement:**
- https://aws.amazon.com/agreement/

Current version observed as updated June 1, 2026. The agreement states that customers can specify AWS Regions for content and describes AWS access/use restrictions regarding customer content.

**AWS Data Processing Addendum guidance:**
- https://docs.aws.amazon.com/whitepapers/latest/navigating-gdpr-compliance/aws-data-processing-addendum-dpa.html

AWS states that its DPA applies automatically to customers using AWS services to process customer data under the described terms.

TPP-specific regional claims must come from actual deployed configuration. Current pilot infrastructure is configured for AWS `us-east-2`.

## Supabase

**Supabase Data Processing Addendum:**
- https://supabase.com/downloads/docs/Supabase%2BDPA%2B260601.pdf

Current DPA observed as version dated June 1, 2026. Production project region, enabled services, backup retention, and exact contractual posture must still be verified in the actual TPP Supabase project before publication.

## Accessibility

**Web Content Accessibility Guidelines (WCAG) 2.2 — W3C Recommendation:**
- https://www.w3.org/TR/WCAG22/

WCAG 2.2 is a W3C Recommendation. TPP's pre-release accessibility statement uses Level AA as an engineering target, not a certification claim.

## Repository implementation facts verified 2026-08-08

From current `main`:
- `backend/app/settings.py` defaults `TPP_DATA_BOUNDARY` to `teacher-and-curriculum-only`.
- `infra/pilot-stack.yml` describes isolated TPP controlled-pilot infrastructure in `us-east-2` and tags/sets the teacher-and-curriculum-only boundary.
- `infra/pilot-stack.yml` configures the AWS ECS application log group with `RetentionInDays: 30`.
- the runtime configuration includes Supabase and OpenAI settings, though exact production secret/configuration state must be verified in the deployed environment.

## Research discipline

Before changing a time-sensitive legal/vendor statement:
1. prefer primary official sources;
2. record the date verified;
3. distinguish provider marketing statements from binding contract terms;
4. distinguish statutory text from legal interpretation;
5. do not treat these notes as legal advice;
6. flag uncertain applicability for qualified counsel.
