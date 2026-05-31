# TgramBotz

Telegram bot backed by an opencode-ai agent running in an E2B sandbox.

## Active sandbox

**Sandbox ID:** `inv8w825em5hs1ej2nu9k`

To reconnect after a new session:

```bash
echo "inv8w825em5hs1ej2nu9k" > .sandbox-id
just bot-status   # confirm it's running/paused
just bot-resume   # if paused
just bot-logs     # tail logs
```

> Do not run `just bot-stop` on this sandbox — it permanently kills it.

## Commands

```bash
just init         # install Doppler CLI (run first in every new session)
just bot-start    # create a new sandbox and start the bot
just bot-pause    # freeze sandbox (billing stops, state preserved)
just bot-resume   # thaw sandbox
just bot-status   # show sandbox state
just bot-logs     # tail last 50 lines from inside the sandbox
just bot-stop     # PERMANENTLY kill sandbox
```

See `CLAUDE.md` for full architecture and development notes.
