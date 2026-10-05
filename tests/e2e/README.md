# Live end-to-end tests

These tests set the integration up in a test Home Assistant against a real ZoneMinder
server, then check entity states against what a separate zm-py client reads from that
server. The unit tests mock zm-py, so they can't catch what these do: the order of
coordinator refreshes, real ZoneMinder responses, and the real zm-py error behaviour.

Every test here is skipped unless `ZM_HOST` is set. The `tox` unit environments ignore
this directory entirely.

## Against zm-holodeck

`scripts/e2e-holodeck.sh` targets a stack that is **already running** and never starts,
stops or rebuilds containers. It finds the port with `docker compose port` and reads the
admin password from the stack, by compose project name (no checkout path needed).

```bash
./scripts/e2e-holodeck.sh                        # master stack (:8480), read-only tier
./scripts/e2e-holodeck.sh -p zm138 --write       # 1.38 stack, plus the write tier
./scripts/e2e-holodeck.sh --zm-py local          # your ../zm-py checkout, uncommitted edits included
./scripts/e2e-holodeck.sh --zm-py zm-py==0.5.5   # any pip requirement (PyPI, git+https://…@ref, a path)
./scripts/e2e-holodeck.sh -- tests/e2e/test_e2e_entities.py -x   # custom pytest args
```

## Choosing the zm-py under test

| How | zm-py used |
|-----|------------|
| `.venv/bin/pytest tests/e2e` (or `--zm-py venv`) | whatever `.venv` has. `pip install -e ../zm-py` makes that your working tree |
| `tox -e e2e-local` (`--zm-py local`) | editable install of `ZM_PY_SRC` (default `../zm-py`), so uncommitted edits are tested, with no commit or release needed |
| `ZM_PY=<requirement> tox -e e2e` (`--zm-py <requirement>`) | that requirement. Default: the pinned `zm-py==0.5.6` |

The tox environments skip installing the project (`package = skip`), so the pin in
`pyproject.toml` can't replace the zm-py you chose. The run ends with a summary of the
zm-py it actually imported: the version, and for an editable install the checkout path and
`git describe --dirty`. For example:

```
================================ ZoneMinder E2E ================================
  zm-py: zm-py 0.5.6, editable from ../zm-py @ 2f08fcb-dirty (../zm-py/zoneminder)
  ZoneMinder: http://127.0.0.1:8480 (version 1.39.36)
  Write target: monitor 7 (axis-1)
  PTZ target: monitor 9 (hikvision-1)
  Tiers: read, write
```

## Configuration

Set these in the environment or in `.env.zm_e2e` at the project root (gitignored). The
names are the same as in zm-py's live suite.

| Variable | Meaning |
|----------|---------|
| `ZM_HOST` | base URL, e.g. `http://127.0.0.1:8480` (required) |
| `ZM_USER` / `ZM_PASSWORD` | credentials (default `admin` / `admin`) |
| `ZM_SERVER_PATH` / `ZM_ZMS_PATH` | default `/zm/` and `/zm/cgi-bin/nph-zms` |
| `ZM_VERIFY_SSL` | `1` to verify TLS certificates |
| `ZM_E2E_WRITE` | `1` enables the write tier |
| `ZM_E2E_RUN_STATE` | `1` enables the run-state tier |
| `ZM_E2E_MONITOR` | id or name of the monitor the write tier changes (default: first capturing one) |
| `ZM_E2E_PTZ_MONITOR` | id or name of the PTZ camera (default: a controllable one, Hikvision first, never Reolink) |

The HA test plugin blocks network access in every test. The live tests open sockets to
the configured server only (by name or IP).

## Tiers

| Tier | Marker | Files | What it does to the server |
|------|--------|-------|----------------------------|
| read | `zm_e2e` | `test_e2e_setup.py`, `test_e2e_entities.py` | logins, reads, one failed login (wrong password) |
| write | `zm_e2e_write` | `test_e2e_write.py` | changes Recording and Function on one monitor and restores them, forces an alarm (records an event), pans a PTZ camera and sends it home |
| run state | `zm_e2e_run_state` | `test_e2e_write_run_state.py` | switches to another run state and back. Each switch **restarts the ZoneMinder daemons** (not the containers). Waits until the monitors capture again |

The run-state test needs a second run state. Holodeck creates one (`holodeck`).
