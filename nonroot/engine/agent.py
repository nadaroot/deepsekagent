"""
Master Autonomous Agent for NonRoot.
Coordinates multi-turn conversations, reasoning extraction, autonomous ReAct loops,
tool execution, and subagent orchestration.
"""

import time
import json
import uuid
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

from nonroot.engine.deepseek_client import DeepSeekClient
from nonroot.engine.tools import ToolExecutor
from nonroot.engine.subagents import SubagentManager
from nonroot.engine.prompts import SYSTEM_PROMPT_TEMPLATE, TOOL_DEFINITIONS

class AutonomousAgent:
    def __init__(
        self,
        workspace: Path,
        api_base_url: str = "http://127.0.0.1:3000/v1",
        api_key: str = "sk-nonroot-free",
        model: str = "deepseek-chat",
        auto_accept: bool = True,
        max_steps: int = 30,
        system_prompt: str = "",
        on_event: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        self.workspace = Path(workspace).resolve()
        self.api_base_url = api_base_url
        self.api_key = api_key
        self.model = model
        self.auto_accept = auto_accept
        self.max_steps = max_steps
        self.custom_system_prompt = system_prompt
        self.on_event = on_event

        self.client = DeepSeekClient(api_base_url=self.api_base_url, api_key=self.api_key)
        self.tool_executor = ToolExecutor(workspace=self.workspace)
        self.subagent_manager = SubagentManager(
            workspace=self.workspace,
            client=self.client,
            on_event=self._on_subagent_event
        )

        self.messages: List[Dict[str, Any]] = []
        self.is_running = False
        self._stop_event = threading.Event()
        self._pending_tool_confirmation: Optional[Dict[str, Any]] = None
        self._tool_confirm_event = threading.Event()
        self._tool_approved = False

        self._init_system_prompt()

    def _init_system_prompt(self):
        base_prompt = SYSTEM_PROMPT_TEMPLATE.format(workspace=str(self.workspace))
        if self.custom_system_prompt:
            base_prompt += f"\n\n[ADDITIONAL USER INSTRUCTIONS]:\n{self.custom_system_prompt}"
        self.messages = [{"role": "system", "content": base_prompt}]

    def _emit(self, event_type: str, data: Dict[str, Any]):
        if self.on_event:
            self.on_event({"type": event_type, **data})

    def _on_subagent_event(self, event: Dict[str, Any]):
        self._emit("subagent_event", event)

    def stop(self):
        self._stop_event.set()
        self._tool_confirm_event.set()
        self.subagent_manager.kill_all()
        self.is_running = False
        self._emit("status", {"status": "stopped", "message": "Agent execution stopped by user"})

    def confirm_tool(self, approved: bool):
        self._tool_approved = approved
        self._tool_confirm_event.set()

    def update_settings(self, **kwargs):
        if "api_base_url" in kwargs or "api_key" in kwargs:
            self.api_base_url = kwargs.get("api_base_url", self.api_base_url)
            self.api_key = kwargs.get("api_key", self.api_key)
            self.client = DeepSeekClient(api_base_url=self.api_base_url, api_key=self.api_key)
        if "model" in kwargs:
            self.model = kwargs["model"]
        if "auto_accept" in kwargs:
            self.auto_accept = kwargs["auto_accept"]
        if "max_steps" in kwargs:
            self.max_steps = kwargs["max_steps"]
        if "workspace" in kwargs:
            self.workspace = Path(kwargs["workspace"]).resolve()
            self.tool_executor = ToolExecutor(workspace=self.workspace)
            self.subagent_manager.workspace = self.workspace
            self._init_system_prompt()

    def run_task(self, prompt: str, images: Optional[List[str]] = None):
        """Runs an autonomous task loop on a background thread."""
        if self.is_running:
            return False, "Agent is already running a task"
        self._stop_event.clear()
        self.is_running = True
        thread = threading.Thread(target=self._task_loop, args=(prompt, images), daemon=True)
        thread.start()
        return True, "Task launched"

    def _task_loop(self, prompt: str, images: Optional[List[str]] = None):
        try:
            self._emit("status", {"status": "thinking", "message": "Planning actions..."})
            
            user_msg = {"role": "user", "content": prompt}
            if images:
                user_msg["images"] = images
            self.messages.append(user_msg)
            self._emit("user_message", {"content": prompt, "images": images})

            step = 0
            while step < self.max_steps and not self._stop_event.is_set():
                step += 1
                self._emit("step_start", {"step": step, "max_steps": self.max_steps})

                reasoning_text = ""
                content_text = ""
                tool_calls = []

                for chunk in self.client.stream_chat(
                    messages=self.messages,
                    model=self.model,
                    tools=TOOL_DEFINITIONS,
                    images=images if step == 1 else None
                ):
                    if self._stop_event.is_set():
                        break

                    c_type = chunk.get("type")
                    if c_type == "reasoning":
                        reasoning_text += chunk.get("content", "")
                        self._emit("reasoning", {"delta": chunk.get("content", ""), "full": reasoning_text})
                    elif c_type == "content":
                        content_text += chunk.get("content", "")
                        self._emit("content", {"delta": chunk.get("content", ""), "full": content_text})
                    elif c_type == "tool_call":
                        tool_calls.append(chunk)
                    elif c_type == "error":
                        self._emit("error", {"error": chunk.get("message")})
                        self.is_running = False
                        return

                if self._stop_event.is_set():
                    break

                # Record assistant turn in context
                self.messages.append({"role": "assistant", "content": content_text})

                # Check if model outputted tool_call blocks in content text directly
                if not tool_calls and "```tool_call" in content_text:
                    import re
                    matches = re.findall(r'```tool_call\s*(\{[\s\S]*?\})\s*```', content_text)
                    for m in matches:
                        try:
                            parsed = json.loads(m)
                            tool_calls.append({
                                "id": f"call_{len(tool_calls)+1}",
                                "name": parsed.get("name"),
                                "arguments": parsed.get("arguments", {})
                            })
                        except Exception:
                            pass

                if not tool_calls:
                    # Model finished turn without tool calls
                    self._emit("task_completed", {
                        "response": content_text,
                        "steps": step
                    })
                    break

                # Execute tool calls
                for tc in tool_calls:
                    if self._stop_event.is_set():
                        break

                    t_id = tc.get("id", str(uuid.uuid4())[:6])
                    t_name = tc.get("name")
                    t_args = tc.get("arguments", {})

                    # Special handling for spawn_subagent tool
                    if t_name == "spawn_subagent":
                        sub_role = t_args.get("role", "Subagent")
                        sub_prompt = t_args.get("prompt", "")
                        sub_model = t_args.get("model") or self.model
                        sub = self.subagent_manager.spawn(role=sub_role, prompt=sub_prompt, model=sub_model)
                        res = {
                            "success": True,
                            "output": f"Subagent '{sub_role}' (ID: {sub.id}) spawned in background.",
                            "subagent_id": sub.id,
                            "subagent_role": sub_role,
                            "subagent_prompt": sub_prompt,
                            "is_subagent": True
                        }
                    else:
                        # Auto-Accept vs Confirmation Check
                        if not self.auto_accept and t_name in ["run_command", "write_file", "edit_file"]:
                            self._pending_tool_confirmation = {"id": t_id, "name": t_name, "args": t_args}
                            self._tool_confirm_event.clear()
                            self._emit("tool_confirmation_required", {
                                "id": t_id,
                                "name": t_name,
                                "args": t_args
                            })
                            # Wait for user approval
                            self._tool_confirm_event.wait()
                            if self._stop_event.is_set() or not self._tool_approved:
                                res = {"success": False, "error": "Tool execution rejected by user."}
                            else:
                                self._emit("tool_start", {"id": t_id, "name": t_name, "args": t_args})
                                res = self.tool_executor.execute(t_name, t_args)
                        else:
                            self._emit("tool_start", {"id": t_id, "name": t_name, "args": t_args})
                            res = self.tool_executor.execute(t_name, t_args)

                    self._emit("tool_end", {"id": t_id, "name": t_name, "result": res})

                    if res.get("is_finish"):
                        self._emit("task_completed", {
                            "response": res.get("summary", content_text),
                            "steps": step
                        })
                        self.is_running = False
                        return

                    out_str = res.get("output", "")
                    if res.get("error"):
                        out_str += f"\nError: {res['error']}"

                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": t_id,
                        "content": out_str
                    })

        except Exception as e:
            self._emit("error", {"error": f"Agent loop error: {str(e)}"})
        finally:
            self.is_running = False
            self._emit("status", {"status": "idle", "message": "Ready"})
