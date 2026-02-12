"""ツール定義とエグゼキューター

LLMエージェントが使用できるツールを定義し、実行する
"""

import os
import logging
import time
from typing import Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, asdict
import httpx

logger = logging.getLogger(__name__)

# Tavily API Key
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")


# =============================================================================
# ツール定義（OpenAI Function Calling形式）
# =============================================================================

WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search the web for current information. Use this when the question requires up-to-date information, news, or facts that might have changed after your knowledge cutoff.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to find relevant information"
                }
            },
            "required": ["query"]
        }
    }
}

# 利用可能なツール一覧
AVAILABLE_TOOLS = [WEB_SEARCH_TOOL]


# =============================================================================
# ツール実行ログ
# =============================================================================

@dataclass
class ToolExecutionLog:
    """ツール実行ログ"""
    timestamp: str
    tool_name: str
    arguments: Dict[str, Any]
    result_preview: str  # 結果の最初の100文字
    result_count: int  # 検索結果数など
    execution_time_ms: int
    success: bool
    error_message: str = None


class ToolLogger:
    """ツール実行を記録"""

    def __init__(self):
        self.logs: List[ToolExecutionLog] = []

    def log_execution(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result: str,
        execution_time_ms: int,
        success: bool = True,
        error_message: str = None
    ) -> ToolExecutionLog:
        """ツール実行を記録"""
        log = ToolExecutionLog(
            timestamp=datetime.utcnow().isoformat(),
            tool_name=tool_name,
            arguments=arguments,
            result_preview=result[:100] if result else "",
            result_count=result.count("\n- ") if result else 0,
            execution_time_ms=execution_time_ms,
            success=success,
            error_message=error_message,
        )
        self.logs.append(log)
        status = "✓" if success else "✗"
        logger.info(f"Tool: {tool_name} | {execution_time_ms}ms | {status}")
        return log

    def get_logs(self) -> List[Dict[str, Any]]:
        """全ログを取得"""
        return [asdict(log) for log in self.logs]


# =============================================================================
# ツール実行関数
# =============================================================================

async def execute_web_search(query: str, tool_logger: ToolLogger = None) -> str:
    """
    Tavily APIでWeb検索を実行

    Args:
        query: 検索クエリ
        tool_logger: ツール実行ログ（任意）

    Returns:
        検索結果をテキスト形式で整形したもの
    """
    start_time = time.time()

    if not TAVILY_API_KEY:
        error_msg = "Error: Web search not configured (TAVILY_API_KEY not set)"
        if tool_logger:
            tool_logger.log_execution(
                tool_name="web_search",
                arguments={"query": query},
                result=error_msg,
                execution_time_ms=0,
                success=False,
                error_message="TAVILY_API_KEY not configured"
            )
        logger.warning(error_msg)
        return error_msg

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": TAVILY_API_KEY,
                    "query": query,
                    "search_depth": "basic",  # basic or advanced
                    "max_results": 10,
                    "include_answer": True,  # AIサマリーを含める
                },
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()

            # 結果をテキストに整形
            results = data.get("results", [])
            formatted = []

            # AIサマリーがあれば追加
            if data.get("answer"):
                formatted.append(f"Summary: {data['answer']}")
                formatted.append("")

            formatted.append("Sources:")
            for r in results:
                title = r.get("title", "No title")
                content = r.get("content", "")[:300]
                url = r.get("url", "")
                formatted.append(f"- {title}")
                formatted.append(f"  {content}...")
                formatted.append(f"  URL: {url}")
                formatted.append("")

            result_text = "\n".join(formatted) if formatted else "No results found"

            execution_time_ms = int((time.time() - start_time) * 1000)

            if tool_logger:
                tool_logger.log_execution(
                    tool_name="web_search",
                    arguments={"query": query},
                    result=result_text,
                    execution_time_ms=execution_time_ms,
                    success=True
                )

            logger.info(f"Web search for '{query}': {len(results)} results in {execution_time_ms}ms")
            return result_text

    except Exception as e:
        execution_time_ms = int((time.time() - start_time) * 1000)
        error_msg = f"Error searching: {str(e)}"

        if tool_logger:
            tool_logger.log_execution(
                tool_name="web_search",
                arguments={"query": query},
                result=error_msg,
                execution_time_ms=execution_time_ms,
                success=False,
                error_message=str(e)
            )

        logger.error(f"Web search failed: {e}")
        return error_msg


async def search_images(query: str, max_results: int = 8) -> List[Dict[str, str]]:
    """
    Tavily APIで関連画像を検索

    Args:
        query: 検索クエリ
        max_results: 最大画像数

    Returns:
        画像URLのリスト [{"url": "...", "description": "..."}]
    """
    if not TAVILY_API_KEY:
        logger.warning("Image search: TAVILY_API_KEY not set")
        return []

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": TAVILY_API_KEY,
                    "query": query,
                    "search_depth": "basic",
                    "max_results": max_results,
                    "include_images": True,
                    "include_image_descriptions": True,
                },
                timeout=15.0
            )
            response.raise_for_status()
            data = response.json()

            images = []
            # Tavily APIのレスポンスから画像を取得
            raw_images = data.get("images", [])
            for img in raw_images[:max_results]:
                if isinstance(img, dict):
                    url = img.get("url", "")
                    desc = img.get("description", "")
                elif isinstance(img, str):
                    url = img
                    desc = ""
                else:
                    continue

                # 基本的なURLバリデーション
                if url and url.startswith("http"):
                    images.append({"url": url, "description": desc})

            logger.info(f"Image search for '{query}': {len(images)} images found")
            return images

    except Exception as e:
        logger.error(f"Image search failed: {e}")
        return []


async def execute_tool(
    name: str,
    arguments: Dict[str, Any],
    tool_logger: ToolLogger = None
) -> str:
    """
    ツール実行ディスパッチャー

    Args:
        name: ツール名
        arguments: ツール引数
        tool_logger: ツール実行ログ（任意）

    Returns:
        ツール実行結果
    """
    if name == "web_search":
        return await execute_web_search(arguments.get("query", ""), tool_logger)

    error_msg = f"Unknown tool: {name}"
    logger.warning(error_msg)

    if tool_logger:
        tool_logger.log_execution(
            tool_name=name,
            arguments=arguments,
            result=error_msg,
            execution_time_ms=0,
            success=False,
            error_message=error_msg
        )

    return error_msg
