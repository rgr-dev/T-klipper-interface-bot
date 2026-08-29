# klipper_bot

Telegram bot (and optional REST API) to monitor and control 3D printers
running Klipper + Moonraker from outside your home network. Supports
multiple printers. See [`docs/architecture.md`](docs/architecture.md) for
the full design.

> Status: in development (WIP). This README is updated as each piece is
> implemented — see the work plan for details on what's missing.

## Requirements

- Python 3.11+
- A printer with Klipper + Moonraker accessible on the network (typically a
  Raspberry Pi running this bot on the same LAN).
- A Telegram bot created with [@BotFather](https://t.me/BotFather).

## Installation

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env               # fill in TELEGRAM_BOT_TOKEN
cp printers.yaml.example printers.yaml
cp users.yaml.example users.yaml
```

Edit `printers.yaml` with your printer(s) data, and `users.yaml` with the
allowed Telegram users (by `username`, see
[`docs/architecture.md`](docs/architecture.md#static-config-vs-dynamic-state)).

`printers.yaml` and `users.yaml` are gitignored — they hold your LAN's IPs
and your Telegram allowlist, not meant to be published in a (potentially
public) repo. Only the `.example` templates are versioned.

## Usage

```bash
python main.py --mode bot     # bot only
python main.py --mode rest    # REST API only
python main.py --mode both    # both in a single process (default)
```

## Bot commands (MVP)

- `/start` — welcome message (triggered only when opening the chat with the bot for the first time).
- `/help` — list of available commands.
- `/printers` — lists the configured printers and allows choosing the active one (inline buttons). If only one printer is configured, it's used automatically without needing to select it.
- `/active` — shows which printer is currently active in this chat.
- `/status` — status, progress and temperatures (hotend/bed) of the active printer.
- `/pause`, `/resume` — pause/resume the active print.
- `/cancel` — cancels the active print, with confirmation (yes/no) before executing since it's a destructive action.
- `/snapshot` — current photo from the active printer's camera (requires `camera_snapshot_url` in `printers.yaml`).
- `/files [n]` — lists the last `n` uploaded gcode files (by date), in ascending order (the newest one ends up last, close to the buttons). Defaults to `n=5`; more can be explicitly requested, up to a cap of 20 (e.g. `/files 10`).
- `/timelapses [n]` — same as `/files` but for timelapses (requires the [moonraker-timelapse](https://github.com/mainsail-crew/moonraker-timelapse) component installed on Moonraker): lists the last `n` (defaults to 5, cap 20) and tapping one downloads it and sends it as a video to the chat.
- `/clear_timelapses` — deletes **all** timelapses of the active printer, with confirmation (yes/no) since it's a destructive and irreversible action.

Only responds to users confirmed in `users.yaml` (see
[`docs/architecture.md`](docs/architecture.md)). Push alerts
(print completed/error/paused) are sent automatically to the main chat — no
need to request them. The bot also alerts the main chat when it loses (and
later regains) its connection to a printer's Moonraker instance — e.g. if
the printer is powered off — even if nothing was printing at the time; see
["Detecting an offline/unreachable printer"](docs/architecture.md#detecting-an-offlineunreachable-printer).

## REST API (MVP)

Requires `REST_API_TOKEN` in `.env` (if not defined, the API responds
503 — it's disabled for security). Authentication: header
`Authorization: Bearer <token>`.

| Method | Route | Description |
|---|---|---|
| GET | `/api/printers` | Lists configured printers |
| GET | `/api/printers/<name>/status` | Status/progress/temperatures |
| POST | `/api/printers/<name>/pause` | Pause print |
| POST | `/api/printers/<name>/resume` | Resume print |
| POST | `/api/printers/<name>/cancel` | Cancel print |
| GET | `/api/printers/<name>/files` | List gcode files |
| POST | `/api/printers/<name>/print` | Start print (body: `{"filename": "..."}`) |
| GET | `/api/printers/<name>/snapshot` | Current camera photo (jpeg) |

If the printer/Moonraker can't be reached at all (off, unreachable on the
LAN), these endpoints respond `503` with `{"error": "...", "printer_offline": true}`
instead of the generic `502` used for other Moonraker-side errors.

## Deploy on a Raspberry Pi running DietPi (systemd)

`klipper_bot.service` targets a stock DietPi setup: the default `dietpi`
user/group (uid/gid 1000) and the project cloned at
`/home/dietpi/klipper_bot`. Adjust `User=`, `Group=`, `WorkingDirectory=`
and the `EnvironmentFile=`/`ExecStart=` paths if you install it elsewhere
(e.g. next to Moonraker under `/home/<klipper-user>/`).

1. **System packages.** DietPi's minimal image doesn't ship `venv` or
   `pip` by default — install them first:
   ```bash
   sudo apt update
   sudo apt install -y python3-venv python3-pip git
   ```
2. **Get the code and set up the virtualenv** (as the `dietpi` user, not
   root — the service runs unprivileged):
   ```bash
   cd /home/dietpi
   git clone <this-repo-url> klipper_bot
   cd klipper_bot
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env   # fill in TELEGRAM_BOT_TOKEN, etc.
   ```
   Edit `printers.yaml` and `users.yaml` as described above. Make sure
   `data/` exists (`mkdir -p data`) — that's where `state.json` (TinyDB)
   lives, and it's the only path the service can write to (see hardening
   below).
3. **Install the unit:**
   ```bash
   sudo cp klipper_bot.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now klipper_bot
   journalctl -u klipper_bot -f   # view logs
   ```
4. Moonraker runs on the printer itself (the K1C's own board), not on
   this DietPi device, so the unit only waits on
   `network-online.target` — there's no local `moonraker.service` to
   depend on. The bot reaches it over the LAN via `printers.yaml`'s
   `moonraker_url`; make sure that host/IP is reachable from the DietPi
   device before enabling the service (`curl http://<printer-ip>:7125/server/info`).

The shipped unit runs with a few systemd hardening options
(`ProtectSystem=strict`, `ProtectHome=read-only`, `NoNewPrivileges=true`)
and only allows writes under `data/` via `ReadWritePaths=`. If you add new
runtime-writable files elsewhere in the project (e.g. a different state
path), add them to `ReadWritePaths=` too or the service will fail with a
permission error despite file permissions looking correct.

**Updating:** `git pull`, `venv/bin/pip install -r requirements.txt` (in
case of new dependencies), then `sudo systemctl restart klipper_bot`.

## Development

```bash
pip install -r requirements-dev.txt
pytest
```

See [`CLAUDE.md`](CLAUDE.md) for the working rules in this repo
(includes the obligation to keep this documentation up to date on every
code change).
