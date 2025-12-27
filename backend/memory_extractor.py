"""メモリ抽出・サマリー生成モジュール

LLMを使用して会話からユーザー情報を抽出し、会話サマリーを生成する。
安価なユーティリティモデル（DeepSeek R1 Distill等）を使用してコスト削減。
"""

import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from .openrouter import query_model
from . import storage
from .config import get_config

logger = logging.getLogger(__name__)

# デフォルトのユーティリティモデル（安価モデル）
DEFAULT_UTILITY_MODEL = "deepseek/deepseek-r1-distill-llama-8b"


def get_utility_model(project_id: str) -> str:
    """プロジェクトのユーティリティモデルを取得"""
    config = get_config(project_id)
    memory_settings = config.get("memory_settings", {})
    return memory_settings.get("utility_model", DEFAULT_UTILITY_MODEL)


def is_memory_enabled(project_id: str) -> bool:
    """メモリ機能が有効かチェック"""
    config = get_config(project_id)
    memory_settings = config.get("memory_settings", {})
    return memory_settings.get("enabled", True)


def is_auto_extract_enabled(project_id: str) -> bool:
    """自動抽出が有効かチェック"""
    config = get_config(project_id)
    memory_settings = config.get("memory_settings", {})
    return memory_settings.get("auto_extract", True)


def get_max_summaries(project_id: str) -> int:
    """最大サマリー数を取得"""
    config = get_config(project_id)
    memory_settings = config.get("memory_settings", {})
    return memory_settings.get("max_summaries", 15)


# =============================================================================
# メモリ抽出
# =============================================================================

MEMORY_EXTRACTION_PROMPT = """あなたはユーザー情報を抽出するアシスタントです。
以下の会話から、ユーザーに関する重要な情報を抽出してください。

{existing_memory_section}

今回の会話:
ユーザー: {user_message}
アシスタント: {assistant_response}

以下のカテゴリで新しい情報や更新が必要な情報を抽出してください:
- personal: 名前、職業、所属、年齢など
- preference: 好みのスタイル、形式、言語、詳細度など
- goal: 目標、プロジェクト、学習中のこと
- skill: スキルレベル、専門分野、経験
- context: 継続的な文脈（進行中の作業など）

JSON形式で回答してください（コードブロックなしで純粋なJSONのみ）:
{{
  "extracted": [
    {{
      "category": "カテゴリ名",
      "key": "キー（短い識別子）",
      "value": "値（詳細な内容）",
      "confidence": 0.0から1.0の確信度,
      "action": "add" または "update",
      "update_key": "更新の場合、既存メモリのキー"
    }}
  ]
}}

注意:
- 明示的に述べられた情報のみ抽出
- 推測は避ける（確信度0.7未満は含めない）
- 既存メモリと重複する場合はaction: "update"として処理
- 抽出すべき情報がない場合は空配列 {{"extracted": []}} を返す
- 必ず有効なJSON形式で回答"""


async def extract_memory_from_conversation(
    user_message: str,
    assistant_response: str,
    conversation_id: str,
    project_id: str = "default"
) -> List[Dict[str, Any]]:
    """
    会話からメモリを抽出してストレージに保存

    Args:
        user_message: ユーザーのメッセージ
        assistant_response: アシスタントの応答
        conversation_id: 会話ID
        project_id: プロジェクトID

    Returns:
        抽出されたメモリエントリのリスト
    """
    if not is_memory_enabled(project_id) or not is_auto_extract_enabled(project_id):
        logger.debug(f"Memory extraction disabled for project {project_id}")
        return []

    # 既存メモリを取得
    existing_memory = storage.get_memory(project_id)
    existing_entries = existing_memory.get("entries", [])

    # 既存メモリのセクションを構築
    if existing_entries:
        existing_text = "\n".join([
            f"- {e['category']}/{e['key']}: {e['value']}"
            for e in existing_entries
        ])
        existing_memory_section = f"既存のメモリ:\n{existing_text}"
    else:
        existing_memory_section = "既存のメモリ: なし"

    # プロンプト構築
    prompt = MEMORY_EXTRACTION_PROMPT.format(
        existing_memory_section=existing_memory_section,
        user_message=user_message,
        assistant_response=assistant_response[:2000]  # 長すぎる場合は切り詰め
    )

    # LLM呼び出し
    utility_model = get_utility_model(project_id)
    logger.info(f"Extracting memory using {utility_model}")

    try:
        response = await query_model(
            utility_model,
            [{"role": "user", "content": prompt}],
            timeout=30.0
        )

        if response is None:
            logger.warning("Memory extraction failed: no response")
            return []

        # JSONをパース
        content = response.get("content", "")
        extracted_data = _parse_json_response(content)

        if not extracted_data or "extracted" not in extracted_data:
            logger.debug("No memory to extract")
            return []

        # 抽出されたメモリを保存
        saved_entries = []
        for item in extracted_data["extracted"]:
            # 確信度チェック
            if item.get("confidence", 0) < 0.7:
                continue

            entry = {
                "category": item.get("category", "context"),
                "key": item.get("key", ""),
                "value": item.get("value", ""),
                "confidence": item.get("confidence", 0.8),
                "source_conversation_id": conversation_id,
            }

            # 既存エントリの更新 or 新規追加
            if item.get("action") == "update" and item.get("update_key"):
                # 同じカテゴリ・キーのエントリを探して更新
                updated = False
                for existing in existing_entries:
                    if existing.get("key") == item["update_key"]:
                        storage.update_memory_entry(
                            existing["id"],
                            {"value": entry["value"], "last_confirmed_at": datetime.utcnow().isoformat()},
                            project_id
                        )
                        updated = True
                        saved_entries.append(entry)
                        break
                if not updated:
                    # 見つからなければ新規追加
                    result = storage.add_memory_entry(entry, project_id)
                    saved_entries.append(result)
            else:
                # 新規追加
                result = storage.add_memory_entry(entry, project_id)
                saved_entries.append(result)

        logger.info(f"Extracted {len(saved_entries)} memory entries")
        return saved_entries

    except Exception as e:
        logger.error(f"Memory extraction error: {e}")
        return []


def _parse_json_response(content: str) -> Optional[Dict[str, Any]]:
    """LLMレスポンスからJSONをパース"""
    # コードブロックを除去
    content = content.strip()
    if content.startswith("```json"):
        content = content[7:]
    if content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # 部分的なJSONを探す
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(content[start:end])
            except json.JSONDecodeError:
                pass
        return None


# =============================================================================
# サマリー生成
# =============================================================================

SUMMARY_GENERATION_PROMPT = """以下の会話を要約してください。

会話タイトル: {title}
メッセージ数: {message_count}

既存サマリー:
{previous_summary}

新しい会話内容（直近の抜粋）:
{conversation_content}

以下のJSON形式で要約を作成してください（コードブロックなしで純粋なJSONのみ）:
{{
  "summary": "会話の要約（2-3文）",
  "key_topics": ["主要なトピック1", "トピック2", "トピック3"],
  "user_intent": "ユーザーの目的や意図",
  "outcome": "会話の結果や成果"
}}

注意:
- 既存サマリーがあれば更新するつもりで書き直す（古い情報は必要に応じて置き換える）
- 要約は簡潔かつ情報量を保つ
- key_topicsは3-5個程度
- 技術的な詳細よりも「何を達成しようとしていたか」に焦点
- 必ず有効なJSON形式で回答"""


def _build_recent_conversation_content(messages: List[Dict[str, Any]], max_chars: int = 3000, max_messages: int = 12) -> str:
    """直近の会話だけを取り出して要約入力にする（先頭だけの偏りを防ぐ）。"""
    lines = []
    total_len = 0

    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            final_response = msg.get("stage3", {}).get("response", "")
            if not final_response:
                continue
            line = f"アシスタント: {final_response}"
        else:
            line = f"ユーザー: {msg.get('content', '')}"

        if not line.strip():
            continue

        line_len = len(line) + 1
        if lines and total_len + line_len > max_chars:
            break

        lines.append(line)
        total_len += line_len

        if len(lines) >= max_messages:
            break

    lines.reverse()
    return "\n".join(lines)


async def generate_conversation_summary(
    conversation_id: str,
    project_id: str = "default"
) -> Optional[Dict[str, Any]]:
    """
    会話のサマリーを生成してストレージに保存

    Args:
        conversation_id: 会話ID
        project_id: プロジェクトID

    Returns:
        生成されたサマリー、または失敗時はNone
    """
    if not is_memory_enabled(project_id):
        logger.debug(f"Memory disabled for project {project_id}")
        return None

    # 会話を取得
    conversation = storage.get_conversation(conversation_id, project_id)
    if not conversation:
        logger.warning(f"Conversation {conversation_id} not found")
        return None

    messages = conversation.get("messages", [])
    if not messages:
        logger.debug("No messages to summarize")
        return None

    # 既存サマリーを取得（ローリング更新のため）
    summaries = storage.get_summaries(project_id)
    existing_summary = next(
        (s for s in summaries.get("entries", []) if s.get("conversation_id") == conversation_id),
        None
    )

    if existing_summary:
        previous_summary = (
            f"summary: {existing_summary.get('summary', '')}\n"
            f"key_topics: {existing_summary.get('key_topics', [])}\n"
            f"user_intent: {existing_summary.get('user_intent', '')}\n"
            f"outcome: {existing_summary.get('outcome', '')}"
        )
    else:
        previous_summary = "なし"

    # 直近の会話のみを構築（先頭偏りを防ぐ）
    conversation_content = _build_recent_conversation_content(messages)
    if not conversation_content.strip():
        logger.debug("No recent content to summarize")
        return None

    # プロンプト構築
    prompt = SUMMARY_GENERATION_PROMPT.format(
        title=conversation.get("title", "無題"),
        message_count=len(messages),
        previous_summary=previous_summary,
        conversation_content=conversation_content
    )

    # LLM呼び出し
    utility_model = get_utility_model(project_id)
    logger.info(f"Generating summary using {utility_model}")

    try:
        response = await query_model(
            utility_model,
            [{"role": "user", "content": prompt}],
            timeout=30.0
        )

        if response is None:
            logger.warning("Summary generation failed: no response")
            return None

        # JSONをパース
        content = response.get("content", "")
        summary_data = _parse_json_response(content)

        if not summary_data:
            logger.warning("Failed to parse summary response")
            return None

        # サマリーオブジェクトを構築
        summary = {
            "conversation_id": conversation_id,
            "title": conversation.get("title", "無題"),
            "summary": summary_data.get("summary", ""),
            "key_topics": summary_data.get("key_topics", []),
            "user_intent": summary_data.get("user_intent", ""),
            "outcome": summary_data.get("outcome", ""),
            "message_count": len(messages),
            "created_at": conversation.get("created_at", datetime.utcnow().isoformat()),
        }

        # ストレージに保存
        max_summaries = get_max_summaries(project_id)
        storage.add_summary(summary, project_id, max_summaries)

        logger.info(f"Generated summary for conversation {conversation_id}")
        return summary

    except Exception as e:
        logger.error(f"Summary generation error: {e}")
        return None


# =============================================================================
# メモリコンテキスト構築
# =============================================================================

def build_memory_context(
    project_id: str = "default",
    session_metadata: Optional[Dict[str, Any]] = None
) -> str:
    """
    4レイヤーメモリをLLMコンテキスト文字列に変換

    Args:
        project_id: プロジェクトID
        session_metadata: セッションメタデータ（オプション）

    Returns:
        LLMシステムプロンプトに追加するコンテキスト文字列
    """
    if not is_memory_enabled(project_id):
        return ""

    context_parts = []

    # レイヤー1: セッションメタデータ
    if session_metadata:
        meta_lines = []
        if session_metadata.get("device"):
            meta_lines.append(f"- デバイス: {session_metadata['device']}")
        if session_metadata.get("os"):
            meta_lines.append(f"- OS: {session_metadata['os']}")
        if session_metadata.get("timezone"):
            meta_lines.append(f"- タイムゾーン: {session_metadata['timezone']}")
        if session_metadata.get("language"):
            meta_lines.append(f"- 言語設定: {session_metadata['language']}")

        if meta_lines:
            context_parts.append("[現在のセッション情報]\n" + "\n".join(meta_lines))

    # レイヤー2: ユーザーメモリ
    memory = storage.get_memory(project_id)
    entries = memory.get("entries", [])
    if entries:
        # カテゴリ別にグループ化
        by_category = {}
        for entry in entries:
            cat = entry.get("category", "other")
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(f"- {entry['key']}: {entry['value']}")

        memory_lines = []
        category_labels = {
            "personal": "個人情報",
            "preference": "好み・スタイル",
            "goal": "目標・プロジェクト",
            "skill": "スキル・経験",
            "context": "現在の文脈",
        }
        for cat, items in by_category.items():
            label = category_labels.get(cat, cat)
            memory_lines.append(f"{label}:")
            memory_lines.extend(items)

        context_parts.append("[ユーザー情報]\n" + "\n".join(memory_lines))

    # レイヤー3: 最近の会話サマリー
    summaries = storage.get_summaries(project_id)
    summary_entries = summaries.get("entries", [])[:5]  # 直近5件
    if summary_entries:
        summary_lines = []
        for s in summary_entries:
            summary_lines.append(f"- {s['title']}: {s['summary']}")
        context_parts.append("[最近の会話履歴]\n" + "\n".join(summary_lines))

    if context_parts:
        return "\n\n".join(context_parts)
    return ""
