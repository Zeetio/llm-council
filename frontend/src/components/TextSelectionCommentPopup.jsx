import { useState, useRef, useEffect } from 'react';
import './TextSelectionCommentPopup.css';

/**
 * テキスト選択時に表示されるコメント入力ポップアップ
 *
 * @param {Object} props
 * @param {Object} props.anchorRect - ポップアップの位置 { top, left, width }
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

  // ポップアップ表示時にフォーカス
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  }, []);

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
      className="comment-popup"
      style={{
        top: anchorRect.top + 8,
        left: Math.max(0, anchorRect.left),
      }}
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
