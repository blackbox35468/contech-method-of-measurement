#!/usr/bin/env bash
set -euo pipefail

tag=${1:?Pass the CMM release tag}
assets=${2:?Pass the directory containing downloaded release assets}
if [[ ! "$tag" =~ ^cmm-v[0-9]+\.[0-9]+(\.[0-9]+)?$ ]]; then
  echo "Invalid CMM release tag: $tag" >&2
  exit 1
fi
edition=${tag#cmm-v}
if [[ "$edition" == "1.0" ]]; then
  package=release
else
  package="release-$edition"
fi
[[ -d "$package" && -d "$assets" ]] || { echo "Release package or assets missing" >&2; exit 1; }

(cd "$package" && sha256sum -c SHA256SUMS)
[[ $(jq -r .edition "$package/release-manifest.json") == "$edition" ]]
[[ $(jq -r .status "$package/release-manifest.json") == published ]]
canonical=$(sha256sum "$package/CMM-$edition.json")
[[ ${canonical%% *} == "$(jq -r .canonical_sha256 "$package/release-manifest.json")" ]]

for name in "CMM-$edition.json" "CMM-$edition.schema.json" release-manifest.json SHA256SUMS; do
  [[ -f "$assets/$name" ]] || { echo "Missing release asset: $name" >&2; exit 1; }
done
[[ $(find "$assets" -maxdepth 1 -type f | wc -l) -eq 4 ]] || { echo "Unexpected release asset" >&2; exit 1; }
cmp "$package/CMM-$edition.json" "$assets/CMM-$edition.json"
cmp "$package/schemas/CMM-$edition.schema.json" "$assets/CMM-$edition.schema.json"
cmp "$package/release-manifest.json" "$assets/release-manifest.json"
cmp "$package/SHA256SUMS" "$assets/SHA256SUMS"
echo "Verified checked-in package and uploaded assets for $tag"
