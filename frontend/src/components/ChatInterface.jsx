import { useState, useEffect, useRef, memo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import Stage1 from './Stage1';
import Stage2 from './Stage2';
import Stage3 from './Stage3';
import UsageStats from './UsageStats';
import TextSelectionCommentPopup from './TextSelectionCommentPopup';
import { useTextSelection } from '../hooks/useTextSelection';
import './ChatInterface.css';

// メモ化されたメッセージコンポーネント（ReactMarkdownの不要な再レンダーを防ぐ）
const MessageItem = memo(function MessageItem({ msg }) {
  if (msg.role === 'user') {
    return (
      <div className="message-group">
        <div className="user-message">
          <div className="message-label">You</div>
          <div className="message-content">
            <div className="markdown-content">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {msg.content}
              </ReactMarkdown>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="message-group">
      <div className="assistant-message">
        <div className="message-label">LLM Council</div>

        {/* Stage 1 */}
        {msg.loading?.stage1 && (
          <div className="stage-loading">
            <div className="spinner"></div>
            <span>Running Stage 1: Collecting individual responses...</span>
          </div>
        )}
        {msg.stage1 && <Stage1 responses={msg.stage1} />}

        {/* Stage 2 */}
        {msg.loading?.stage2 && (
          <div className="stage-loading">
            <div className="spinner"></div>
            <span>Running Stage 2: Peer rankings...</span>
          </div>
        )}
        {msg.stage2 && (
          <Stage2
            rankings={msg.stage2}
            labelToId={msg.metadata?.label_to_id}
            aggregateRankings={msg.metadata?.aggregate_rankings}
            stage1Results={msg.stage1}
          />
        )}

        {/* Stage 3 */}
        {msg.loading?.stage3 && (
          <div className="stage-loading">
            <div className="spinner"></div>
            <span>Running Stage 3: Final synthesis...</span>
          </div>
        )}
        {msg.stage3 && <Stage3 finalResponse={msg.stage3} />}

        {/* Usage Stats - Stage3完了後に表示 */}
        {msg.usage && <UsageStats usage={msg.usage} />}
      </div>
    </div>
  );
});

export default function ChatInterface({
  conversation,
  onSendMessage,
  isLoading,
  onAddComment,
  onDeleteComment,
  onStopGeneration,
  pendingComments = [],
  onToggleSidebar,
  isMobile = false,
  isSidebarOpen = false,
}) {
  const [input, setInput] = useState('');
  const [attachedFiles, setAttachedFiles] = useState([]);
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const messagesContainerRef = useRef(null);

  // テキスト選択検知
  const { selectedText, anchorRect, clearSelection } = useTextSelection(messagesContainerRef);

  // 選択中のコンテキスト情報
  const [selectionContext, setSelectionContext] = useState(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [conversation]);

  const handleFileSelect = async (e) => {
    const files = Array.from(e.target.files);
    const textFiles = [];

    for (const file of files) {
      try {
        const content = await file.text();
        textFiles.push({ name: file.name, content });
      } catch (err) {
        console.error(`Failed to read file ${file.name}:`, err);
      }
    }

    setAttachedFiles((prev) => [...prev, ...textFiles]);
    e.target.value = '';
  };

  const removeFile = (index) => {
    setAttachedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if ((input.trim() || attachedFiles.length > 0) && !isLoading) {
      let fullMessage = input;

      if (attachedFiles.length > 0) {
        const fileContents = attachedFiles
          .map((f) => `--- ${f.name} ---\n${f.content}`)
          .join('\n\n');
        fullMessage = fullMessage
          ? `${fullMessage}\n\n${fileContents}`
          : fileContents;
      }

      onSendMessage(fullMessage);
      setInput('');
      setAttachedFiles([]);
    }
  };

  const handleKeyDown = (e) => {
    // Submit on Enter (without Shift)
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  // コメント送信ハンドラー
  const handleCommentSubmit = (comment) => {
    // 選択テキストを先にキャプチャ（clearSelection前に）
    const capturedText = selectedText;

    // 先にポップアップを閉じる
    clearSelection();

    // 次のイベントループでコメントを追加（Reactのレンダリングを安定させる）
    if (onAddComment && capturedText) {
      setTimeout(() => {
        onAddComment({
          selectedText: capturedText,
          comment,
        });
      }, 0);
    }
  };

  // コメントキャンセルハンドラー
  const handleCommentCancel = () => {
    clearSelection();
  };

  const hasConversation = Boolean(conversation);
  const messages = conversation?.messages ?? [];
  const conversationTitle = conversation?.title || 'LLM Council';

  return (
    <div className="chat-interface">
      {isMobile && (
        <div className="chat-header">
          <button
            type="button"
            className="menu-button"
            onClick={() => onToggleSidebar?.()}
            aria-label="Open sidebar"
          >
            ☰
          </button>
          <div className="chat-header__title">
            {conversationTitle}
          </div>
        </div>
      )}

      {isMobile && !isSidebarOpen && (
        <button
          type="button"
          className="menu-button menu-button--floating"
          onClick={() => onToggleSidebar?.()}
          aria-label="Open sidebar"
        >
          ☰
        </button>
      )}
      <div className="messages-container" ref={messagesContainerRef}>
        {!hasConversation ? (
          <div className="empty-state">
            <h2>Welcome to LLM Council</h2>
            <p>Create a new conversation to get started</p>
          </div>
        ) : messages.length === 0 ? (
          <div className="empty-state">
            <h2>Start a conversation</h2>
            <p>Ask a question to consult the LLM Council</p>
          </div>
        ) : (
          messages.map((msg, index) => (
            <MessageItem key={index} msg={msg} />
          ))
        )}

        {isLoading && (
          <div className="loading-indicator">
            <div className="spinner"></div>
            <span>Consulting the council...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {hasConversation && (
        <>
          {/* 保留中のコメント表示 */}
          {pendingComments.length > 0 && (
            <div className="pending-comments">
              <div className="pending-comments__header">
                <span className="pending-comments__icon">💬</span>
                <span className="pending-comments__title">
                  {pendingComments.length}件のフィードバックが次の送信に含まれます
                </span>
              </div>
              <div className="pending-comments__list">
                {pendingComments.map((c) => (
                  <div key={c.id} className="pending-comment">
                    <span className="pending-comment__text">
                      「{c.selectedText?.length > 30 ? c.selectedText.substring(0, 30) + '...' : c.selectedText}」
                    </span>
                    <span className="pending-comment__arrow">→</span>
                    <span className="pending-comment__feedback">
                      {c.comment?.length > 50 ? c.comment.substring(0, 50) + '...' : c.comment}
                    </span>
                    <button
                      type="button"
                      className="pending-comment__delete"
                      onClick={() => onDeleteComment(c.id)}
                      title="削除"
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          <form className="input-form" onSubmit={handleSubmit}>
            <div className="input-wrapper">
              {attachedFiles.length > 0 && (
                <div className="attached-files">
                  {attachedFiles.map((file, index) => (
                    <div key={index} className="attached-file">
                      <span className="file-name">{file.name}</span>
                      <button
                        type="button"
                        className="remove-file"
                        onClick={() => removeFile(index)}
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
              )}
              <textarea
                className="message-input"
                placeholder="Ask your question... (Shift+Enter for new line, Enter to send)"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={isLoading}
                rows={3}
              />
            </div>
            <div className="input-actions">
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileSelect}
                accept=".md,.txt,.json,.js,.jsx,.ts,.tsx,.py,.html,.css,.yml,.yaml,.xml,.csv,.log"
                multiple
                style={{ display: 'none' }}
              />
              <button
                type="button"
                className="attach-button"
                onClick={() => fileInputRef.current?.click()}
                disabled={isLoading}
                title="Attach files"
              >
                📎
              </button>
              {isLoading ? (
                <button
                  type="button"
                  className="stop-button"
                  onClick={onStopGeneration}
                >
                  Stop
                </button>
              ) : (
                <button
                  type="submit"
                  className="send-button"
                  disabled={!input.trim() && attachedFiles.length === 0}
                >
                  Send
                </button>
              )}
            </div>
          </form>
        </>
      )}

      {/* テキスト選択時のコメントポップアップ（position: fixedなのでどこに配置しても良い） */}
      {hasConversation && selectedText && anchorRect && (
        <TextSelectionCommentPopup
          anchorRect={anchorRect}
          selectedText={selectedText}
          onSubmit={handleCommentSubmit}
          onCancel={handleCommentCancel}
        />
      )}
    </div>
  );
}
