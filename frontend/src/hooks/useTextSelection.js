import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * テキスト選択を検知するカスタムフック
 *
 * @param {React.RefObject} containerRef - 選択対象のコンテナ要素
 * @returns {{ selectedText, anchorRect, clearSelection }}
 */
export function useTextSelection(containerRef) {
  const [selectedText, setSelectedText] = useState('');
  const [anchorRect, setAnchorRect] = useState(null);

  // 選択直後のクリックを無視するためのフラグ
  const justSelectedRef = useRef(false);

  const handleMouseUp = useCallback(() => {
    // containerRef内での選択のみ対象
    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0) return;

    const range = selection.getRangeAt(0);

    // コンテナ内の選択かどうかを確認
    if (containerRef.current && !containerRef.current.contains(range.commonAncestorContainer)) {
      return;
    }

    const text = selection.toString().trim();

    if (text.length > 0) {
      const rect = range.getBoundingClientRect();

      // 選択直後フラグを立てる（クリックイベントがすぐ後に来るのを防ぐ）
      justSelectedRef.current = true;
      setTimeout(() => {
        justSelectedRef.current = false;
      }, 200); // 200ms間は選択直後とみなす

      setSelectedText(text);
      // ビューポート相対座標のみを使用（position: fixedで配置するため）
      setAnchorRect({
        top: rect.top,
        left: rect.left,
        right: rect.right,
        bottom: rect.bottom,
        width: rect.width,
        height: rect.height,
      });
    }
  }, [containerRef]);

  const clearSelection = useCallback(() => {
    setSelectedText('');
    setAnchorRect(null);
    window.getSelection()?.removeAllRanges();
  }, []);

  useEffect(() => {
    document.addEventListener('mouseup', handleMouseUp);
    return () => document.removeEventListener('mouseup', handleMouseUp);
  }, [handleMouseUp]);

  // クリック時に選択をクリア（選択エリア外をクリックした場合）
  useEffect(() => {
    const handleClick = (e) => {
      // ポップアップ内のクリックは無視
      if (e.target.closest('.comment-popup')) return;

      // 選択直後のクリックは無視（mouseup直後のclickイベント対策）
      if (justSelectedRef.current) return;

      // ポップアップが表示されている場合、外側クリックで閉じる
      if (selectedText) {
        setSelectedText('');
        setAnchorRect(null);
        return;
      }

      // 入力フィールド内のクリックは無視（カーソル操作を妨げないため）
      const tagName = e.target.tagName.toLowerCase();
      if (tagName === 'input' || tagName === 'textarea' || e.target.isContentEditable) {
        return;
      }
    };

    document.addEventListener('click', handleClick);
    return () => document.removeEventListener('click', handleClick);
  }, [selectedText]);

  return { selectedText, anchorRect, clearSelection };
}
