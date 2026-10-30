"""Display names: agents, models (claude-opus-5-5 -> Claude Opus 5.5) and tool categories."""
from __future__ import annotations

import re

SOURCE_LABELS = {
    "claude-code": "Claude Code",
    "codex": "Codex",
    "cursor": "Cursor",
    "hermes": "Hermes",
}

# Tool names differ per agent; categories make "what did your agent do" comparable across them.
TOOL_CATEGORIES = {
    "Shell": {"bash", "exec", "exec_command", "local_shell_call", "shell", "terminal", "run_terminal_cmd",
              "write_stdin", "js", "process"},
    "Edit": {"edit", "multiedit", "write", "notebookedit", "apply_patch", "patch", "write_file", "edit_file",
             "search_replace", "str_replace_based_edit_tool"},
    "Read": {"read", "read_file", "view", "notebookread", "ls", "list_dir"},
    "Search": {"grep", "glob", "search_files", "codebase_search", "grep_search", "file_search", "toolsearch",
               "tool_search_call", "session_search"},
    "Web": {"websearch", "webfetch", "web_search", "web_extract", "web_search_call", "browser_exec"},
    "Subagents": {"agent", "task", "delegate_task", "spawn_task", "send_message"},
    "Planning": {"todowrite", "update_plan", "todo", "taskcreate", "taskupdate", "exitplanmode"},
}
_CATEGORY_OF = {name: category for category, names in TOOL_CATEGORIES.items() for name in names}


def tool_category(name: str) -> str:
    low = (name or "").strip().lower()
    if low.startswith("mcp__") or low.startswith("mcp_"):
        return "MCP"
    return _CATEGORY_OF.get(low, "Other")


def _words(rest: str) -> str:
    rest = rest.strip("-_ .")
    return (" " + " ".join(part.capitalize() for part in re.split(r"[-_]", rest) if part)) if rest else ""


def pretty_model(raw: str) -> str:
    name = (raw or "").strip()
    low = name.lower().split("/")[-1]
    low = re.sub(r"-\d{8}$", "", low)  # claude-haiku-4-5-20251001
    if not low or low == "unknown":
        return "Unknown model"
    if low in ("default", "auto"):
        return "Cursor Auto"
    match = re.match(r"^claude-(opus|sonnet|haiku|fable)-(\d+)(?:[-.](\d))?(?![\d])(.*)$", low)
    if match:
        family, major, minor, rest = match.groups()
        return f"Claude {family.capitalize()} {major}" + (f".{minor}" if minor else "") + _words(rest)
    match = re.match(r"^claude-(\d+)(?:[-.](\d))?-(opus|sonnet|haiku|fable)(.*)$", low)
    if match:
        major, minor, family, rest = match.groups()
        return f"Claude {family.capitalize()} {major}" + (f".{minor}" if minor else "") + _words(rest)
    match = re.match(r"^gpt-?(\d[\w.]*?)(-.*)?$", low)
    if match:
        return "GPT-" + match.group(1) + _words(match.group(2) or "")
    match = re.match(r"^composer-([\w.]+)$", low)
    if match:
        return "Cursor Composer " + match.group(1)
    if low.startswith("gemini-"):
        return "Gemini" + _words(low[len("gemini-"):])
    return name
