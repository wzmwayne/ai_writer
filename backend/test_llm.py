#!/usr/bin/env python3
"""测试 LLM 客户端模块

用法:
    python test_llm.py --list-models
    python test_llm.py --model deepseek-v4-flash-free --stream
    python test_llm.py --model deepseek-v4-flash-free --no-think
    python test_llm.py --model big-pickle
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.llm import LLMClient, LLMConfig, ThinkingEvent, ContentEvent, DoneEvent, ErrorEvent

API_KEY = "sk-Q6SCyDB23TFw1awzWLXh6Lu5CjjXboXqVWrI8HAD5gHwBfqfdkRfAzX1T9FD6D10"
BASE_URL = "https://opencode.ai/zen/v1"


async def list_models():
    client = LLMClient(LLMConfig(api_key=API_KEY, base_url=BASE_URL))
    models = await client.list_models()
    print(f"\n{'='*50}")
    print(f"可用模型 ({len(models)}):")
    print('='*50)
    for m in models:
        print(f"  - {m['id']}  (owned by: {m.get('owned_by','?')})")
    print()


async def chat_non_stream(model: str, thinking: bool = True):
    client = LLMClient(LLMConfig(api_key=API_KEY, base_url=BASE_URL, model=model))
    messages = [
        {"role": "user", "content": "用一句话描述人工智能的未来"}
    ]
    print(f"\n{'='*50}")
    print(f"非流式请求 | model={model} | thinking={thinking}")
    print(f"{'='*50}")
    resp = await client.chat(messages, thinking=thinking)
    if resp.reasoning_content:
        print(f"\n[思考过程]:\n{resp.reasoning_content[:300]}...")
    print(f"\n[回复]:\n{resp.content}")
    print(f"\n[用量]: {json.dumps(resp.usage, ensure_ascii=False) if resp.usage else 'N/A'}")
    print(f"[finish_reason]: {resp.finish_reason}")
    print()


async def chat_stream(model: str, thinking: bool = True):
    client = LLMClient(LLMConfig(api_key=API_KEY, base_url=BASE_URL, model=model))
    messages = [
        {"role": "user", "content": "用一句话描述人工智能的未来"}
    ]
    print(f"\n{'='*50}")
    print(f"流式请求 | model={model} | thinking={thinking}")
    print(f"{'='*50}")
    print()
    usage = None

    async for event in client.chat_stream(messages, thinking=thinking):
        if isinstance(event, ThinkingEvent):
            print(f"\033[90m[思考] {event.chunk}\033[0m", end="", flush=True)
        elif isinstance(event, ContentEvent):
            print(f"\033[92m{event.chunk}\033[0m", end="", flush=True)
        elif isinstance(event, DoneEvent):
            usage = event.usage
            print(f"\n\n[用量]: {json.dumps(usage, ensure_ascii=False) if usage else 'N/A'}")
            print(f"[finish_reason]: {event.finish_reason}")
        elif isinstance(event, ErrorEvent):
            print(f"\n\033[91m[错误]: {event.error}\033[0m")
    print()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="测试 LLM 客户端")
    parser.add_argument("--list-models", action="store_true", help="列出可用模型")
    parser.add_argument("--model", default="deepseek-v4-flash-free", help="模型名")
    parser.add_argument("--stream", action="store_true", help="流式模式")
    parser.add_argument("--no-think", action="store_true", help="禁用思考")
    args = parser.parse_args()

    if args.list_models:
        asyncio.run(list_models())
    elif args.stream:
        asyncio.run(chat_stream(args.model, thinking=not args.no_think))
    else:
        asyncio.run(chat_non_stream(args.model, thinking=not args.no_think))
