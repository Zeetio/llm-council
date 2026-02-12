"""OpenRouter API client for making LLM requests."""

import httpx
import asyncio
import json
import time
import logging
from typing import List, Dict, Any, Optional
from .config import OPENROUTER_API_KEY, OPENROUTER_API_URL

logger = logging.getLogger(__name__)


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    system_prompt: Optional[str] = None,
    timeout: float = 120.0
) -> Optional[Dict[str, Any]]:
    """
    Query a single model via OpenRouter API.

    Args:
        model: OpenRouter model identifier (e.g., "openai/gpt-4o")
        messages: List of message dicts with 'role' and 'content'
        system_prompt: Optional system prompt to prepend
        timeout: Request timeout in seconds

    Returns:
        Response dict with 'content', 'reasoning_details', 'usage', 'model',
        'response_time_ms', or None if failed
    """
    start_time = time.time()

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    # Build messages with optional system prompt
    final_messages = []
    if system_prompt:
        final_messages.append({"role": "system", "content": system_prompt})
    final_messages.extend(messages)

    payload = {
        "model": model,
        "messages": final_messages,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                OPENROUTER_API_URL,
                headers=headers,
                json=payload
            )
            response.raise_for_status()

            data = response.json()
            message = data['choices'][0]['message']
            usage = data.get('usage', {})

            response_time_ms = int((time.time() - start_time) * 1000)

            return {
                'content': message.get('content'),
                'reasoning_details': message.get('reasoning_details'),
                'usage': {
                    'prompt_tokens': usage.get('prompt_tokens', 0),
                    'completion_tokens': usage.get('completion_tokens', 0),
                    'total_tokens': usage.get('total_tokens', 0),
                },
                'model': model,
                'response_time_ms': response_time_ms,
            }

    except Exception as e:
        logger.error(f"Error querying model {model}: {e}")
        return None


async def query_model_with_tools(
    model: str,
    messages: List[Dict[str, str]],
    tools: List[Dict[str, Any]] = None,
    tool_choice: str = "auto",
    system_prompt: Optional[str] = None,
    timeout: float = 120.0,
    max_tool_iterations: int = 5,
    tool_logger=None
) -> Optional[Dict[str, Any]]:
    """
    ツール使用をサポートするモデルクエリ

    ツール呼び出しがあれば実行し、結果をLLMに戻すループを実行

    Args:
        model: OpenRouter model identifier
        messages: List of message dicts
        tools: List of tool definitions (OpenAI function calling format)
        tool_choice: Tool choice strategy ('auto', 'none', 'required')
        system_prompt: Optional system prompt
        timeout: Request timeout in seconds
        max_tool_iterations: Maximum number of tool call iterations
        tool_logger: ToolLogger instance for logging tool executions

    Returns:
        Response dict with content, usage, tool info, or None if failed
    """
    from .tools import execute_tool, ToolLogger

    start_time = time.time()

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    # Build messages with optional system prompt
    final_messages = []
    if system_prompt:
        final_messages.append({"role": "system", "content": system_prompt})
    final_messages.extend(messages)

    # トークン使用量を累積
    total_usage = {
        'prompt_tokens': 0,
        'completion_tokens': 0,
        'total_tokens': 0,
    }

    # ツール使用情報
    tools_used = []

    # ローカルのToolLoggerを使用（渡されなかった場合）
    local_tool_logger = tool_logger or ToolLogger()

    for iteration in range(max_tool_iterations):
        payload = {
            "model": model,
            "messages": final_messages,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    OPENROUTER_API_URL,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                data = response.json()

            message = data['choices'][0]['message']
            usage = data.get('usage', {})

            # 使用量を累積
            total_usage['prompt_tokens'] += usage.get('prompt_tokens', 0)
            total_usage['completion_tokens'] += usage.get('completion_tokens', 0)
            total_usage['total_tokens'] += usage.get('total_tokens', 0)

            # ツール呼び出しがなければ終了
            if not message.get('tool_calls'):
                response_time_ms = int((time.time() - start_time) * 1000)

                return {
                    'content': message.get('content'),
                    'reasoning_details': message.get('reasoning_details'),
                    'usage': total_usage,
                    'model': model,
                    'response_time_ms': response_time_ms,
                    'tool_used': len(tools_used) > 0,
                    'tools_used': tools_used,
                }

            # ツール呼び出しを実行
            final_messages.append(message)  # assistant message with tool_calls

            for tool_call in message['tool_calls']:
                tool_name = tool_call['function']['name']
                try:
                    arguments = json.loads(tool_call['function']['arguments'])
                except json.JSONDecodeError:
                    arguments = {}

                logger.info(f"Tool call: {tool_name}({arguments})")

                result = await execute_tool(tool_name, arguments, local_tool_logger)

                final_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call['id'],
                    "content": result
                })

                tools_used.append({
                    "name": tool_name,
                    "arguments": arguments,
                })

        except Exception as e:
            logger.error(f"Error in tool loop for model {model}: {e}")
            return None

    # 最大イテレーション到達 → ツールなしで最終回答を強制取得
    logger.warning(f"Maximum tool iterations ({max_tool_iterations}) reached for {model}, forcing final answer")

    try:
        # ツールを外して最終回答を強制
        payload = {
            "model": model,
            "messages": final_messages,
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                OPENROUTER_API_URL,
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()

        message = data['choices'][0]['message']
        usage = data.get('usage', {})
        total_usage['prompt_tokens'] += usage.get('prompt_tokens', 0)
        total_usage['completion_tokens'] += usage.get('completion_tokens', 0)
        total_usage['total_tokens'] += usage.get('total_tokens', 0)

        response_time_ms = int((time.time() - start_time) * 1000)

        return {
            'content': message.get('content', ''),
            'reasoning_details': message.get('reasoning_details'),
            'usage': total_usage,
            'model': model,
            'response_time_ms': response_time_ms,
            'tool_used': len(tools_used) > 0,
            'tools_used': tools_used,
        }
    except Exception as e:
        logger.error(f"Fallback (no-tool) call failed for {model}: {e}")
        response_time_ms = int((time.time() - start_time) * 1000)
        return {
            'content': "Error: Failed to generate response after tool calls.",
            'reasoning_details': None,
            'usage': total_usage,
            'model': model,
            'response_time_ms': response_time_ms,
            'tool_used': len(tools_used) > 0,
            'tools_used': tools_used,
        }


async def query_models_parallel(
    models: List[str],
    messages: List[Dict[str, str]]
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Query multiple models in parallel (legacy function for compatibility).

    Args:
        models: List of OpenRouter model identifiers
        messages: List of message dicts to send to each model

    Returns:
        Dict mapping model identifier to response dict (or None if failed)
    """
    tasks = [query_model(model, messages) for model in models]
    responses = await asyncio.gather(*tasks)
    return {model: response for model, response in zip(models, responses)}


async def query_members_parallel(
    members: List[Dict[str, Any]],
    messages: List[Dict[str, str]],
    tools: List[Dict[str, Any]] = None,
    tool_logger=None
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Query multiple council members in parallel.

    Args:
        members: List of member dicts with 'id', 'model', 'system_prompt'
        messages: List of message dicts to send to each member
        tools: Optional list of tool definitions
        tool_logger: Optional ToolLogger for logging tool executions

    Returns:
        Dict mapping member id to response dict (or None if failed)
    """
    if tools:
        # ツール有効な場合
        tasks = [
            query_model_with_tools(
                member["model"],
                messages,
                tools=tools,
                system_prompt=member.get("system_prompt"),
                tool_logger=tool_logger
            )
            for member in members
        ]
    else:
        # ツールなしの場合（従来通り）
        tasks = [
            query_model(
                member["model"],
                messages,
                system_prompt=member.get("system_prompt")
            )
            for member in members
        ]

    responses = await asyncio.gather(*tasks)

    return {
        member["id"]: response
        for member, response in zip(members, responses)
    }
