#!/usr/bin/env sh
set -eu

if [ -z "${TEAMS_APP_ID:-}" ] || [ -z "${APP_HOSTNAME:-}" ]; then
  echo "TEAMS_APP_ID and APP_HOSTNAME are required" >&2
  exit 2
fi

case "$TEAMS_APP_ID" in
  ????????-????-????-????-????????????) ;;
  *) echo "TEAMS_APP_ID must use UUID format" >&2; exit 2 ;;
esac

case "$APP_HOSTNAME" in
  *://*|*/*|*' '*) echo "APP_HOSTNAME must be a hostname without scheme or path" >&2; exit 2 ;;
esac

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
source_dir="$repo_root/apps/teams-app"
output_dir="$repo_root/dist"
stage_dir=$(mktemp -d)
trap 'rm -rf "$stage_dir"' EXIT

sed \
  -e "s/__TEAMS_APP_ID__/$TEAMS_APP_ID/g" \
  -e "s/__APP_HOSTNAME__/$APP_HOSTNAME/g" \
  "$source_dir/manifest/manifest.template.json" > "$stage_dir/manifest.json"
cp "$source_dir/assets/color.png" "$stage_dir/color.png"
cp "$source_dir/assets/outline.png" "$stage_dir/outline.png"

mkdir -p "$output_dir"
(cd "$stage_dir" && zip -q "$output_dir/project-assistant-teams.zip" manifest.json color.png outline.png)
echo "$output_dir/project-assistant-teams.zip"
