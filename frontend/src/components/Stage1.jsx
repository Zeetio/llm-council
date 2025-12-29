import { useState, memo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './Stage1.css';

// メモ化してpropsが変わらない限り再レンダーしない
export default memo(function Stage1({ responses }) {
  const [activeTab, setActiveTab] = useState(0);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [copySuccess, setCopySuccess] = useState(false);

  if (!responses || responses.length === 0) {
    return null;
  }

  // コピー機能（現在アクティブなタブの回答をコピー）
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(responses[activeTab].response);
      setCopySuccess(true);
      setTimeout(() => setCopySuccess(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  return (
    <div className="stage stage1">
      <div className="stage-header">
        <h3 className="stage-title" onClick={() => setIsCollapsed(!isCollapsed)} style={{ cursor: 'pointer' }}>
          <span className="collapse-icon">{isCollapsed ? '▶' : '▼'}</span>
          Stage 1: Individual Responses
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
        <>
          <div className="tabs">
            {responses.map((resp, index) => (
              <button
                key={index}
                className={`tab ${activeTab === index ? 'active' : ''}`}
                onClick={() => setActiveTab(index)}
              >
                {resp.model.split('/')[1] || resp.model}
              </button>
            ))}
          </div>

          <div className="tab-content">
            <div className="model-name">{responses[activeTab].model}</div>
            <div className="response-text markdown-content">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {responses[activeTab].response}
              </ReactMarkdown>
            </div>
          </div>
        </>
      )}
    </div>
  );
});
