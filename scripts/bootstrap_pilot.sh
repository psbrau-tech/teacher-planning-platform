#!/usr/bin/env bash
set -euo pipefail

required=(
  AWS_REGION
  CLOUDFORMATION_ROLE_ARN
  STACK_NAME
  ECR_REPOSITORY
  ECS_CLUSTER
  ECS_SERVICE
  TASK_DEFINITION_FAMILY
  VITE_SUPABASE_URL
  VITE_SUPABASE_ANON_KEY
  SUPABASE_URL_SECRET_ID
  SUPABASE_ANON_KEY_SECRET_ID
  GITHUB_SHA
  GITHUB_OUTPUT
  GITHUB_STEP_SUMMARY
  REASON
  REQUEST_CERTIFICATE
)
missing=()
for name in "${required[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    missing+=("$name")
  fi
done
if (( ${#missing[@]} > 0 )); then
  printf 'Missing required TPP pilot bootstrap values: %s\n' "${missing[*]}" >&2
  exit 1
fi
if [[ "$AWS_REGION" != "us-east-2" ]]; then
  echo "TPP pilot infrastructure is locked to us-east-2." >&2
  exit 1
fi
if [[ ! "$CLOUDFORMATION_ROLE_ARN" =~ ^arn:aws:iam::697091778129:role/TeacherPlanningPlatformPilotCloudFormationExecution$ ]]; then
  echo "Unexpected TPP CloudFormation execution-role ARN." >&2
  exit 1
fi
if [[ "$REQUEST_CERTIFICATE" != "true" && "$REQUEST_CERTIFICATE" != "false" ]]; then
  echo "REQUEST_CERTIFICATE must be true or false." >&2
  exit 1
fi

aws cloudformation validate-template --template-body file://infra/pilot-stack.yml >/dev/null
aws iam get-role --role-name "${CLOUDFORMATION_ROLE_ARN##*/}" >/dev/null

resolve_secret_arn() {
  local secret_id="$1"
  local arn
  arn="$(aws secretsmanager describe-secret \
    --secret-id "$secret_id" \
    --query ARN \
    --output text)"
  if [[ -z "$arn" || "$arn" == "None" ]]; then
    echo "Unable to resolve runtime secret: $secret_id" >&2
    exit 1
  fi
  printf '%s' "$arn"
}

supabase_url_secret_arn="$(resolve_secret_arn "$SUPABASE_URL_SECRET_ID")"
supabase_anon_key_secret_arn="$(resolve_secret_arn "$SUPABASE_ANON_KEY_SECRET_ID")"

stack_exists=false
service_deployed=false
existing_stack_status="not-created"
existing_task_definition=""
current_image=""

if stack_json="$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --output json 2>/dev/null)"; then
  stack_exists=true
  existing_stack_status="$(jq -r '.Stacks[0].StackStatus' <<<"$stack_json")"
  case "$existing_stack_status" in
    CREATE_COMPLETE|UPDATE_COMPLETE) ;;
    *)
      echo "Existing pilot stack is not stable: $existing_stack_status" >&2
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

  configured_repository="$(output_value EcrRepositoryName)"
  if [[ -n "$configured_repository" && "$configured_repository" != "$ECR_REPOSITORY" ]]; then
    echo "Existing stack ECR repository does not match the protected configuration." >&2
    exit 1
  fi

  existing_task_definition="$(output_value TaskDefinitionArn)"
  if [[ -n "$existing_task_definition" && "$existing_task_definition" != "not-deployed" ]]; then
    service_deployed=true
    current_image="$(aws ecs describe-task-definition \
      --task-definition "$existing_task_definition" \
      --query 'taskDefinition.containerDefinitions[0].image' \
      --output text)"
  fi
fi

if [[ "$service_deployed" != "true" ]]; then
  aws cloudformation deploy \
    --stack-name "$STACK_NAME" \
    --template-file infra/pilot-stack.yml \
    --role-arn "$CLOUDFORMATION_ROLE_ARN" \
    --capabilities CAPABILITY_NAMED_IAM \
    --no-fail-on-empty-changeset \
    --parameter-overrides \
      EcrRepositoryName="$ECR_REPOSITORY" \
      EcsClusterName="$ECS_CLUSTER" \
      EcsServiceName="$ECS_SERVICE" \
      TaskDefinitionFamily="$TASK_DEFINITION_FAMILY" \
      DeployService=false \
      CertificateArn="${CERTIFICATE_ARN:-}" \
      SupabaseUrlSecretArn="$supabase_url_secret_arn" \
      SupabaseAnonKeySecretArn="$supabase_anon_key_secret_arn"
fi

account_id="$(aws sts get-caller-identity --query Account --output text)"
ecr_registry="$account_id.dkr.ecr.$AWS_REGION.amazonaws.com"
aws ecr get-login-password | docker login --username AWS --password-stdin "$ecr_registry" >/dev/null

image_output="$(mktemp)"
trap 'rm -f "$image_output"' EXIT
GITHUB_OUTPUT="$image_output" \
ECR_REGISTRY="$ecr_registry" \
  bash scripts/build_or_reuse_pilot_image.sh

image_value() {
  local key="$1"
  awk -F= -v key="$key" '$1 == key {sub($1 "=", ""); value=$0} END {print value}' "$image_output"
}
immutable_image="$(image_value immutable_image)"
image_reused="$(image_value reused)"
build_config_fingerprint="$(image_value build_config_fingerprint)"
if [[ -z "$immutable_image" || ! "$immutable_image" =~ @sha256:[0-9a-f]{64}$ ]]; then
  echo "The bootstrap image builder did not return an immutable image." >&2
  exit 1
fi
cat "$image_output" >> "$GITHUB_OUTPUT"

if [[ "$service_deployed" == "true" && "$current_image" != "$immutable_image" ]]; then
  echo "Bootstrap cannot replace an existing service with a different commit or build configuration." >&2
  echo "Use Deploy TPP Pilot for an approved application update." >&2
  exit 1
fi

if [[ "$service_deployed" != "true" ]]; then
  aws cloudformation deploy \
    --stack-name "$STACK_NAME" \
    --template-file infra/pilot-stack.yml \
    --role-arn "$CLOUDFORMATION_ROLE_ARN" \
    --capabilities CAPABILITY_NAMED_IAM \
    --no-fail-on-empty-changeset \
    --parameter-overrides \
      EcrRepositoryName="$ECR_REPOSITORY" \
      EcsClusterName="$ECS_CLUSTER" \
      EcsServiceName="$ECS_SERVICE" \
      TaskDefinitionFamily="$TASK_DEFINITION_FAMILY" \
      ImageUri="$immutable_image" \
      DeployService=true \
      CertificateArn="${CERTIFICATE_ARN:-}" \
      PublicBaseUrl=https://planner.guidedscholar.ai \
      AllowedEmailDomains=anniston.k12.al.us \
      SupabaseUrlSecretArn="$supabase_url_secret_arn" \
      SupabaseAnonKeySecretArn="$supabase_anon_key_secret_arn"
fi

aws ecs wait services-stable --cluster "$ECS_CLUSTER" --services "$ECS_SERVICE"
stack_json="$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --output json)"
output_value() {
  jq -r --arg key "$1" '
    .Stacks[0].Outputs[]
    | select(.OutputKey == $key)
    | .OutputValue
  ' <<<"$stack_json"
}
alb_dns="$(output_value LoadBalancerDnsName)"
target_group_arn="$(output_value TargetGroupArn)"

for attempt in {1..30}; do
  target_health="$(aws elbv2 describe-target-health \
    --target-group-arn "$target_group_arn" \
    --output json)"
  target_count="$(jq '.TargetHealthDescriptions | length' <<<"$target_health")"
  unhealthy_count="$(jq '[.TargetHealthDescriptions[] | select(.TargetHealth.State != "healthy")] | length' <<<"$target_health")"
  if [[ "$target_count" -ge 1 && "$unhealthy_count" == "0" ]]; then
    break
  fi
  if [[ "$attempt" == "30" ]]; then
    jq '.TargetHealthDescriptions' <<<"$target_health" >&2
    exit 1
  fi
  sleep 10
done

if [[ -z "${CERTIFICATE_ARN:-}" ]]; then
  curl --fail --silent "http://$alb_dns/health" >/dev/null
fi

task_definition="$(aws ecs describe-services \
  --cluster "$ECS_CLUSTER" \
  --services "$ECS_SERVICE" \
  --query 'services[0].taskDefinition' \
  --output text)"
deployed_image="$(aws ecs describe-task-definition \
  --task-definition "$task_definition" \
  --query 'taskDefinition.containerDefinitions[0].image' \
  --output text)"
if [[ "$deployed_image" != "$immutable_image" ]]; then
  echo "Initial service image does not match the accepted exact digest." >&2
  exit 1
fi

echo "alb_dns=$alb_dns" >> "$GITHUB_OUTPUT"
echo "task_definition=$task_definition" >> "$GITHUB_OUTPUT"

certificate_arn=""
validation_name=""
validation_value=""
if [[ "$REQUEST_CERTIFICATE" == "true" ]]; then
  certificate_arn="${CERTIFICATE_ARN:-}"
  if [[ -z "$certificate_arn" ]]; then
    certificate_arn="$(aws acm list-certificates \
      --certificate-statuses ISSUED PENDING_VALIDATION \
      --query "CertificateSummaryList[?DomainName=='planner.guidedscholar.ai'].CertificateArn | [0]" \
      --output text)"
  fi
  if [[ -z "$certificate_arn" || "$certificate_arn" == "None" ]]; then
    certificate_arn="$(aws acm request-certificate \
      --domain-name planner.guidedscholar.ai \
      --validation-method DNS \
      --idempotency-token tpppilot \
      --options CertificateTransparencyLoggingPreference=ENABLED \
      --query CertificateArn \
      --output text)"
  fi

  for attempt in {1..20}; do
    validation_name="$(aws acm describe-certificate \
      --certificate-arn "$certificate_arn" \
      --query 'Certificate.DomainValidationOptions[0].ResourceRecord.Name' \
      --output text)"
    validation_value="$(aws acm describe-certificate \
      --certificate-arn "$certificate_arn" \
      --query 'Certificate.DomainValidationOptions[0].ResourceRecord.Value' \
      --output text)"
    if [[ -n "$validation_name" && "$validation_name" != "None" \
      && -n "$validation_value" && "$validation_value" != "None" ]]; then
      break
    fi
    sleep 3
  done
  if [[ -z "$validation_name" || "$validation_name" == "None" ]]; then
    echo "ACM did not return its DNS validation record." >&2
    exit 1
  fi

  echo "certificate_arn=$certificate_arn" >> "$GITHUB_OUTPUT"
  echo "validation_name=$validation_name" >> "$GITHUB_OUTPUT"
  echo "validation_value=$validation_value" >> "$GITHUB_OUTPUT"
fi

{
  echo "## TPP pilot bootstrap"
  echo "- Reason: $REASON"
  echo "- Commit: \`$GITHUB_SHA\`"
  echo "- Build configuration fingerprint: \`$build_config_fingerprint\`"
  echo "- Region: \`$AWS_REGION\`"
  echo "- Stack: \`$STACK_NAME\`"
  echo "- CloudFormation execution role: \`$CLOUDFORMATION_ROLE_ARN\`"
  echo "- Existing deployed service: \`$service_deployed\`"
  echo "- Existing immutable image reused: \`$image_reused\`"
  echo "- ALB DNS: \`$alb_dns\`"
  echo "- Image: \`$immutable_image\`"
  echo "- Task definition: \`$task_definition\`"
  echo "- Runtime secret mappings: \`TPP_SUPABASE_URL, TPP_SUPABASE_ANON_KEY\`"
  echo "- High-privilege runtime credentials: \`not injected\`"
  echo "- Data boundary: teacher and curriculum data only; no student data"
  if [[ "$REQUEST_CERTIFICATE" == "true" ]]; then
    echo "- ACM certificate: \`$certificate_arn\`"
    echo "- Required Cloudflare ACM validation CNAME name: \`$validation_name\`"
    echo "- Required Cloudflare ACM validation CNAME value: \`$validation_value\`"
    echo "- Do not add the planner application CNAME until ACM is issued and HTTPS is attached."
  fi
} >> "$GITHUB_STEP_SUMMARY"
