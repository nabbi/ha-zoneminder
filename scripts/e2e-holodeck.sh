#!/bin/bash
set -euo pipefail

# Run the live tests (tests/e2e) against an already running zm-holodeck stack.
# Never starts, stops or rebuilds containers: it only reads the admin password.
#
# Usage: ./scripts/e2e-holodeck.sh [options] [-- pytest args]
#   -p, --project NAME   compose project (default zm-holodeck; e.g. zm138, zm-multi)
#   --port PORT          host port (default: from the project, 8480 for zm-holodeck)
#   --zm-py WHICH        zm-py to test with:
#                          venv   whatever .venv has installed (default)
#                          local  editable ../zm-py, uncommitted edits included
#                                 (tox -e e2e-local; ZM_PY_SRC overrides the path)
#                          SPEC   any pip requirement, via tox -e e2e
#                                 (e.g. zm-py==0.5.5, git+https://...@branch, ../zm-py)
#   --write              enable the write tier (monitor settings, force alarm, PTZ)
#   --run-state          enable run state switching (restarts ZoneMinder daemons, not containers)
#
# ZM_PASSWORD in the environment skips the password lookup. The stack is found by
# compose project name, so the holodeck checkout's location does not matter.

cd "$(dirname "$0")/.."

PROJECT=zm-holodeck
PORT=""
ZM_PY_CHOICE=venv
PYTEST_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        -p|--project) PROJECT="$2"; shift 2 ;;
        --port) PORT="$2"; shift 2 ;;
        --zm-py) ZM_PY_CHOICE="$2"; shift 2 ;;
        --write) export ZM_E2E_WRITE=1; shift ;;
        --run-state) export ZM_E2E_RUN_STATE=1; shift ;;
        --) shift; PYTEST_ARGS=("$@"); break ;;
        -h|--help) sed -n '4,21p' "$0"; exit 0 ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
    esac
done

compose() {
    docker compose -p "$PROJECT" "$@"
}

if [[ -z "$PORT" ]]; then
    PORT="$(compose port zoneminder 80 2>/dev/null | sed 's/.*://')" || true
    if [[ -z "$PORT" ]]; then
        echo "Project $PROJECT has no running zoneminder service; start it from zm-holodeck or pass --port" >&2
        exit 1
    fi
fi

if [[ -z "${ZM_PASSWORD:-}" ]]; then
    ZM_PASSWORD="$(compose exec -T zoneminder cat /run/holodeck-secrets/zm_admin_password)"
fi

export ZM_HOST="http://127.0.0.1:$PORT" ZM_USER="${ZM_USER:-admin}" ZM_PASSWORD

[[ ${#PYTEST_ARGS[@]} -eq 0 ]] && PYTEST_ARGS=(tests/e2e -v -rs)

case "$ZM_PY_CHOICE" in
    venv) exec .venv/bin/pytest "${PYTEST_ARGS[@]}" ;;
    local) exec .venv/bin/tox -e e2e-local -- "${PYTEST_ARGS[@]}" ;;
    *) ZM_PY="$ZM_PY_CHOICE" exec .venv/bin/tox -e e2e -- "${PYTEST_ARGS[@]}" ;;
esac
