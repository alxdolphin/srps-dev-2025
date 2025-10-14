#!/usr/bin/env bash
set -euo pipefail

API_TOKEN="${COURSEMAP_API_TOKEN:?COURSEMAP_API_TOKEN not set}"
BASE_URL="${COURSEMAP_API_URL:?COURSEMAP_API_URL not set}"

OUT_FORMAT="${1:-ids}"  # json|csv|ids
OUTFILE="run_leads_ids_names.txt"

# Accept optional second argument: active param (default: empty, i.e., all)
ACTIVE_FILTER="${2:-}"

call_get_leaders_all() {
  local url="$BASE_URL/users/get-leaders"
  local params="api_token=$API_TOKEN&page=all"
  # Only append active param if provided (can be "1", "0", "true", "false" etc)
  if [ -n "$ACTIVE_FILTER" ]; then
    params="$params&active=$ACTIVE_FILTER"
  fi
  # do NOT add team_id, so pulls all teams
  curl -s "$url?$params" -H "Accept: application/json"
}

# Output each user record to stdout as soon as it's pulled and processed
response="$(call_get_leaders_all)"

# basic diagnostic if no users found in common response shapes
users_count="$(printf '%s' "$response" | jq -r '((.data.users // .users // .data.data // .data // []) | length)')"
if [ "$users_count" -eq 0 ]; then
  echo "no users found; response did not include a users array" >&2
  # try to surface any server-provided message
  printf '%s' "$response" | jq -r '.message? // .error? // .errors? // empty' 1>&2 || true
fi

# Clear the output file before writing
: > "$OUTFILE"

printf '%s\n' "$response" | jq -c '
  ( .data.users // .users // .data.data // .data // [] ) as $users |
  if ($users | type) == "array" then $users else [] end |
  .[]
' | while IFS= read -r user; do
  id=$(echo "$user" | jq -r '.id')
  first_name=$(echo "$user" | jq -r '.first_name // ""')
  last_name=$(echo "$user" | jq -r '.last_name // ""')
  # Output id and name to OUTFILE in format: id,first_name,last_name
  echo "$id,$first_name,$last_name" >> "$OUTFILE"

  case "$OUT_FORMAT" in
    csv)
      if [ "${_CSV_HEADER:-}" != 1 ]; then
        echo "id,first_name,last_name,email,role_id,roles"
        _CSV_HEADER=1
      fi
      # Print CSV values for each user
      echo "$user" | jq -r '
        [
          .id,
          (.first_name // ""),
          (.last_name // ""),
          (.email // ""),
          (.role_id // ""),
          ((.roles // []) | map(.name) | join("|"))
        ] | @csv
      '
      ;;
    ids)
      # Print ID and name (space separated)
      printf "%s %s %s\n" "$id" "$first_name" "$last_name"
      ;;
    json|*)
      echo "$user" | jq -c '{
        id, first_name, last_name, email,
        role_id,
        roles: ((.roles // []) | map(.name))
      }'
      ;;
  esac
done

echo "Wrote list of IDs and names to $OUTFILE" >&2