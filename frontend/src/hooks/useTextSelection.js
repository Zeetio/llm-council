import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * テキスト選択を検知するカスタムフック
 * デスクトップ(mouseup)とモバイル(selectionchange)の両方に対応
 *
 * @param {React.RefObject} containerRef - 選択対象のコンテナ要素
 * @returns {{ selectedText, anchorRect, clearSelection }}
 */
export function useTextSelection(containerRef) {
  const [selectedText, setSelectedText] = useState('');
  const [anchorRect, setAnchorRect] = useState(null);

  // 選択直後のクリック/タップを無視するためのフラグ
  const justSelectedRef = useRef(false);

  /**
   * 選択されたテキストとその位置を取得する共通処理
   */
  const processSelection = useCallback(() => {
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

      // 選択直後フラグを立てる（クリック/タップイベントがすぐ後に来るのを防ぐ）
      justSelectedRef.current = true;
      setTimeout(() => {
        justSelectedRef.current = false;
      }, 300); // 300ms間は選択直後とみなす（モバイルは少し長めに）

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

  // デスクトップ: mouseupで選択を検知
  useEffect(() => {
    const handleMouseUp = () => processSelection();
    document.addEventListener('mouseup', handleMouseUp);
    return () => document.removeEventListener('mouseup', handleMouseUp);
  }, [processSelection]);

  // モバイル: selectionchangeで選択を検知（タッチデバイス対応）
  // モバイルブラウザではmouseupの代わりにselectionchangeイベントが発火する
  useEffect(() => {
    let debounceTimer = null;

    const handleSelectionChange = () => {
      // デバウンス: selectionchangeは頻繁に発火するため、選択完了後に処理
      if (debounceTimer) clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        const selection = window.getSelection();
        const text = selection?.toString().trim();
        if (text && text.length > 0) {
          processSelection();
        }
      }, 300);
    };

    document.addEventListener('selectionchange', handleSelectionChange);
    return () => {
      document.removeEventListener('selectionchange', handleSelectionChange);
      if (debounceTimer) clearTimeout(debounceTimer);
    };
  }, [processSelection]);

  // クリック/タップ時に選択をクリア（選択エリア外をクリック/タップした場合）
  useEffect(() => {
    const handleDismiss = (e) => {
      // ポップアップ内のクリック/タップは無視
      if (e.target.closest('.comment-popup')) return;

      // 選択直後のクリック/タップは無視
      if (justSelectedRef.current) return;

      // ポップアップが表示されている場合、外側クリック/タップで閉じる
      if (selectedText) {
        setSelectedText('');
        setAnchorRect(null);
        return;
      }

      // 入力フィールド内のクリック/タップは無視（カーソル操作を妨げないため）
      const tagName = e.target.tagName.toLowerCase();
      if (tagName === 'input' || tagName === 'textarea' || e.target.isContentEditable) {
        return;
      }
    };

    document.addEventListener('click', handleDismiss);
    // モバイル: touchendでも閉じる
    document.addEventListener('touchend', handleDismiss);
    return () => {
      document.removeEventListener('click', handleDismiss);
      document.removeEventListener('touchend', handleDismiss);
    };
  }, [selectedText]);

  return { selectedText, anchorRect, clearSelection };
}
