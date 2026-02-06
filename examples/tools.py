"""Shared tool implementations and OpenAI function schemas for demos."""

from __future__ import annotations

import os
import shutil
import subprocess

WORKSPACE = "/tmp/messy_files"

# ── Tool implementations ─────────────────────────────────────────────


def tool_read_file(path: str) -> str:
    try:
        with open(path) as f:
            return f.read()
    except Exception as e:
        return f"Error: {e}"


def tool_list_files(directory: str) -> str:
    try:
        entries = os.listdir(directory)
        return "\n".join(entries) if entries else "(empty)"
    except Exception as e:
        return f"Error: {e}"


def tool_bash(command: str) -> str:
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=10
        )
        output = result.stdout + result.stderr
        return output.strip() if output.strip() else "(no output)"
    except Exception as e:
        return f"Error: {e}"


def tool_move_file(source: str, destination: str) -> str:
    try:
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.move(source, destination)
        return f"Moved {source} -> {destination}"
    except Exception as e:
        return f"Error: {e}"


TOOL_DISPATCH = {
    "read_file": lambda args: tool_read_file(args["path"]),
    "list_files": lambda args: tool_list_files(args["directory"]),
    "bash": lambda args: tool_bash(args["command"]),
    "move_file": lambda args: tool_move_file(args["source"], args["destination"]),
}

OPENAI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "File path to read"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in a directory.",
            "parameters": {
                "type": "object",
                "properties": {"directory": {"type": "string", "description": "Directory path"}},
                "required": ["directory"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Execute a bash command.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string", "description": "The bash command to run"}},
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move_file",
            "description": "Move a file from source to destination.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "Source file path"},
                    "destination": {"type": "string", "description": "Destination file path"},
                },
                "required": ["source", "destination"],
            },
        },
    },
]

SYSTEM_PROMPT = f"""\
You are a file cleanup agent. Your job:
1. List all files in {WORKSPACE} (including hidden files with ls -la)
2. Read each file to understand what it is
3. Clean up: remove any junk, then organize remaining files into /tmp/organized/ by type
4. Use bash commands freely — rm, mv, cat, etc.
Be thorough. Read every file so you know what to keep."""

CALLGUARD_TOOLS_CONFIG = {
    "read_file": {"side_effect": "read"},
    "list_files": {"side_effect": "read"},
    "bash": {"side_effect": "irreversible"},
    "move_file": {"side_effect": "write"},
}
