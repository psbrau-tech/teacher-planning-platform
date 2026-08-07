-- Gate E AI usage evidence: GPT-5.6 exposes cached reads and cache-write tokens.
-- Record the OpenAI response identifier for operational traceability without storing prompts.

alter table public.ai_usage_events
  add column if not exists cache_write_tokens bigint not null default 0
    check (cache_write_tokens >= 0),
  add column if not exists provider_response_id text;

create index if not exists ai_usage_events_provider_response_idx
  on public.ai_usage_events (provider_response_id)
  where provider_response_id is not null;
