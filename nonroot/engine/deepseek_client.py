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

class DeepSeekClient:
    def __init__(self, api_base_url: str = "http://127.0.0.1:3000/v1", api_key: str = "sk-nonroot-free"):
        self.api_base_url = api_base_url.rstrip("/")
        self.api_key = api_key or "sk-nonroot-free"

    def list_models(self) -> List[Dict[str, Any]]:
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
