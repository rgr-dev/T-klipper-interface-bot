# CLAUDE.md

Instructions for working in this repository.

## Documentation rule (permanent)

After every implementation or code edit, the relevant documentation
(`README.md`, `docs/architecture.md`) must be updated **in the same
change**. A task is not considered done if the documentation ends up
out of sync with the code. Specifically:

- If a bot command or REST endpoint is added/changed → update the
  corresponding section in `README.md`.
- If the format of `printers.yaml` or `users.yaml` changes → update the
  examples and explanation in `docs/architecture.md`.
- If the folder structure or data flow changes (push alerts, printer
  selection, allowlist resolution) → update `docs/architecture.md`.

## Architecture (summary)

See `docs/architecture.md` for the full detail. In short: `core/` contains
the domain logic (Moonraker, services, auth, state) agnostic of the
interface; `interfaces/telegram_bot/` and `interfaces/rest_api/` are thin
adapters that consume those services. `main.py --mode bot|rest|both`
decides what to run.

## Config and state

- `printers.yaml`: static printer config (source of truth, versionable).
- `users.yaml`: user allowlist (source of truth, versionable; also
  rewritten at runtime when a pending username gets confirmed).
- `data/state.json` (TinyDB, gitignored): non-critical dynamic state
  (active printer per chat, dedupe of notifications already sent).
