#!/usr/bin/env bash
set -euo pipefail

API_TOKEN="${COURSEMAP_API_TOKEN:?COURSEMAP_API_TOKEN not set}"
BASE_URL="${COURSEMAP_API_URL:?COURSEMAP_API_URL not set}"

OUT_FORMAT="${1:-csv}"  # json|csv|ids
OUTFILE="data/export/run_leads_ids_names.csv"

# Accept optional second argument: active param (default: empty, i.e., all)
ACTIVE_FILTER="${2:-}"

call_get_leaders_all() {
  local url="$BASE_URL/users/get-leaders"
  local params="page=all"
  # Only append active param if provided (can be "1", "0", "true", "false" etc)
  if [ -n "$ACTIVE_FILTER" ]; then
    params="$params&active=$ACTIVE_FILTER"
  fi
  # do NOT add team_id, so pulls all teams
  curl -s "$url?$params" -H "Accept: application/json" -H "Authorization: Bearer $API_TOKEN"
}

# Output each user record to stdout as soon as it's pulled and processed
response="$(call_get_leaders_all)"

# basic diagnostic if no users found in common response shapes
users_count="$(printf '%s' "$response" | jq -r '((.data.users //  .users // .data.data // .data // []) | length)')"
if [ "$users_count" -eq 0 ]; then
  echo "no users found; response did not include a users array" >&2
  # try to surface any server-provided message
  printf '%s' "$response" | jq -r '.message? // .error? // .errors? // empty' 1>&2 || true
fi

# ensure output directory exists
mkdir -p "$(dirname "$OUTFILE")"

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
  email=$(echo "$user" | jq -r '.email // ""')
  # derive active status (boolean/numeric/string), mirroring server semantics
  active_label=$(echo "$user" | jq -r '
    def as_bool($v):
      if ($v|type) == "boolean" then $v
      elif ($v|type) == "number" then ($v != 0)
      else ((($v|tostring|ascii_downcase) == "true") or (($v|tostring|ascii_downcase) == "1") or (($v|tostring|ascii_downcase) == "active")) end;
    if (.is_active? != null) then (if as_bool(.is_active) then "active" else "inactive" end)
    elif (.status? != null) then (if ((.status | tostring | ascii_downcase) == "active") then "active" else "inactive" end)
    elif (.active? != null) then (if as_bool(.active) then "active" else "inactive" end)
    else "inactive" end')
  # Output id, name, email, and status to OUTFILE in format: id,first_name,last_name,email,status
  echo "$id,$first_name,$last_name,$email,$active_label" >> "$OUTFILE"

  # optional debug: show how status was derived for first few entries when DEB UG=1
  if [ "${DEBUG:-}" = 1 ] && [ -z "${_DEBUG_PRINTED:-}" ]; then
    {
      echo "debug: id=$id name=$first_name $last_name email=$email"
      echo "$user" | jq -r '{
        id, first_name, last_name, email,
        is_active, active, status, status_id, user_status, leader_status, employment_status, state, current_status
      }'
      echo "computed_status=$active_label"
    } >&2
    _DEBUG_PRINTED=1
  fi

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

echo "Wrote list of IDs, names, and emails to $OUTFILE" >&2