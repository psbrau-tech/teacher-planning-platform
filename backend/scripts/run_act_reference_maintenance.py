from __future__ import annotations

from app.act_benchmarks import fetch_and_parse_act_benchmarks, stage_act_benchmarks
from app.act_reference import (
    ACT_CCR_SOURCES,
    ActReferenceError,
    fetch_and_parse_act_ccr,
    service_role_client,
    stage_act_reference,
)
from app.settings import Settings


def main() -> int:
    settings = Settings()
    try:
        client = service_role_client(settings)
        print("TPP ACT reference maintenance — public first-party ACT sources only")
        print("database_boundary=professional_reference_data_only")
        for source_key, domain, url in ACT_CCR_SOURCES:
            parsed = fetch_and_parse_act_ccr(source_key, domain, url)
            snapshot_id = stage_act_reference(client, parsed)
            print(
                f"{source_key}|domain={domain}|entries={len(parsed.entries)}|"
                f"snapshot={snapshot_id}|status=pending_platform_admin_approval"
            )

        benchmarks = fetch_and_parse_act_benchmarks()
        benchmark_snapshot_id = stage_act_benchmarks(client, benchmarks)
        print(
            f"act_readiness_benchmarks|benchmarks={len(benchmarks.benchmarks)}|"
            f"snapshot={benchmark_snapshot_id}|status=pending_platform_admin_approval"
        )
    except ActReferenceError as error:
        print(f"ACT reference maintenance failed: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
