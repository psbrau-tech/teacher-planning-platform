# Final Pilot-Ready UI Corrections

This narrow correction set follows authenticated Gate E browser acceptance on candidate `76ddd65adfc551c314c2f7b65576ccc608c0e5e1`.

Accepted behavior already retained:
- XLSX pacing import and export;
- curriculum ownership and active-retirement protection;
- future pacing edit protection;
- shared-curriculum edit choices;
- Monday week identity;
- explicit no-class/postpone pacing behavior;
- PDF review separated from weekly-plan submission;
- Administration teacher-filter click-away collapse.

Final UI corrections:
1. Course Setup class cards use **Select class** / **Selected** rather than **Continue setup**, reflecting that class setup is generally completed once and the cards function as a reusable selector afterward.
2. Planning Assistance uses the primary action style for **Generate planning draft** / **Generate a new draft** so the teacher can immediately identify the action that advances the workflow.

No data model, database migration, standards source/materialization, AI-generation contract, authentication/authorization boundary, student-data capability, or legal data boundary changes are introduced.
