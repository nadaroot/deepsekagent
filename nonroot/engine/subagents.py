from pathlib import Path
"""
Subagent Manager for NonRoot.
Spawns and orchestrates background autonomous subagents with independent memory and execution loops.
"""

import time
import uuid
import threading
from typing import Dict, Any, List, Optional, Callable

class Subagent:
    def __init__(
        self,
        subagent_id: str,
        role: str,
        prompt: str,
        workspace: Path,
        client: Any,
        model: str = "deepseek-chat",
        on_event: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        self.id = subagent_id
        self.role = role
        self.prompt = prompt
        self.workspace = workspace
        self.client = client
        self.model = model
        self.on_event = on_event
        self.status = "running"
        self.created_at = int(time.time())
        self.finished_at = None
        self.result = None
        self.error = None
        self.thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self):
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self._stop_event.set()
        self.status = "killed"
        self.finished_at = int(time.time())

    def _emit(self, event_type: str, data: Dict[str, Any]):
        if self.on_event:
            payload = {
                "subagent_id": self.id,
                "role": self.role,
                "type": event_type,
                **data
            }
            self.on_event(payload)

    def _run_loop(self):
        from nonroot.engine.tools import ToolExecutor
        from nonroot.engine.prompts import SYSTEM_PROMPT_TEMPLATE, TOOL_DEFINITIONS

        tool_executor = ToolExecutor(self.workspace)
        sys_prompt = SYSTEM_PROMPT_TEMPLATE.format(workspace=str(self.workspace))
        subagent_sys = f"{sys_prompt}\n\n[SUBAGENT ROLE]: You are assigned the specialized role: '{self.role}'. Focus exclusively on your assigned subtask and conclude with finish_task()."

        messages = [
            {"role": "system", "content": subagent_sys},
            {"role": "user", "content": self.prompt}
        ]

        self._emit("status", {"status": "running", "message": f"Subagent '{self.role}' started"})

        step = 0
        max_steps = 15

        while step < max_steps and not self._stop_event.is_set():
            step += 1
            full_response = ""
            reasoning_buf = ""
            tool_calls = []

            for chunk in self.client.stream_chat(
                messages=messages,
                model=self.model,
                tools=TOOL_DEFINITIONS
            ):
                if self._stop_event.is_set():
                    return

                c_type = chunk.get("type")
                if c_type == "reasoning":
                    reasoning_buf += chunk.get("content", "")
                    self._emit("reasoning", {"delta": chunk.get("content", "")})
                elif c_type == "content":
                    full_response += chunk.get("content", "")
                    self._emit("content", {"delta": chunk.get("content", "")})
                elif c_type == "tool_call":
                    tool_calls.append(chunk)
                elif c_type == "error":
                    self.status = "error"
                    self.error = chunk.get("message")
                    self._emit("error", {"error": self.error})
                    return

            messages.append({"role": "assistant", "content": full_response})

            if not tool_calls:
                # Agent responded without tool calls - finish
                self.status = "completed"
                self.result = full_response
                self.finished_at = int(time.time())
                self._emit("finished", {"result": full_response})
                return

            # Execute tool calls
            for tc in tool_calls:
                t_name = tc.get("name")
                t_args = tc.get("arguments", {})

                self._emit("tool_start", {"tool": t_name, "args": t_args})
                res = tool_executor.execute(t_name, t_args)
                self._emit("tool_end", {"tool": t_name, "result": res})

                if res.get("is_finish"):
                    self.status = "completed"
                    self.result = res.get("summary", full_response)
                    self.finished_at = int(time.time())
                    self._emit("finished", {"result": self.result})
                    return

                messages.append({
                    "role": "tool",
                    "content": f"Tool '{t_name}' result: {res.get('output', '')} {res.get('error', '')}"
                })

        if not self.result and self.status == "running":
            self.status = "completed"
            self.result = "Subagent reached step limit."
            self.finished_at = int(time.time())
            self._emit("finished", {"result": self.result})

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "prompt": self.prompt,
            "model": self.model,
            "status": self.status,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "result": self.result,
            "error": self.error
        }

class SubagentManager:
    def __init__(self, workspace: Path, client: Any, on_event: Optional[Callable[[Dict[str, Any]], None]] = None):
        self.workspace = workspace
        self.client = client
        self.on_event = on_event
        self.subagents: Dict[str, Subagent] = {}

    def spawn(self, role: str, prompt: str, model: Optional[str] = None) -> Subagent:
        s_id = str(uuid.uuid4())[:8]
        subagent = Subagent(
            subagent_id=s_id,
            role=role,
            prompt=prompt,
            workspace=self.workspace,
            client=self.client,
            model=model or "deepseek-chat",
            on_event=self.on_event
        )
        self.subagents[s_id] = subagent
        subagent.start()
        return subagent

    def list_all(self) -> List[Dict[str, Any]]:
        return [s.to_dict() for s in self.subagents.values()]

    def kill(self, subagent_id: str) -> bool:
        if subagent_id in self.subagents:
            self.subagents[subagent_id].stop()
            return True
        return False

    def kill_all(self):
        for s in self.subagents.values():
            s.stop()
