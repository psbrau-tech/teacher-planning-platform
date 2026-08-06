#!/usr/bin/env bash
set -euo pipefail

required=(
  ECR_REGISTRY
  ECR_REPOSITORY
  VITE_SUPABASE_URL
  VITE_SUPABASE_ANON_KEY
  GITHUB_SHA
  GITHUB_OUTPUT
  GITHUB_SERVER_URL
  GITHUB_REPOSITORY
)
missing=()
for name in "${required[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    missing+=("$name")
  fi
done
if (( ${#missing[@]} > 0 )); then
  printf 'Missing image-build values: %s\n' "${missing[*]}" >&2
  exit 1
fi
if [[ ! "$GITHUB_SHA" =~ ^[0-9a-f]{40}$ ]]; then
  echo "GITHUB_SHA must be a full lowercase Git commit SHA." >&2
  exit 1
fi

build_config_digest="$(
  printf '%s\0%s' "$VITE_SUPABASE_URL" "$VITE_SUPABASE_ANON_KEY" \
    | sha256sum \
    | awk '{print $1}'
)"
build_config_fingerprint="${build_config_digest:0:12}"
image_tag="${GITHUB_SHA}-${build_config_fingerprint}"
tagged_image="$ECR_REGISTRY/$ECR_REPOSITORY:$image_tag"
existing_digest="$(aws ecr describe-images \
  --repository-name "$ECR_REPOSITORY" \
  --image-ids imageTag="$image_tag" \
  --query 'imageDetails[0].imageDigest' \
  --output text 2>/dev/null || true)"

reused=false
if [[ -n "$existing_digest" && "$existing_digest" != "None" ]]; then
  digest="$existing_digest"
  reused=true
  echo "Reusing immutable ECR image for the accepted commit and build configuration."
else
  docker build \
    --build-arg "VITE_SUPABASE_URL=$VITE_SUPABASE_URL" \
    --build-arg "VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY" \
    --label "org.opencontainers.image.revision=$GITHUB_SHA" \
    --label "org.opencontainers.image.source=$GITHUB_SERVER_URL/$GITHUB_REPOSITORY" \
    --label "ai.guidedscholar.tpp.build-config=$build_config_fingerprint" \
    --tag "$tagged_image" \
    .
  docker push "$tagged_image"
  digest="$(aws ecr describe-images \
    --repository-name "$ECR_REPOSITORY" \
    --image-ids imageTag="$image_tag" \
    --query 'imageDetails[0].imageDigest' \
    --output text)"
fi

if [[ ! "$digest" =~ ^sha256:[0-9a-f]{64}$ ]]; then
  echo "ECR did not return a valid immutable image digest." >&2
  exit 1
fi

immutable_image="$ECR_REGISTRY/$ECR_REPOSITORY@$digest"
{
  echo "image_tag=$image_tag"
  echo "build_config_fingerprint=$build_config_fingerprint"
  echo "tagged_image=$tagged_image"
  echo "immutable_image=$immutable_image"
  echo "digest=$digest"
  echo "image_digest=$digest"
  echo "reused=$reused"
} >> "$GITHUB_OUTPUT"
