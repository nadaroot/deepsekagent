"""
DeepSeek API Client for NonRoot.
Supports streaming SSE completions, reasoning <think> tag separation,
tool calling, and multi-modal image/vision attachments.
"""

import json
import base64
import urllib.request
import urllib.error
from typing import Generator, Dict, Any, List, Optional

DEEPSEEK_MODELS = [
    {"id": "deepseek-chat", "name": "DeepSeek Chat (V3)", "desc": "Официальная флагманская модель DeepSeek-V3", "group": "Официальные"},
    {"id": "deepseek-reasoner", "name": "DeepSeek Reasoner (R1)", "desc": "Официальная reasoning-модель R1 с процессом мышления", "group": "Официальные"},
    {"id": "deepseek-coder", "name": "DeepSeek Coder (33B)", "desc": "Специализированная кодинг-модель", "group": "Официальные"},
    {"id": "deepseek-ai/DeepSeek-V3", "name": "DeepSeek-V3 (SiliconFlow/Router)", "desc": "DeepSeek V3 через роутер/провайдеры", "group": "Роутеры"},
    {"id": "deepseek-ai/DeepSeek-R1", "name": "DeepSeek-R1 (SiliconFlow/Router)", "desc": "DeepSeek R1 через роутер/провайдеры", "group": "Роутеры"},
    {"id": "deepseek-v3", "name": "deepseek-v3 (Alias)", "desc": "Короткий алиас DeepSeek V3", "group": "Алиасы"},
    {"id": "deepseek-r1", "name": "deepseek-r1 (Alias)", "desc": "Короткий алиас DeepSeek R1", "group": "Алиасы"},
    {"id": "deepseek-coder-33b-instruct", "name": "DeepSeek Coder 33B Instruct", "desc": "Инструкт-версия Coder 33B", "group": "Кодеры"},
    {"id": "deepseek-coder-6.7b-instruct", "name": "DeepSeek Coder 6.7B Instruct", "desc": "Быстрая легкая версия кодера", "group": "Кодеры"},
    {"id": "deepseek-math-7b-instruct", "name": "DeepSeek Math 7B", "desc": "Математическая логика и формулы", "group": "Специализированные"}
]

import os
import time
import socket
import subprocess
from pathlib import Path

def is_local_port_open(port: int) -> bool:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.4)
        res = s.connect_ex(("127.0.0.1", port))
        s.close()
        return res == 0
    except Exception:
        return False

def auto_start_deepseek_proxy(target_port: int = 9655) -> bool:
    if is_local_port_open(target_port) or is_local_port_open(3000):
        return True

    candidates = [
        Path.home() / ".nonroot" / "deepseek-api" / "server.js",
        Path.home() / "Applications" / "NonRoot.app" / "Contents" / "Resources" / "deepseek-api" / "server.js",
        Path("/Users/mac/Documents/strim/playerok/deepseek-api/server.js"),
        Path(__file__).parent.parent.parent.parent / "deepseek-api" / "server.js",
        Path(__file__).parent.parent.parent / "deepseek-api" / "server.js",
    ]

    node_exec = None
    for n in ["/usr/local/bin/node", "/opt/homebrew/bin/node", "/usr/bin/node"]:
        if os.path.exists(n) and os.access(n, os.X_OK):
            node_exec = n
            break

    if not node_exec:
        return False

    for s_path in candidates:
        if s_path.exists():
            env = os.environ.copy()
            env["NON_INTERACTIVE"] = "1"
            env["PORT"] = str(target_port)
            log_dir = Path.home() / ".nonroot"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "deepseek_proxy.log"
            try:
                f = open(log_file, "a")
                subprocess.Popen(
                    [node_exec, str(s_path)],
                    cwd=str(s_path.parent),
                    env=env,
                    stdout=f,
                    stderr=f
                )
                # Wait up to 3 seconds for proxy to start
                for _ in range(30):
                    time.sleep(0.1)
                    if is_local_port_open(target_port):
                        return True
            except Exception:
                pass
    return False

class DeepSeekClient:
    def __init__(self, api_base_url: str = "http://127.0.0.1:9655/v1", api_key: str = "sk-nonroot-free"):
        self.api_base_url = api_base_url.rstrip("/")
        self.api_key = api_key or "sk-nonroot-free"

    def _ensure_endpoint_ready(self):
        if "127.0.0.1" in self.api_base_url or "localhost" in self.api_base_url:
            if "9655" in self.api_base_url:
                if not is_local_port_open(9655):
                    auto_start_deepseek_proxy(9655)
            elif "3000" in self.api_base_url:
                if not is_local_port_open(3000):
                    if is_local_port_open(9655):
                        self.api_base_url = "http://127.0.0.1:9655/v1"
                    else:
                        auto_start_deepseek_proxy(9655)
                        if is_local_port_open(9655):
                            self.api_base_url = "http://127.0.0.1:9655/v1"

    def list_models(self) -> List[Dict[str, Any]]:
        self._ensure_endpoint_ready()
        models = list(DEEPSEEK_MODELS)
        try:
            url = f"{self.api_base_url}/models"
            req = urllib.request.Request(url, headers={
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": "NonRoot/1.0"
            })
            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                remote_models = data.get("data", [])
                if remote_models:
                    existing_ids = {m["id"] for m in models}
                    for m in remote_models:
                        m_id = m.get("id", "")
                        if m_id and m_id not in existing_ids:
                            models.append({
                                "id": m_id,
                                "name": m.get("name", m_id),
                                "desc": m.get("description", "API Модель"),
                                "group": "Доступные из API"
                            })
                            existing_ids.add(m_id)
        except Exception:
            pass
        return models

    def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        model: str = "deepseek-chat",
        temperature: float = 0.2,
        tools: Optional[List[Dict[str, Any]]] = None,
        images: Optional[List[str]] = None
    ) -> Generator[Dict[str, Any], None, None]:
        self._ensure_endpoint_ready()
        url = f"{self.api_base_url}/chat/completions"
        
        # Prepare messages payload
        payload_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            msg_images = msg.get("images", [])
            
            if msg_images and isinstance(content, str):
                parts = [{"type": "text", "text": content}]
                for img_data in msg_images:
                    if not img_data.startswith("data:"):
                        img_data = f"data:image/jpeg;base64,{img_data}"
                    parts.append({"type": "image_url", "image_url": {"url": img_data}})
                payload_messages.append({"role": role, "content": parts})
            else:
                payload_messages.append({"role": role, "content": content})

        if images and payload_messages:
            last_msg = payload_messages[-1]
            if last_msg["role"] == "user":
                if isinstance(last_msg["content"], str):
                    last_msg["content"] = [{"type": "text", "text": last_msg["content"]}]
                for img in images:
                    if not img.startswith("data:"):
                        img = f"data:image/jpeg;base64,{img}"
                    last_msg["content"].append({"type": "image_url", "image_url": {"url": img}})

        req_body = {
            "model": model,
            "messages": payload_messages,
            "temperature": temperature,
            "stream": True
        }
        if tools:
            req_body["tools"] = tools

        body_bytes = json.dumps(req_body).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "NonRoot/1.0"
        }

        try:
            req = urllib.request.Request(url, data=body_bytes, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=120) as resp:
                in_think_block = False
                current_tool_calls: Dict[int, Dict[str, Any]] = {}

                for line in resp:
                    line = line.decode("utf-8").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    if line == "data: [DONE]":
                        break
                    
                    try:
                        raw_json = line[len("data:"):].strip()
                        chunk = json.loads(raw_json)
                    except Exception:
                        continue

                    choices = chunk.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})

                    reasoning = delta.get("reasoning_content") or delta.get("reasoning")
                    if reasoning:
                        yield {"type": "reasoning", "content": reasoning}

                    content = delta.get("content", "")
                    if content:
                        if "<think>" in content:
                            in_think_block = True
                            parts = content.split("<think>", 1)
                            if parts[0]:
                                yield {"type": "content", "content": parts[0]}
                            if parts[1]:
                                yield {"type": "reasoning", "content": parts[1]}
                            continue

                        if "</think>" in content:
                            in_think_block = False
                            parts = content.split("</think>", 1)
                            if parts[0]:
                                yield {"type": "reasoning", "content": parts[0]}
                            if parts[1]:
                                yield {"type": "content", "content": parts[1]}
                            continue

                        if in_think_block:
                            yield {"type": "reasoning", "content": content}
                        else:
                            yield {"type": "content", "content": content}

                    tool_calls_delta = delta.get("tool_calls", [])
                    for tc in tool_calls_delta:
                        idx = tc.get("index", 0)
                        if idx not in current_tool_calls:
                            current_tool_calls[idx] = {
                                "id": tc.get("id", f"call_{idx}"),
                                "name": tc.get("function", {}).get("name", ""),
                                "arguments": ""
                            }
                        if tc.get("function", {}).get("name"):
                            current_tool_calls[idx]["name"] = tc["function"]["name"]
                        if tc.get("function", {}).get("arguments"):
                            current_tool_calls[idx]["arguments"] += tc["function"]["arguments"]

                    finish_reason = choices[0].get("finish_reason")
                    if finish_reason:
                        for tc_data in current_tool_calls.values():
                            try:
                                parsed_args = json.loads(tc_data["arguments"])
                            except Exception:
                                parsed_args = {"raw": tc_data["arguments"]}
                            yield {
                                "type": "tool_call",
                                "id": tc_data["id"],
                                "name": tc_data["name"],
                                "arguments": parsed_args
                            }
                        yield {"type": "done", "finish_reason": finish_reason}
                        return

        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode("utf-8")
                err_json = json.loads(err_body)
                err_msg = err_json.get("error", {}).get("message", err_body)
            except Exception:
                err_msg = f"HTTP Error {e.code}: {e.reason}"
            yield {"type": "error", "message": err_msg}
        except Exception as e:
            yield {"type": "error", "message": str(e)}
