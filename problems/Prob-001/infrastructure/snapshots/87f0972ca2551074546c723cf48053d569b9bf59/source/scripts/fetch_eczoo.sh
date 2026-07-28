#!/usr/bin/env bash
# Vendor a snapshot of the Error Correction Zoo data (CC-BY-SA 4.0).
# Usage: scripts/fetch_eczoo.sh [REF]
# REF defaults to the pinned SHA below; pass a tag/branch/sha to override.
set -euo pipefail

REPO="https://github.com/errorcorrectionzoo/eczoo_data.git"
PINNED_REF="${1:-65193f6cd62fd3714c2f35c51369cf3cf561fa16}"   # pinned snapshot; pass a ref to override
DEST="zoo/external/eczoo"
RAW="$DEST/raw"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

# Shallow-fetch the exact ref. Works for branches, tags, AND commit SHAs
# (`git clone --branch <sha>` does not), so the pinned snapshot stays cheap.
echo "Fetching $REPO @ $PINNED_REF ..."
git init -q "$tmp/repo"
git -C "$tmp/repo" remote add origin "$REPO"
if git -C "$tmp/repo" fetch -q --depth 1 origin "$PINNED_REF"; then
  git -C "$tmp/repo" checkout -q FETCH_HEAD
else
  # Some servers reject fetching an arbitrary SHA; fall back to a full clone.
  rm -rf "$tmp/repo"
  git clone -q "$REPO" "$tmp/repo"
  git -C "$tmp/repo" checkout -q "$PINNED_REF"
fi
SHA="$(git -C "$tmp/repo" rev-parse HEAD)"

echo "Copying codes/ and LICENSE into $RAW ..."
rm -rf "$RAW"
mkdir -p "$RAW"
cp -R "$tmp/repo/codes" "$RAW/codes"
# Carry whatever license file upstream ships (name varies). Fail loudly if the
# license vanished upstream — never vendor the data without its license.
license_copied=0
for f in LICENSE LICENSE.md LICENSE.txt COPYING; do
  if [ -f "$tmp/repo/$f" ]; then
    cp "$tmp/repo/$f" "$DEST/LICENSE"
    license_copied=1
    break
  fi
done
if [ "$license_copied" -ne 1 ]; then
  echo "ERROR: no upstream license file found; refusing to vendor data without it." >&2
  exit 1
fi

cat > "$DEST/SNAPSHOT.md" <<EOF
# eczoo snapshot

- upstream: errorcorrectionzoo/eczoo_data
- commit: $SHA
- ref requested: $PINNED_REF
- fetched: $(date -u +%Y-%m-%d)
EOF

echo "Done. Snapshot SHA: $SHA"
echo "Files: $(find "$RAW/codes" -name '*.yml' | wc -l) yml"
