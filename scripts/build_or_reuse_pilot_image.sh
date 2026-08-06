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

tagged_image="$ECR_REGISTRY/$ECR_REPOSITORY:$GITHUB_SHA"
existing_digest="$(aws ecr describe-images \
  --repository-name "$ECR_REPOSITORY" \
  --image-ids imageTag="$GITHUB_SHA" \
  --query 'imageDetails[0].imageDigest' \
  --output text 2>/dev/null || true)"

reused=false
if [[ -n "$existing_digest" && "$existing_digest" != "None" ]]; then
  digest="$existing_digest"
  reused=true
  echo "Reusing immutable ECR image already associated with commit $GITHUB_SHA."
else
  docker build \
    --build-arg "VITE_SUPABASE_URL=$VITE_SUPABASE_URL" \
    --build-arg "VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY" \
    --label "org.opencontainers.image.revision=$GITHUB_SHA" \
    --label "org.opencontainers.image.source=$GITHUB_SERVER_URL/$GITHUB_REPOSITORY" \
    --tag "$tagged_image" \
    .
  docker push "$tagged_image"
  digest="$(aws ecr describe-images \
    --repository-name "$ECR_REPOSITORY" \
    --image-ids imageTag="$GITHUB_SHA" \
    --query 'imageDetails[0].imageDigest' \
    --output text)"
fi

if [[ ! "$digest" =~ ^sha256:[0-9a-f]{64}$ ]]; then
  echo "ECR did not return a valid immutable image digest for $GITHUB_SHA." >&2
  exit 1
fi

immutable_image="$ECR_REGISTRY/$ECR_REPOSITORY@$digest"
{
  echo "tagged_image=$tagged_image"
  echo "immutable_image=$immutable_image"
  echo "digest=$digest"
  echo "image_digest=$digest"
  echo "reused=$reused"
} >> "$GITHUB_OUTPUT"
