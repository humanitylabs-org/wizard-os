#!/bin/sh
# Pull each image (pinned by digest) with retries: Docker Hub and GHCR blob fetches from the VM fail transiently.
# Usage: pull.sh <ref@sha256:...> ...
status=0
for ref in "$@"; do
  ok=0
  for attempt in 1 2 3 4 5 6; do
    if docker pull -q "$ref" >/dev/null 2>&1; then ok=1; break; fi
    echo "pull $ref failed (attempt $attempt), retrying" >&2
    sleep $((attempt * 5))
  done
  if [ $ok = 1 ]; then echo "pulled $ref"; else echo "PULL FAILED $ref" >&2; status=1; fi
done
exit $status
