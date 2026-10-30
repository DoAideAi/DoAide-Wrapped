# Launch plan: Agent Wrapped

The window is fixed: people post year-in-review cards from about 1 December, and the format peaks
in the first two weeks of the month. ChatGPT Wrapped took off from a single user's prompt on
6 December 2025 ([Mashable](https://in.mashable.com/tech/103393/chatgpt-just-dropped-its-own-wrapped-heres-how-to-make-yours-in-minutes)).

## The November problem is the November hook

Claude Code deletes transcripts after 30 days unless `cleanupPeriodDays` is raised
([settings reference](https://code.claude.com/docs/en/settings-reference#cleanupperioddays)). Anyone
who runs Agent Wrapped on 1 December without changing it sees only November. So the first post is a
public service announcement, not a launch. It is useful on its own, and it builds the audience that
will run the tool in December.

| When | What | Where |
| --- | --- | --- |
| Now to mid-November | The retention post (draft 1), linking the repository for "the thing that needs it" | X, r/ClaudeAI, LinkedIn |
| 20-25 November | Teaser: an example card plus "runs on your logs, nothing uploaded" (draft 2) | X, LinkedIn |
| 1 December | Launch (draft 3) and Show HN (draft 4) | X, Hacker News, r/ClaudeAI, r/ChatGPTCoding, r/cursor |
| 1-15 December | Repost the best #AgentWrapped cards and answer "wrong numbers" issues within a day | X, GitHub |

Gate before 1 December: run it on at least five other people's machines (one Linux, one Windows),
fix every "wrong numbers" report, push to `DoAideAi/DoAide-Wrapped`, and deploy
`wrapped.doaide.com` from `site/index.html`.

## Drafts

**1. Retention post (November)**

> Claude Code deletes your session transcripts after 30 days by default.
>
> If you want to look back at your year (or resume an old session), add this to
> ~/.claude/settings.json today:
>
> { "cleanupPeriodDays": 3650 }
>
> Anything already deleted is gone. I'm building a "year in agents" card that reads these logs
> locally, and found out the hard way: [repo link]

**2. Teaser (late November)**

> Your 2026 with Claude Code, Codex, Cursor and Hermes, as one card. Tokens, prompts, streak,
> your most-used model, a persona and one line of roast.
>
> Reads the logs on your machine. Nothing is uploaded. Out 1 December. [example card image]

**3. Launch (1 December)**

> Agent Wrapped is out. One command:
>
> uvx --from git+https://github.com/DoAideAi/DoAide-Wrapped agent-wrapped
>
> It reads Claude Code, Codex, Cursor and Hermes logs locally and makes a card you can post. Mine:
> [card]. Post yours with #AgentWrapped.

**4. Show HN**

> Show HN: Agent Wrapped, a year-in-review card from your local AI coding agent logs
>
> Claude Code, Codex, Cursor and Hermes all keep detailed local logs. Agent Wrapped reads them
> (Python standard library, no network calls) and turns the year into a shareable card. The
> interesting part was getting the counts right: Claude Code writes one reply as several lines
> that share a message ID, the desktop app routes every message through a queue, most "queued"
> entries are background-task notifications, and a Codex Desktop thread can log thousands of
> automatic turns for a handful of user messages. The README lists every rule.

## What to measure

Stars and `#AgentWrapped` posts are the vanity numbers. The useful ones: share rate (cards posted
per tool run, estimated from posts vs. stars), "wrong numbers" issues per 100 stars, and the two
interest labels (`interest-team`, `interest-business`), which show whether a team edition is worth
building after December.
