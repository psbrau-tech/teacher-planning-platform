# TPP Version 1 Architecture

## Technology stack
- Frontend: React + TypeScript.
- Backend: Python + FastAPI.
- Persistence and authentication: Supabase/PostgreSQL.
- Hosting target: AWS.
- Optional AI: OpenAI API through a metered service boundary.
- Document generation: Python PDF service using the Anniston HQI AcroForm template.

## Core design principle
The lesson plan is an output. The source of truth is structured curriculum, actual instructional progress, teacher-specific meeting schedules, and approved weekly adjustments.

## Domain layers

### Organization configuration
District, school, academic year, calendar, schedule definitions, standards libraries, lesson-plan templates, and known events.

### Teacher assignments
A teacher may have multiple assignments. Each assignment independently links a course, curriculum, standards framework, date range, and meeting pattern. One teacher may mix periods and blocks in the same day.

### Curriculum engine
Curriculum contains units and ordered lessons. Lessons carry estimated minutes, split/compression rules, standards, objectives, Know–Understand–Do content, activities, assessments, resources, and dependencies.

### Scheduling engine
The engine intersects:
- valid school dates;
- assignment meeting occurrences;
- available minutes;
- curriculum queue position;
- incomplete/carry-forward work;
- one-time exceptions;
- teacher overrides.

It returns proposed scheduled lesson segments. It never changes completed history.

### Weekly validation
Teachers record completed, modified, missed, or not-needed outcomes. Missed segments remain at the front of that assignment's queue unless the teacher skips, combines, or manually resequences them.

### Document generation
The document service receives a versioned weekly-plan snapshot and maps it to the 57 fields in the Anniston HQI PDF. Generated documents retain their source snapshot and generation status.

### Reporting
Administrator reporting aggregates adoption, configuration, weekly validation, generated plans, carry-forward activity, and failures. Cost reporting records AI usage by organization, school, teacher, assignment, feature, model, tokens, retries, and estimated cost.

## Security boundary
- No student data in Version 1.
- Teachers may access only their assignments and plans.
- School administrators may access aggregate school reporting and authorized teacher-plan status.
- Platform administrators may access system-wide operations and cost reporting.
- Core scheduling and PDF generation must function with AI disabled.

## Initial services
- `web`: React teacher/admin UI.
- `api`: FastAPI application and domain services.
- `db`: Supabase migrations and row-level-security policies.
- `pdf`: HQI template field mapping and rendering.
- `ai`: opt-in drafting and metering boundary.
