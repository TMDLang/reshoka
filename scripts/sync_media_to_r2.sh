#!/usr/bin/env bash

set -euo pipefail

: "${R2_ACCESS_KEY_ID:?Set R2_ACCESS_KEY_ID before uploading}"
: "${R2_SECRET_ACCESS_KEY:?Set R2_SECRET_ACCESS_KEY before uploading}"
: "${R2_ENDPOINT:?Set R2_ENDPOINT before uploading}"
: "${R2_BUCKET:?Set R2_BUCKET before uploading}"

MEDIA_ROOT="${MEDIA_ROOT:-docs}"
R2_PREFIX="${R2_PREFIX:-reshoka}"

export AWS_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID"
export AWS_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY"

aws s3 sync "$MEDIA_ROOT" "s3://${R2_BUCKET}/${R2_PREFIX}" \
  --endpoint-url "$R2_ENDPOINT" \
  --region auto \
  --no-progress \
  --exclude "*" \
  --include "*.jpg" \
  --include "*.jpeg" \
  --include "*.png" \
  --include "*.mp3" \
  --include "*.wav" \
  --include "*.mid" \
  --include "*.pdf" \
  --cache-control "public,max-age=31536000,immutable" \
  "$@"
