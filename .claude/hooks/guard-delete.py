#!/usr/bin/env python3
"""PreToolUse hook: prompt before any Bash delete outside thumbnails/ or projects/*/tmp.

Silent (no output) when a command deletes nothing, or only deletes inside those
two places. Otherwise it returns permissionDecision "ask" so Claude Code prompts,
even with sandbox auto-allow or acceptEdits on.
"""
import json
import os
import re
import shlex
import sys

SEPARATORS = {";", "&&", "||", "|", "&", "(", ")", "\n"}
DELETERS = {"rm", "rmdir", "unlink", "srm", "trash"}
WRAPPERS = {"sudo", "command", "builtin", "nice", "nohup", "time", "env"}


def ask(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "ask",
        "permissionDecisionReason": reason,
    }}))
    sys.exit(0)


def safe_target(raw, cwd, project):
    if any(c in raw for c in "$`") or raw.startswith("~"):
        return False
    path = os.path.normpath(os.path.join(cwd, raw))
    # Resolve symlinked parent dirs; the final component is what rm removes.
    path = os.path.join(os.path.realpath(os.path.dirname(path)), os.path.basename(path))
    rel = os.path.relpath(path, project)
    parts = rel.split(os.sep)
    if parts[0] == "..":
        return False
    if parts[0] == "thumbnails" and len(parts) >= 2:
        return True
    if len(parts) >= 3 and parts[0] == "projects" and parts[2] == "tmp":
        return True
    return False


def segments(tokens):
    seg = []
    for t in tokens:
        if t in SEPARATORS:
            if seg:
                yield seg
            seg = []
        else:
            seg.append(t)
    if seg:
        yield seg


def main():
    data = json.load(sys.stdin)
    cmd = (data.get("tool_input") or {}).get("command", "")
    cwd = data.get("cwd") or os.getcwd()
    project = os.path.realpath(os.environ.get("CLAUDE_PROJECT_DIR") or cwd)

    try:
        lexer = shlex.shlex(cmd, posix=True, punctuation_chars=";&|()")
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        if re.search(r"\b(rm|rmdir|unlink|-delete)\b", cmd):
            ask("Could not parse a command that looks like it deletes files.")
        return

    for seg in segments(tokens):
        while seg and (seg[0] in WRAPPERS or re.match(r"^\w+=", seg[0])):
            seg = seg[1:]
        if not seg:
            continue
        prog = os.path.basename(seg[0])
        args = seg[1:]

        if prog in ("bash", "sh", "zsh", "eval", "xargs", "parallel"):
            if any(re.search(r"\b(rm|rmdir|unlink)\b|-delete\b", a) for a in args):
                ask(f"`{prog}` runs a delete whose targets can't be checked.")
            continue

        if prog == "git" and args[:1] and args[0] in ("rm", "clean"):
            ask(f"`git {args[0]}` deletes files.")

        targets = None
        if prog in DELETERS:
            targets, after_dd = [], False
            for a in args:
                if a == "--" and not after_dd:
                    after_dd = True
                elif after_dd or not a.startswith("-"):
                    targets.append(a)
        elif prog == "find" and ("-delete" in args or any(
                a in ("-exec", "-execdir", "-ok", "-okdir") and i + 1 < len(args)
                and os.path.basename(args[i + 1]) in DELETERS
                for i, a in enumerate(args))):
            targets = []
            for a in args:
                if a.startswith("-") or a in ("(", "!"):
                    break
                targets.append(a)
            targets = targets or ["."]

        if targets is None:
            continue
        if not targets:
            ask(f"`{prog}` with no visible targets.")
        bad = [t for t in targets if not safe_target(t, cwd, project)]
        if bad:
            ask("Deletes outside thumbnails/ and projects/*/tmp: " + ", ".join(bad))


if __name__ == "__main__":
    main()
