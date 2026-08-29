# Architecture

## Goal

Telegram bot (and, optionally, REST API) to monitor and control 3D printers
running Klipper + Moonraker, without depending on being on the same network
as the printer. Designed to support multiple printers from day one.

## Layers

```
interfaces/telegram_bot/   interfaces/rest_api/
        \                         /
         \                       /
              core/services/         <- use cases (domain)
                    |
   core/moonraker_client.py, core/moonraker_ws.py, core/auth.py, core/state_store.py
                    |
              core/config.py
                    |
        printers.yaml   users.yaml   data/state.json (TinyDB)
        (all gitignored, local-only — see the .example templates)
```

`core/` doesn't import anything from `interfaces/`. The interface adapters
only call functions from `core/services/`, never talk directly to
Moonraker. This allows running the Telegram bot, the REST API, or both at
the same time, over the same logic.

## Static config vs. dynamic state

- **`printers.yaml`** (gitignored, local config — see `printers.yaml.example`):
  list of printers — name, Moonraker URL, optional api key, camera
  snapshot URL. Not versioned since it typically contains real LAN IPs.
- **`users.yaml`** (gitignored, local config — see `users.yaml.example`):
  allowlist of allowed users, not versioned since it contains real
  Telegram `user_id`s. It's the single source of truth for permissions —
  it isn't duplicated in TinyDB.
  It has two states per user:
  - `pending`: only the `username` is known (added by hand in the file, or
    via a bot command). Telegram doesn't allow resolving an `@username` to
    a `user_id` unless that user has messaged the bot before.
  - `confirmed`: the `username` messaged the bot at least once; its
    `user_id` (a stable identifier, doesn't change if the username changes)
    was resolved and saved. This rewrite is done atomically on the same
    `users.yaml`.
  - The `role` field exists from now (all `admin` for now) to allow adding
    differentiated roles (read-only vs. control) later without migrating
    the schema.
- **`data/state.json`** (TinyDB, gitignored): non-critical dynamic state —
  "active" printer per chat (to choose which one `/status` talks to when
  more than one is configured) and dedupe of push notifications already
  sent (to avoid repeating the same alert twice). See "Performance:
  `state.json` I/O" below — plain TinyDB storage would make this a
  meaningful CPU/disk cost on every single bot interaction.

## Chat model for alerts

There is a single **main chat** that receives push alerts from *all*
configured printers, each message identified by the printer's name (e.g.
`🖨️ K1C: print completed`). The main chat is determined as follows:

1. If `TELEGRAM_MAIN_CHAT_ID` is defined in `.env`, that one is used.
2. Otherwise, the chat of the first confirmed allowlist user who messages
   the bot is used.

No additional chats are created or linked per printer in this version:
Telegram doesn't allow a bot to create chats on its own (it can only talk
to chats that have already contacted it), so that idea is out of scope for
the MVP.

## File management (gcodes and timelapses)

Moonraker manages different file types under "roots" (`gcodes`,
`timelapse`, etc.) with the same generic list/download/delete endpoints
(`MoonrakerClient.list_files/download_file/delete_file`, in
`core/moonraker_client.py`). `core/services/job_service.py` (gcodes) and
`core/services/timelapse_service.py` reuse that generic client, each one
applying its own logic (starting a print vs. downloading/deleting).
Timelapses require the
[moonraker-timelapse](https://github.com/mainsail-crew/moonraker-timelapse)
component installed on Moonraker — without it, the `timelapse` root
doesn't exist and `/timelapses` returns an empty list or a Moonraker error.

`timelapse_service.list_timelapses` filters and deduplicates entries
before returning them: it keeps only known video extensions (`.mp4`,
`.mkv`, `.webm`, `.avi`, `.mov`) since moonraker-timelapse stores thumbnail
images (`.jpg`) alongside the renders in the same root; it drops entries
with the same path listed twice (some setups do this via a
symlinked/mirrored directory); and it drops 0-byte files, which are
almost always leftovers from a render that failed or got interrupted
mid-way (ffmpeg crash, Klipper restart during rendering). `/clear_timelapses`
still deletes every file in
the root regardless of size, so those broken leftovers get cleaned up too.

## Push alerts (WebSocket, not polling)

Moonraker supports a JSON-RPC WebSocket (`/websocket`) on which, after a
`printer.objects.subscribe`, the server **pushes** (`notify_status_update`)
changes to the subscribed objects (`print_stats`, `virtual_sdcard`,
temperatures) as soon as they occur — no need to poll in a loop. For each
printer in `printers.yaml` an `asyncio` task runs (`core/moonraker_ws.py`)
keeping that connection open; when it detects a relevant event (print
completed, error, unexpected pause), it calls `core/services/notifier.py`,
which:

1. Checks `state_store` to avoid repeating the same event.
2. If it's new, sends the message to the main chat via the Telegram bot
   instance (injected at startup).

## Detecting an offline/unreachable printer

Two independent mechanisms cover this, since it can be noticed either
while someone is actively interacting with the bot/API, or silently in
the background:

- **On-demand (commands/endpoints).** `MoonrakerClient` distinguishes two
  failure kinds in `core/moonraker_client.py`: a `MoonrakerUnavailableError`
  (subclass of `MoonrakerError`) when the HTTP request never got a
  response at all (`httpx.RequestError` — connection refused, timeout,
  DNS failure: the printer is very likely off or unreachable on the LAN),
  versus a plain `MoonrakerError` when Moonraker *did* respond but with an
  error status (it's up, just rejecting the request). Every bot command
  and REST endpoint that talks to Moonraker already catches
  `MoonrakerError`, so this distinction is transparent to them — the
  message is just clearer (e.g. "K1C is unreachable (printer off or not
  reachable on the network)") — except the REST layer, which additionally
  maps `MoonrakerUnavailableError` to HTTP `503` with
  `{"printer_offline": true}` in the body (instead of the generic `502`
  used for other Moonraker-side errors), so REST clients can tell the two
  cases apart programmatically.
- **In the background (WebSocket listener).** `core/moonraker_ws.py`'s
  `listen_printer` already reconnects forever with exponential backoff
  when the WebSocket drops. It now also pushes a one-off alert to the main
  chat the first time a connection attempt fails ("lost connection to
  Moonraker") and another when it succeeds again after that ("connection
  restored"), via `notifier.notify_now` — a version of `notifier.dispatch`
  that skips the persistent per-event dedupe in `state_store`, since
  connectivity flaps are a repeating condition tracked with an in-memory
  flag in `listen_printer` itself, not a one-shot state transition like
  "print completed". This means downtime gets reported even if no print
  was running when the printer went offline.

## Active printer selection

`/printers` shows inline buttons (one per printer in `printers.yaml`).
Pressing one saves it as the active printer for that chat in
`state_store`. The other commands (`/status`, `/pause`, etc.) use that
active printer if another one isn't explicitly specified.

## Performance: `state.json` I/O

`StateStore` (`core/state_store.py`) is on the hot path of every single bot
update: `auth_middleware.enforce_allowlist` calls
`state_store.get_main_chat_id()` before every handler runs, and most
handlers also touch `get_active_printer`/`set_active_printer`. TinyDB's
plain `JSONStorage` re-reads and re-serializes the *entire* file on every
single operation (reads included) and calls `os.fsync()` on every write —
on an SD-card-backed Pi, doing that synchronously inside the asyncio event
loop on every message is a real, avoidable CPU/IO cost. To fix this,
`StateStore` wraps the storage in TinyDB's `CachingMiddleware` (reads the
file once, serves later reads from memory, batches writes) on top of a
`_NoFsyncJSONStorage` (same as `JSONStorage`, minus the `fsync` call) —
acceptable because this file is explicitly non-critical, best-effort state
(see above), not a source of truth.

For the same reason, `mark_notified` keeps only the **latest** event per
printer instead of accumulating one row per event forever — an unbounded
`sent_notifications` table would make the full-file read/write on every
operation progressively more expensive over the bot's lifetime.

## Running in multiple modes

`main.py --mode bot|rest|both` (default `both`) decides what to start. Both
modes run in the same `asyncio` process (the bot with PTB, the REST API
with Quart, which is async-native), together with each printer's WebSocket
listeners.

## Deployment (systemd on DietPi)

`klipper_bot.service` runs the process as the unprivileged `dietpi` user
(uid/gid 1000, DietPi's default account) rather than root, and is scoped
with `ProtectSystem=strict` + `ProtectHome=read-only`. Under
`ProtectHome=read-only` the whole project directory (including
`/home/dietpi/klipper_bot`) is read-only by default, so the unit
explicitly whitelists the two paths the process writes to at runtime via
`ReadWritePaths=`: `data/` (TinyDB's `state.json`) and `users.yaml` (which
`core/config.py` rewrites atomically when a pending username gets
confirmed). `printers.yaml` and `.env` stay read-only. Adding any other
runtime-writable file requires extending `ReadWritePaths=` in the unit or
the write will fail with a permission error despite the file's own
permissions looking correct. See
[`README.md`](../README.md#deploy-on-a-raspberry-pi-running-dietpi-systemd)
for install steps.
