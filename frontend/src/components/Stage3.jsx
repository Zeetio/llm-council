import { memo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './Stage3.css';

// メモ化してpropsが変わらない限り再レンダーしない
export default memo(function Stage3({ finalResponse }) {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [copySuccess, setCopySuccess] = useState(false);

  if (!finalResponse) {
    return null;
  }

  // コピー機能
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(finalResponse.response);
      setCopySuccess(true);
      setTimeout(() => setCopySuccess(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  return (
    <div className="stage stage3">
      <div className="stage-header">
        <h3 className="stage-title" onClick={() => setIsCollapsed(!isCollapsed)} style={{ cursor: 'pointer' }}>
          <span className="collapse-icon">{isCollapsed ? '▶' : '▼'}</span>
          Stage 3: Final Council Answer
        </h3>
        <button
          className="copy-button"
          onClick={handleCopy}
          title="回答をコピー"
        >
          {copySuccess ? '✓ コピー済み' : '📋 コピー'}
        </button>
      </div>
      {!isCollapsed && (
        <div className="final-response">
          <div className="chairman-label">
            Chairman: {finalResponse.model.split('/')[1] || finalResponse.model}
          </div>
          <div className="final-text markdown-content">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {finalResponse.response}
            </ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  );
});
