#!/usr/bin/env bash
set -euo pipefail

ACCOUNT_ID="697091778129"
REGION="us-east-2"
OIDC_ROLE_NAME="TeacherPlanningPlatformPilotGitHubOidc"
EXECUTION_ROLE_NAME="TeacherPlanningPlatformPilotCloudFormationExecution"
OIDC_POLICY_NAME="TeacherPlanningPlatformPilotDeployment"
EXECUTION_POLICY_NAME="TeacherPlanningPlatformPilotInfrastructure"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TRUST_POLICY="$ROOT_DIR/infra/iam/tpp-cloudformation-execution-trust.json"
EXECUTION_POLICY="$ROOT_DIR/infra/iam/tpp-cloudformation-execution-policy.json"
OIDC_POLICY="$ROOT_DIR/infra/iam/tpp-github-oidc-deployment-policy.json"

apply=false
case "${1:-}" in
  "") ;;
  --apply) apply=true ;;
  -h|--help)
    cat <<'EOF'
Usage: scripts/configure_pilot_deployment_roles.sh [--apply]

Without --apply, validates the AWS account, Region, policy JSON, and current role state without mutation.
With --apply, creates or updates the dedicated CloudFormation execution role and adds the bounded deployment policy to the existing GitHub OIDC role.
EOF
    exit 0
    ;;
  *)
    echo "Unsupported argument: ${1}" >&2
    exit 2
    ;;
esac

validate_json_file() {
  local path="$1"

  if command -v python3 >/dev/null 2>&1 \
    && python3 -c 'import json, sys; json.load(open(sys.argv[1], encoding="utf-8"))' "$path" >/dev/null 2>&1; then
    return 0
  fi

  if command -v python >/dev/null 2>&1 \
    && python -c 'import json, sys; json.load(open(sys.argv[1], encoding="utf-8"))' "$path" >/dev/null 2>&1; then
    return 0
  fi

  if command -v node >/dev/null 2>&1; then
    node -e 'JSON.parse(require("fs").readFileSync(process.argv[1], "utf8"))' "$path" >/dev/null
    return 0
  fi

  if command -v powershell.exe >/dev/null 2>&1; then
    local powershell_path="$path"
    if command -v cygpath >/dev/null 2>&1; then
      powershell_path="$(cygpath -w "$path")"
    fi
    powershell.exe -NoProfile -NonInteractive -Command \
      '$ErrorActionPreference="Stop"; Get-Content -Raw -LiteralPath $args[0] | ConvertFrom-Json | Out-Null' \
      "$powershell_path" >/dev/null
    return 0
  fi

  echo "Unable to validate JSON because no supported JSON parser is available." >&2
  echo "Install Python, Node.js, or run from Windows PowerShell/Git Bash where powershell.exe is available." >&2
  return 1
}

for path in "$TRUST_POLICY" "$EXECUTION_POLICY" "$OIDC_POLICY"; do
  if [[ ! -f "$path" ]]; then
    echo "Required policy file is missing: $path" >&2
    exit 1
  fi
  if ! validate_json_file "$path"; then
    echo "Invalid policy JSON: $path" >&2
    exit 1
  fi
done

# Pass validated JSON as literal CLI argument values rather than file:// paths.
# This keeps the same script portable across Linux and Windows Git Bash, where
# the native Windows AWS CLI cannot resolve MSYS-style paths such as /c/Users/....
trust_policy_json="$(cat "$TRUST_POLICY")"
execution_policy_json="$(cat "$EXECUTION_POLICY")"
oidc_policy_json="$(cat "$OIDC_POLICY")"

caller_account="$(aws sts get-caller-identity --query Account --output text)"
if [[ "$caller_account" != "$ACCOUNT_ID" ]]; then
  echo "Refusing to configure TPP pilot roles in AWS account $caller_account; expected $ACCOUNT_ID." >&2
  exit 1
fi

configured_region="${AWS_REGION:-${AWS_DEFAULT_REGION:-$REGION}}"
if [[ "$configured_region" != "$REGION" ]]; then
  echo "Refusing to configure TPP pilot roles outside $REGION; current Region is $configured_region." >&2
  exit 1
fi

if ! aws iam get-role --role-name "$OIDC_ROLE_NAME" >/dev/null 2>&1; then
  echo "Required GitHub OIDC role does not exist: $OIDC_ROLE_NAME" >&2
  exit 1
fi

execution_role_exists=false
if aws iam get-role --role-name "$EXECUTION_ROLE_NAME" >/dev/null 2>&1; then
  execution_role_exists=true
fi

if [[ "$apply" != "true" ]]; then
  echo "TPP pilot deployment-role review"
  echo "AWS account: $caller_account"
  echo "Region: $configured_region"
  echo "GitHub OIDC role: present"
  echo "CloudFormation execution role present: $execution_role_exists"
  echo "Mutation status: none"
  echo "Run again with --apply only after reviewing infra/iam and docs/PILOT_IAM_BOOTSTRAP.md."
  exit 0
fi

if [[ "$execution_role_exists" == "true" ]]; then
  aws iam update-assume-role-policy \
    --role-name "$EXECUTION_ROLE_NAME" \
    --policy-document "$trust_policy_json"
else
  aws iam create-role \
    --role-name "$EXECUTION_ROLE_NAME" \
    --description "Least-privilege CloudFormation execution role for the TPP controlled pilot" \
    --assume-role-policy-document "$trust_policy_json" \
    --max-session-duration 3600 >/dev/null
fi

aws iam put-role-policy \
  --role-name "$EXECUTION_ROLE_NAME" \
  --policy-name "$EXECUTION_POLICY_NAME" \
  --policy-document "$execution_policy_json"

aws iam put-role-policy \
  --role-name "$OIDC_ROLE_NAME" \
  --policy-name "$OIDC_POLICY_NAME" \
  --policy-document "$oidc_policy_json"

execution_role_arn="$(aws iam get-role \
  --role-name "$EXECUTION_ROLE_NAME" \
  --query 'Role.Arn' \
  --output text)"

aws iam get-role-policy \
  --role-name "$EXECUTION_ROLE_NAME" \
  --policy-name "$EXECUTION_POLICY_NAME" >/dev/null
aws iam get-role-policy \
  --role-name "$OIDC_ROLE_NAME" \
  --policy-name "$OIDC_POLICY_NAME" >/dev/null

cat <<EOF
TPP pilot deployment roles configured.
CloudFormation execution role: $execution_role_arn
GitHub environment variable required:
  TPP_CLOUDFORMATION_ROLE_ARN=$execution_role_arn
No trust-policy change was made to $OIDC_ROLE_NAME.
EOF
