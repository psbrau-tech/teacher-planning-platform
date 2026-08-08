#!/usr/bin/env bash
set -euo pipefail

required=(
  AWS_REGION
  STACK_NAME
  ECR_REPOSITORY
  ECS_CLUSTER
  ECS_SERVICE
  TASK_DEFINITION_FAMILY
  PILOT_HOSTNAME
  GITHUB_SHA
  GITHUB_STEP_SUMMARY
  REASON
)
missing=()
for name in "${required[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    missing+=("$name")
  fi
done
if (( ${#missing[@]} > 0 )); then
  printf 'Missing deployment-verification values: %s\n' "${missing[*]}" >&2
  exit 1
fi
if [[ "$AWS_REGION" != "us-east-2" ]]; then
  echo "TPP pilot verification is locked to us-east-2." >&2
  exit 1
fi
if [[ -n "${EXPECTED_COMMIT:-}" && ! "$EXPECTED_COMMIT" =~ ^[0-9a-f]{40}$ ]]; then
  echo "EXPECTED_COMMIT must be a full 40-character lowercase Git SHA." >&2
  exit 1
fi
if [[ "${VERIFY_PUBLIC_HOSTNAME:-false}" != "true" \
  && "${VERIFY_PUBLIC_HOSTNAME:-false}" != "false" ]]; then
  echo "VERIFY_PUBLIC_HOSTNAME must be true or false." >&2
  exit 1
fi

stack_json="$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --output json)"
stack_status="$(jq -r '.Stacks[0].StackStatus' <<<"$stack_json")"
case "$stack_status" in
  CREATE_COMPLETE|UPDATE_COMPLETE) ;;
  *)
    echo "Pilot stack is not in an accepted stable state: $stack_status" >&2
    exit 1
    ;;
esac

output_value() {
  jq -r --arg key "$1" '
    .Stacks[0].Outputs[]
    | select(.OutputKey == $key)
    | .OutputValue
  ' <<<"$stack_json"
}

alb_dns="$(output_value LoadBalancerDnsName)"
target_group_arn="$(output_value TargetGroupArn)"
stack_cluster="$(output_value EcsClusterName)"
stack_service="$(output_value EcsServiceName)"
stack_task_definition="$(output_value TaskDefinitionArn)"
data_boundary="$(output_value DataBoundary)"

for value in \
  "$alb_dns" \
  "$target_group_arn" \
  "$stack_cluster" \
  "$stack_service" \
  "$stack_task_definition"; do
  if [[ -z "$value" || "$value" == "None" || "$value" == "not-deployed" ]]; then
    echo "A required deployed CloudFormation output is absent." >&2
    exit 1
  fi
done
if [[ "$stack_cluster" != "$ECS_CLUSTER" || "$stack_service" != "$ECS_SERVICE" ]]; then
  echo "CloudFormation ECS outputs do not match the governed environment configuration." >&2
  exit 1
fi
if [[ "$data_boundary" != "teacher-and-curriculum-only" ]]; then
  echo "Unexpected deployment data boundary: $data_boundary" >&2
  exit 1
fi

service_json="$(aws ecs describe-services \
  --cluster "$ECS_CLUSTER" \
  --services "$ECS_SERVICE" \
  --output json)"
if [[ "$(jq '.failures | length' <<<"$service_json")" != "0" ]]; then
  jq '.failures' <<<"$service_json" >&2
  exit 1
fi

desired="$(jq -r '.services[0].desiredCount' <<<"$service_json")"
running="$(jq -r '.services[0].runningCount' <<<"$service_json")"
pending="$(jq -r '.services[0].pendingCount' <<<"$service_json")"
rollout_state="$(jq -r '
  .services[0].deployments[]
  | select(.status == "PRIMARY")
  | .rolloutState
' <<<"$service_json")"
task_definition="$(jq -r '.services[0].taskDefinition' <<<"$service_json")"

if [[ "$desired" -lt 1 || "$running" != "$desired" || "$pending" != "0" ]]; then
  echo "ECS counts are not stable: desired=$desired running=$running pending=$pending" >&2
  exit 1
fi
if [[ "$rollout_state" != "COMPLETED" ]]; then
  echo "Primary ECS deployment is not complete: $rollout_state" >&2
  exit 1
fi
if [[ "$task_definition" != "$stack_task_definition" ]]; then
  echo "ECS service task definition does not match the CloudFormation output." >&2
  exit 1
fi

task_json="$(aws ecs describe-task-definition \
  --task-definition "$task_definition" \
  --output json)"
image="$(jq -r '.taskDefinition.containerDefinitions[0].image' <<<"$task_json")"
if [[ ! "$image" =~ @sha256:[0-9a-f]{64}$ ]]; then
  echo "The deployed image is not pinned to an immutable sha256 digest: $image" >&2
  exit 1
fi

boundary="$(jq -r '
  .taskDefinition.containerDefinitions[0].environment[]
  | select(.name == "TPP_DATA_BOUNDARY")
  | .value
' <<<"$task_json")"
if [[ "$boundary" != "teacher-and-curriculum-only" ]]; then
  echo "Task definition has an unexpected data boundary: $boundary" >&2
  exit 1
fi

runtime_secret_names='TPP_SUPABASE_URL|TPP_SUPABASE_ANON_KEY|TPP_SUPABASE_SERVICE_ROLE_KEY|TPP_DATABASE_URL|TPP_OPENAI_API_KEY|TPP_GOOGLE_OAUTH_CLIENT_ID|TPP_GOOGLE_OAUTH_CLIENT_SECRET'
plaintext_runtime_secrets="$(
  jq -r '.taskDefinition.containerDefinitions[0].environment[].name' <<<"$task_json" \
    | grep -E "$runtime_secret_names" \
    || true
)"
if [[ -n "$plaintext_runtime_secrets" ]]; then
  echo "A runtime credential is present in plaintext task-definition environment values:" >&2
  echo "$plaintext_runtime_secrets" >&2
  exit 1
fi

secret_names="$(
  jq -r '.taskDefinition.containerDefinitions[0].secrets[].name' <<<"$task_json" \
    | sort
)"
legacy_secret_names=$'TPP_SUPABASE_ANON_KEY\nTPP_SUPABASE_URL'
gate_e_secret_names=$'TPP_OPENAI_API_KEY\nTPP_SUPABASE_ANON_KEY\nTPP_SUPABASE_URL'
runtime_secret_profile=""
if [[ "$secret_names" == "$legacy_secret_names" ]]; then
  runtime_secret_profile="legacy-pre-gate-e"
elif [[ "$secret_names" == "$gate_e_secret_names" ]]; then
  runtime_secret_profile="gate-e"
else
  echo "The pilot task does not use an approved runtime secret set:" >&2
  echo "$secret_names" >&2
  exit 1
fi

# Pre-deployment baseline checks may legitimately observe the legacy two-secret runtime.
# Once an exact expected Gate E commit is supplied, require the Gate E OpenAI runtime secret.
if [[ -n "${EXPECTED_COMMIT:-}" && "$runtime_secret_profile" != "gate-e" ]]; then
  echo "Exact Gate E commit verification requires the Gate E runtime secret profile." >&2
  echo "Observed profile: $runtime_secret_profile" >&2
  exit 1
fi

for prohibited_secret in \
  TPP_DATABASE_URL \
  TPP_GOOGLE_OAUTH_CLIENT_ID \
  TPP_GOOGLE_OAUTH_CLIENT_SECRET \
  TPP_SUPABASE_SERVICE_ROLE_KEY; do
  if grep -qx "$prohibited_secret" <<<"$secret_names"; then
    echo "A prohibited high-privilege credential is injected into the ECS task: $prohibited_secret" >&2
    exit 1
  fi
done

digest="${image##*@}"
image_details="$(aws ecr describe-images \
  --repository-name "$ECR_REPOSITORY" \
  --image-ids imageDigest="$digest" \
  --output json)"
if [[ "$(jq '.imageDetails | length' <<<"$image_details")" != "1" ]]; then
  echo "The deployed digest is not present exactly once in the governed ECR repository." >&2
  exit 1
fi

image_tags="$(jq -r '.imageDetails[0].imageTags // [] | join(",")' <<<"$image_details")"
if [[ -n "${EXPECTED_COMMIT:-}" ]]; then
  if ! jq -e --arg commit "$EXPECTED_COMMIT" '
    (.imageDetails[0].imageTags // [])
    | any(. == $commit or startswith($commit + "-"))
  ' <<<"$image_details" >/dev/null; then
    echo "The deployed digest has no tag for expected commit $EXPECTED_COMMIT." >&2
    exit 1
  fi
fi

target_health="$(aws elbv2 describe-target-health \
  --target-group-arn "$target_group_arn" \
  --output json)"
target_count="$(jq '.TargetHealthDescriptions | length' <<<"$target_health")"
unhealthy_count="$(jq '
  [.TargetHealthDescriptions[] | select(.TargetHealth.State != "healthy")]
  | length
' <<<"$target_health")"
if [[ "$target_count" -lt 1 || "$unhealthy_count" != "0" ]]; then
  jq '.TargetHealthDescriptions' <<<"$target_health" >&2
  exit 1
fi

log_group="/aws/ecs/$TASK_DEFINITION_FAMILY"
retention="$(aws logs describe-log-groups \
  --log-group-name-prefix "$log_group" \
  --query "logGroups[?logGroupName=='$log_group'].retentionInDays | [0]" \
  --output text)"
if [[ "$retention" != "30" ]]; then
  echo "Expected a 30-day application log-group retention; found $retention." >&2
  exit 1
fi

# describe-log-streams is paginated. Avoid a scalar JMESPath query with --output text,
# which AWS CLI pagination can evaluate against a page where the list is null.
log_streams_json="$(aws logs describe-log-streams \
  --log-group-name "$log_group" \
  --order-by LastEventTime \
  --descending \
  --max-items 5 \
  --output json)"
stream_count="$(jq '(.logStreams // []) | length' <<<"$log_streams_json")"
if [[ "$stream_count" -lt 1 ]]; then
  echo "No application log stream exists in $log_group." >&2
  exit 1
fi

certificate_status="not-configured"
if [[ -n "${CERTIFICATE_ARN:-}" ]]; then
  certificate_json="$(aws acm describe-certificate \
    --certificate-arn "$CERTIFICATE_ARN" \
    --output json)"
  certificate_domain="$(jq -r '.Certificate.DomainName' <<<"$certificate_json")"
  certificate_status="$(jq -r '.Certificate.Status' <<<"$certificate_json")"
  if [[ "$certificate_domain" != "$PILOT_HOSTNAME" ]]; then
    echo "Configured certificate does not cover $PILOT_HOSTNAME." >&2
    exit 1
  fi
  case "$certificate_status" in
    ISSUED|PENDING_VALIDATION) ;;
    *)
      echo "Certificate is not in an accepted state: $certificate_status" >&2
      exit 1
      ;;
  esac
fi

if [[ "${VERIFY_PUBLIC_HOSTNAME:-false}" == "true" ]]; then
  if [[ -z "${CERTIFICATE_ARN:-}" ]]; then
    echo "CERTIFICATE_ARN is required for public HTTPS verification." >&2
    exit 1
  fi
  if [[ "$certificate_status" != "ISSUED" ]]; then
    echo "The certificate must be ISSUED before public HTTPS verification." >&2
    exit 1
  fi
  resolved="$(getent ahostsv4 "$PILOT_HOSTNAME" | awk 'NR==1 {print $1}')"
  if [[ -z "$resolved" ]]; then
    echo "$PILOT_HOSTNAME does not currently resolve." >&2
    exit 1
  fi
  curl --fail --silent --show-error \
    --max-time 20 \
    "https://$PILOT_HOSTNAME/health" >/dev/null
fi

{
  echo "## TPP pilot deployment verification"
  echo "- Reason: $REASON"
  echo "- Verification commit: \`$GITHUB_SHA\`"
  echo "- Expected deployed commit: \`${EXPECTED_COMMIT:-not-specified}\`"
  echo "- Stack status: \`$stack_status\`"
  echo "- ECS desired/running: \`$desired/$running\`"
  echo "- Healthy targets: \`$target_count\`"
  echo "- Immutable image: \`$image\`"
  echo "- Image tags: \`$image_tags\`"
  echo "- Task definition: \`$task_definition\`"
  echo "- Runtime secret profile: \`$runtime_secret_profile\`"
  echo "- Supabase service-role/database/OAuth runtime credentials: \`absent\`"
  echo "- Log group: \`$log_group\` with 30-day retention"
  echo "- Application log streams observed: \`$stream_count\`"
  echo "- Certificate status: \`$certificate_status\`"
  echo "- Public HTTPS checked: \`${VERIFY_PUBLIC_HOSTNAME:-false}\`"
  echo "- Data boundary: \`teacher-and-curriculum-only\`"
  echo "- Result: read-only verification passed; no AWS resource was changed"
} >> "$GITHUB_STEP_SUMMARY"
