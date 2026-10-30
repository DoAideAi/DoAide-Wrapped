# DoAide Agent Wrapped

**Your year with AI coding agents, as a card worth posting.** One command reads the logs that
Claude Code, Codex, Cursor and Hermes Agent already keep on your computer, and turns them into a
year-in-review card: tokens, prompts, streak, your most-used model, a persona and one line of roast.
Nothing is uploaded.

> Status: v0.1, scaffolded 30 Oct 2026. Python standard library only (3.9+), 49 behaviour tests.
> The parsers were built against real logs on one Mac (Claude Code desktop 2026, Codex Desktop and
> `codex exec`, Cursor, Hermes) and read 5,400 log files (5.1 GB) in about 5 seconds. Not yet run on
> anyone else's machine, on Linux or on Windows, and not yet published: the GitHub and
> wrapped.doaide.com links below are where it will live.

## Run it

```sh
uvx --from git+https://github.com/DoAideAi/DoAide-Wrapped agent-wrapped
```

or, without installing anything:

```sh
git clone https://github.com/DoAideAi/DoAide-Wrapped && cd DoAide-Wrapped
python3 -m agent_wrapped
```

It prints the year's summary, writes `card.svg` and `card.html` to `./agent-wrapped-2026/` and
opens the HTML page, which has a "Save or share as PNG" button, the post text and a "Post on X"
link. Add `--png` to also render `card.png` with headless Chrome or Chromium.

| Option | Does |
| --- | --- |
| `--year 2025`, `--all-time` | wrap another year, or everything in the logs |
| `--sources claude-code,codex` | read only some agents (`claude-code`, `codex`, `cursor`, `hermes`) |
| `--json` | print the numbers as JSON instead of making a card |
| `--show-projects` | list your top projects in the terminal and JSON (never on the card) |
| `--hide-cost` | leave the API-equivalent cost off the card and the post text |
| `--url URL` | print a link in the card's footer |
| `--utc` | count days and hours in UTC instead of local time |
| `--list` | show which agents were found and where |
| `--home DIR` | read logs under another home folder (ignores `CLAUDE_CONFIG_DIR`, `CODEX_HOME`, `HERMES_HOME`) |

## Do this today: keep your Claude Code history

Claude Code deletes session transcripts after **30 days** unless `cleanupPeriodDays` is raised
([settings reference](https://code.claude.com/docs/en/settings-reference#cleanupperioddays)). Run
Agent Wrapped on 1 December with the default and the card covers November. Add this to
`~/.claude/settings.json` now:

```json
{ "cleanupPeriodDays": 3650 }
```

Deleted transcripts can't be recovered, and `0` is rejected. Agent Wrapped prints a warning when the
setting is missing or under a year.

## What it counts

| Agent | Reads | A prompt is | Tokens | Cost |
| --- | --- | --- | --- | --- |
| Claude Code | `~/.claude/projects/**/*.jsonl` (also `$CLAUDE_CONFIG_DIR`, `~/.config/claude`) | a message you typed, including one typed while the agent was working | per reply, counted once per message ID | the session's `cost-state` line, or per-line `costUSD` in older logs |
| Codex | `~/.codex/sessions/` and `archived_sessions/` (or `$CODEX_HOME`) | a user message in a thread you started | per response (`token_usage_record`), or the last cumulative `token_count` | not recorded |
| Cursor | `state.vscdb` in Cursor's `globalStorage` | a user message in a composer | only where Cursor stored a count, so a lower bound | not recorded |
| Hermes Agent | `state.db` in `$HERMES_HOME` (default `~/.hermes`) and every profile | a user message in a session a person started | session totals | as recorded |

These rules come from reading real logs, and each one corrects a count that would otherwise be
wrong:

* Claude Code writes one reply as several lines (one per content block) that share a message ID and
  repeat its usage. Summing lines would double or triple the tokens.
* The Claude desktop app routes every message through a queue, so queue entries say nothing about
  impatience. A message typed while the agent is mid-turn arrives as a `queued_command` attachment.
  Of 1,030 such attachments on the test machine, 1,003 were background-task notifications and 2 were
  messages from other agents; only 25 were typed. Only those count as prompts and "queued messages".
* Tool results, `/commands`, `<task-notification>` wrappers, meta lines and subagent (sidechain)
  prompts are not your prompts.
* In Codex, `task_started` is not a prompt: one automated Codex Desktop thread logged 3,718 turns
  for 17 user messages. `codex exec` runs and sub-agent threads count as usage, not prompts.
* In Hermes, delegated child sessions and cron or programmatic runs count as usage, not prompts.

Hours "with agents" is the time covered by activity, where a pause of more than 30 minutes ends a
stretch, merged across all agents. "Agent-hours" adds sessions up, so parallel sessions overlap.

## The card

It states totals only: tokens, prompts, sessions, active days, longest streak, hours with agents,
the API-equivalent cost (or lines added), the most-used model, the persona and the roast line. The
persona and roast come from fixed rules over the numbers (`agent_wrapped/persona.py`), not from a
model, so the same logs always give the same card. Personas include The Night Owl, The Interrupter,
The Shell Whisperer, The Delegator, The Marathoner and The Polyglot. Roast lines cover things like
interrupts, context compactions, "You're absolutely right" counts and output tokens in copies of
*War and Peace*.

## Privacy

* It only reads. Databases are opened read-only; one locked by a running app is read from a
  temporary copy that is deleted afterwards.
* Message text is checked only to tell your prompts from tool output, interrupts and commands, and
  to count one phrase ("absolutely right"). No text is stored or printed.
* No network requests. The card page loads nothing from the internet.
* Project names appear only with `--show-projects`, in the terminal and JSON, never on the card.
* Generated cards go to `agent-wrapped-*/`, which `.gitignore` excludes.

## Known limits

* Claude Code's `cost-state` line has no timestamp, so a session that crosses the year boundary
  counts its whole cost.
* A Claude desktop session started by another agent's spawn-task call has a first prompt written by
  that agent; it can't be told apart from a typed one.
* Cursor tool calls aren't counted, and its token totals are a lower bound.
* Not read yet: Gemini CLI, OpenCode, GitHub Copilot, Aider, Windsurf. Open an issue with the
  log location and the field names (values replaced by types).

## Development

```sh
python3 -m unittest discover -s tests -v     # behaviour tests against a fake home, stdlib only
python3 -m agent_wrapped.site                # rebuild site/index.html (a test fails while it is stale)
```

`tests/fakehome.py` builds small logs for every agent with the shapes real logs have, and the
expected numbers are worked out by hand. Launch timing and post drafts: [docs/launch.md](docs/launch.md).

MIT licence. Not affiliated with Anthropic, OpenAI, Anysphere (Cursor) or Nous Research.
