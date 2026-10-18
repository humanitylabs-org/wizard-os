#!/bin/bash
# Disposable-box test cleanup: remove leftover library folders of purged qa63-* test bundles.
C=$(docker ps -q --filter name=wisdom_wizardapps-wisdom)
for id in "$@"; do case "$id" in qa63-*) ;; *) exit 1;; esac
docker exec -u 1000:1000 "$C" sh -c 'L=${WISDOM_LIBRARY:-/media/Wisdom}; rm -rf "$L/$1" "$L/.editions/$1"; echo "cleared $1 under $L"; ls -a "$L"' _ "$id"; done
