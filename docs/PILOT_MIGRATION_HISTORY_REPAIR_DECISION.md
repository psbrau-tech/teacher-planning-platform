# TPP Pilot Migration-History Repair Decision

The migration preview failed because four early schema migrations were applied under remote-generated timestamps while the repository retained their canonical timestamps.

The accepted decision boundary is:

- preserve all existing schema objects;
- do not run `db pull` to create a redundant remote-schema snapshot;
- do not mark genuinely pending migrations as applied;
- use Supabase CLI `migration repair` only for the four verified alias mappings;
- require a review-only GitHub Actions run before the apply run;
- require the explicit confirmation phrase `REPAIR_TPP_HISTORY` for mutation;
- require a post-repair `db push --dry-run` before any schema migration is authorized.

This repair is limited to migration-history metadata and does not alter teacher or curriculum records.
