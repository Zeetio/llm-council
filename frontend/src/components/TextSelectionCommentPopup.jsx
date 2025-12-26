import { useState, useRef, useEffect, useLayoutEffect } from 'react';
import './TextSelectionCommentPopup.css';

/**
 * テキスト選択時に表示されるコメント入力ポップアップ
 * position: fixed でビューポート相対配置
 *
 * @param {Object} props
 * @param {Object} props.anchorRect - ポップアップの位置 { top, left, right, bottom }
 * @param {string} props.selectedText - 選択されたテキスト
 * @param {function} props.onSubmit - コメント送信時のコールバック (comment: string) => void
 * @param {function} props.onCancel - キャンセル時のコールバック
 */
export default function TextSelectionCommentPopup({
  anchorRect,
  selectedText,
  onSubmit,
  onCancel,
}) {
  const [comment, setComment] = useState('');
  const textareaRef = useRef(null);
  const popupRef = useRef(null);
  const [popupStyle, setPopupStyle] = useState({
    top: anchorRect?.bottom ?? 0,
    left: anchorRect?.left ?? 0,
  });

  // ポップアップ表示時にフォーカス
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  }, []);

  // ビューポート内に収まるように位置を調整
  useLayoutEffect(() => {
    if (!anchorRect) return;

    const popup = popupRef.current;
    const margin = 8;
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    const popupWidth = popup?.offsetWidth ?? 320;
    const popupHeight = popup?.offsetHeight ?? 200;

    const belowTop = anchorRect.bottom + margin;
    const aboveTop = anchorRect.top - popupHeight - margin;

    let top = belowTop;
    if (belowTop + popupHeight > viewportHeight && aboveTop >= margin) {
      top = aboveTop;
    }

    top = Math.min(Math.max(top, margin), viewportHeight - popupHeight - margin);

    let left = anchorRect.left;
    if (left + popupWidth > viewportWidth - margin) {
      left = viewportWidth - popupWidth - margin;
    }
    if (left < margin) {
      left = margin;
    }

    setPopupStyle((prev) => (prev.top === top && prev.left === left ? prev : { top, left }));
  }, [anchorRect]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (comment.trim()) {
      onSubmit(comment.trim());
      setComment('');
    }
  };

  const handleKeyDown = (e) => {
    // Escでキャンセル
    if (e.key === 'Escape') {
      onCancel();
    }
    // Ctrl+Enterで送信
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      handleSubmit(e);
    }
  };

  // 選択テキストを短縮表示
  const truncatedText = selectedText.length > 100
    ? selectedText.substring(0, 100) + '...'
    : selectedText;

  return (
    <div
      ref={popupRef}
      className="comment-popup"
      style={popupStyle}
      onClick={(e) => e.stopPropagation()}
    >
      <div className="comment-popup__selected-text">
        「{truncatedText}」
      </div>

      <form onSubmit={handleSubmit}>
        <textarea
          ref={textareaRef}
          className="comment-popup__input"
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="コメントを入力（誤りや正しい情報を記述）"
          rows={3}
        />

        <div className="comment-popup__hint">
          Ctrl+Enter で送信 / Esc でキャンセル
        </div>

        <div className="comment-popup__actions">
          <button
            type="button"
            className="comment-popup__cancel"
            onClick={onCancel}
          >
            キャンセル
          </button>
          <button
            type="submit"
            className="comment-popup__submit"
            disabled={!comment.trim()}
          >
            追加
          </button>
        </div>
      </form>
    </div>
  );
}
