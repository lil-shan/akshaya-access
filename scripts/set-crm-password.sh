#!/usr/bin/env bash
# Set your own password for the CRM test login (crm-tester@akshaya.test). Run it in your own terminal.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
set -a; . "$ROOT/.cloud.env"; set +a
read -rsp "New CRM password (min 6 chars): " PW; echo
[ "${#PW}" -ge 6 ] || { echo "Too short."; exit 1; }
UID_=$(curl -s "$SUPABASE_URL/auth/v1/admin/users?per_page=200" -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" \
  | python3 -c 'import sys,json,os;u=[x for x in json.load(sys.stdin)["users"] if x["email"]==os.environ["CRM_TEST_EMAIL"]];print(u[0]["id"] if u else "")')
[ -n "$UID_" ] || { echo "Test user not found."; exit 1; }
PW="$PW" python3 -c 'import json,os;print(json.dumps({"password":os.environ["PW"]}))' \
 | curl -s -o /dev/null -w "Password updated: HTTP %{http_code}\n" -X PUT "$SUPABASE_URL/auth/v1/admin/users/$UID_" \
   -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY" -H 'Content-Type: application/json' --data-binary @-
# keep .cloud.env in sync so the test scripts still work
PW="$PW" python3 - "$ROOT/.cloud.env" <<'PY'
import os,sys,re
p=sys.argv[1]; s=open(p).read()
s=re.sub(r'^CRM_TEST_PASSWORD=.*$', 'CRM_TEST_PASSWORD='+os.environ['PW'], s, flags=re.M)
open(p,'w').write(s)
PY
echo "Log in at https://akshaya-crm-zeta.vercel.app with $CRM_TEST_EMAIL and the password you just typed."
