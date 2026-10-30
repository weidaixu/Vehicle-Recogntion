from __future__ import annotations
import json, os
import requests

FIELDS=["summary","proportions","lighting_signature","surface_language","aerodynamics","brand_cues","limitations"]
MODEL="deepseek-v4-flash"

def _api_error(response:requests.Response)->str:
    if response.status_code in (401,403): return "DeepSeek API Key 无效或无权限，请重新配置"
    if response.status_code == 402: return "DeepSeek 账户余额不足，请充值后重试"
    if response.status_code == 429: return "DeepSeek 请求过于频繁，请稍后重试"
    try:
        message=response.json().get("error",{}).get("message","")
    except (ValueError,AttributeError):
        message=""
    return f"DeepSeek API 请求失败（HTTP {response.status_code}）"+(f"：{message[:180]}" if message else "")

def generate_design_language(car:dict,user_focus:str="",transport=None):
    key=os.getenv("DEEPSEEK_API_KEY","").strip()
    if not key and transport is None: raise RuntimeError("DEEPSEEK_API_KEY is not configured")
    prompt=("你是汽车设计研究员。只根据给定车型名称和分类分析可观察的设计语言，不编造马力、尺寸或配置。"
            "返回纯JSON，字段为summary,proportions,lighting_signature,surface_language,aerodynamics,brand_cues,limitations。"
            f"车型资料：{json.dumps(car,ensure_ascii=False)}。关注点：{user_focus or '整体设计'}")
    payload={"model":MODEL,"messages":[{"role":"user","content":prompt}],"thinking":{"type":"disabled"},"temperature":.2,"max_tokens":2400,"response_format":{"type":"json_object"}}
    if transport: data=transport(payload)
    else:
        try:
            r=requests.post("https://api.deepseek.com/chat/completions",headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},json=payload,timeout=(10,90))
        except requests.Timeout as exc: raise RuntimeError("DeepSeek 请求超时，请检查网络后重试") from exc
        except requests.RequestException as exc: raise RuntimeError("无法连接 DeepSeek API，请检查网络或代理设置") from exc
        if not r.ok: raise RuntimeError(_api_error(r))
        try: data=r.json()
        except ValueError as exc: raise RuntimeError("DeepSeek 返回了无法解析的响应") from exc
    try: content=data["choices"][0]["message"]["content"]
    except (KeyError,IndexError,TypeError) as exc: raise RuntimeError("DeepSeek 响应缺少生成内容") from exc
    if not isinstance(content,str) or not content.strip(): raise RuntimeError("DeepSeek 未返回有效文本，请稍后重试")
    content=content.strip().removeprefix("```json").removesuffix("```").strip()
    try: parsed=json.loads(content)
    except json.JSONDecodeError as exc: raise RuntimeError("DeepSeek 返回内容不是有效 JSON，请重试") from exc
    if any(not isinstance(parsed.get(k),str) or not parsed[k].strip() for k in FIELDS): raise ValueError("DeepSeek returned an invalid design-language schema")
    return {k:parsed[k] for k in FIELDS}


def call_deepseek(messages, tools, tool_choice="auto", transport=None):
    """Call the chat-completions endpoint for one real tool-calling turn."""
    key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not key and transport is None:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")
    # DeepSeek V4's default Thinking Mode rejects explicit tool_choice.  The
    # agent still uses real tool calling, but runs this tool-call loop in the
    # supported non-thinking mode so the first classify_car call can remain
    # programmatically required.
    payload = {"model": MODEL, "messages": messages, "tools": tools, "tool_choice": tool_choice, "thinking": {"type": "disabled"}, "temperature": 0.2, "max_tokens": 1400}
    if transport is not None:
        return transport(payload)
    try:
        response = requests.post("https://api.deepseek.com/chat/completions", headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, json=payload, timeout=(10, 90))
    except requests.Timeout as exc:
        raise RuntimeError("DeepSeek 请求超时，请检查网络后重试") from exc
    except requests.RequestException as exc:
        raise RuntimeError("无法连接 DeepSeek API，请检查网络或代理设置") from exc
    if not response.ok:
        raise RuntimeError(_api_error(response))
    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError("DeepSeek 返回了无法解析的响应") from exc
