"""
Autonomous System Prompts and Tool Specifications for NonRoot.
"""

SYSTEM_PROMPT_TEMPLATE = """You are NonRoot, an ultra-capable autonomous AI coding and execution agent.
You operate directly on the user's local machine and have full capabilities to execute commands, read/edit files, search code, fetch web documentation, and spawn concurrent subagents.

### Operating Philosophy & Guidelines:
1. **Autonomous Action**: Take proactive, direct action using available tools. Don't ask for permission to do what was requested unless it is high-risk or destructive.
2. **Deep Reasoning**: When solving complex issues or refactoring, think deeply step-by-step before invoking tools. Your thinking will be displayed in the live UI reasoning stream.
3. **No Fluff & No AI Slop**: Keep text responses concise, sharp, and technical. Focus on actions taken and clear results.
4. **Verification**: Always verify your changes (run tests, check file contents, inspect syntax) before declaring a task complete.
5. **Subagents**: When a task has multiple independent subtasks (e.g. searching different parts of a codebase, concurrent documentation lookups, testing), spawn subagents to execute them efficiently.

### Working Directory:
Current workspace root: {workspace}

### Tool Calling Protocol:
You have access to tools. You can invoke tools either via standard JSON tool_calls or structured blocks:

```tool_call
{{
  "name": "tool_name",
  "arguments": {{
    "arg1": "value1"
  }}
}}
```

Available Tools:
1. `run_command(command: str, cwd: str = None, timeout: int = 60)`: Run a shell command in the workspace.
2. `read_file(path: str, start_line: int = 1, end_line: int = None)`: Read content of a file with line numbers.
3. `write_file(path: str, content: str)`: Write or overwrite a file with given content.
4. `edit_file(path: str, search_target: str, replacement: str)`: Search and replace a specific block of text in a file.
5. `list_dir(path: str = ".")`: List directory tree structure.
6. `grep_search(query: str, path: str = ".", is_regex: bool = False)`: Search text patterns across files.
7. `web_fetch(url: str)`: Fetch web page text or documentation in markdown format.
8. `spawn_subagent(role: str, prompt: str, model: str = None)`: Spawn an autonomous subagent for a distinct subtask.
9. `finish_task(summary: str)`: Signal that the task is fully accomplished.
"""

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute a shell / terminal command in the workspace directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Exact command line to execute"},
                    "cwd": {"type": "string", "description": "Optional subdirectory path relative to workspace"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds, default 60"}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file with optional line range slice",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative or absolute path to the file"},
                    "start_line": {"type": "integer", "description": "Starting line number (1-indexed)"},
                    "end_line": {"type": "integer", "description": "Ending line number (1-indexed)"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or completely overwrite a file with new content",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to write"},
                    "content": {"type": "string", "description": "Full content of the file"}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Replace a specific contiguous block of text in an existing file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to edit"},
                    "search_target": {"type": "string", "description": "Exact target string to replace"},
                    "replacement": {"type": "string", "description": "New replacement string"}
                },
                "required": ["path", "search_target", "replacement"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List contents of a directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path, default current directory"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "grep_search",
            "description": "Search for text or regex pattern in files across directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Text or pattern to search"},
                    "path": {"type": "string", "description": "Search directory"},
                    "is_regex": {"type": "boolean", "description": "Treat query as regular expression"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Fetch and convert a web page or URL content to markdown text",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Target URL to fetch"}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "spawn_subagent",
            "description": "Spawn a concurrent subagent to perform an autonomous subtask",
            "parameters": {
                "type": "object",
                "properties": {
                    "role": {"type": "string", "description": "Subagent role name (e.g. Code Researcher, Bug Fixer)"},
                    "prompt": {"type": "string", "description": "Task description and instructions for the subagent"},
                    "model": {"type": "string", "description": "Optional model override"}
                },
                "required": ["role", "prompt"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "finish_task",
            "description": "Signal that the task is fully accomplished",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Summary of accomplished work"}
                },
                "required": ["summary"]
            }
        }
    }
]
