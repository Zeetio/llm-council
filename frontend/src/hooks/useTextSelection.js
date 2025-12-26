import { useState, useEffect, useCallback } from 'react';

/**
 * テキスト選択を検知するカスタムフック
 *
 * @param {React.RefObject} containerRef - 選択対象のコンテナ要素
 * @returns {{ selectedText, anchorRect, clearSelection }}
 */
export function useTextSelection(containerRef) {
  const [selectedText, setSelectedText] = useState('');
  const [anchorRect, setAnchorRect] = useState(null);

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
      const containerRect = containerRef.current?.getBoundingClientRect() || { top: 0, left: 0 };
      // コンテナの内部スクロール位置を取得
      const scrollTop = containerRef.current?.scrollTop || 0;
      const scrollLeft = containerRef.current?.scrollLeft || 0;

      setSelectedText(text);
      setAnchorRect({
        // コンテナ相対位置（内部スクロール考慮）
        top: rect.bottom - containerRect.top + scrollTop,
        left: rect.left - containerRect.left + scrollLeft,
        width: rect.width,
        // 絶対位置（ウィンドウスクロール考慮）
        absoluteTop: rect.bottom + window.scrollY,
        absoluteLeft: rect.left + window.scrollX,
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

      // 選択がある場合、少し遅延してから確認（mouseupの後に実行されるため）
      setTimeout(() => {
        const selection = window.getSelection();
        if (!selection || selection.toString().trim() === '') {
          // 状態のみクリア（removeAllRangesは入力フィールドに影響するため呼ばない）
          setSelectedText('');
          setAnchorRect(null);
        }
      }, 10);
    };

    document.addEventListener('click', handleClick);
    return () => document.removeEventListener('click', handleClick);
  }, [selectedText]);

  return { selectedText, anchorRect, clearSelection };
}
