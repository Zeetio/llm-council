import { useState, useMemo, memo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './Stage2.css';

// メモ化してpropsが変わらない限り再レンダーしない

// Build a mapping from member id to model name using stage1 results
function buildIdToModel(stage1Results) {
  if (!stage1Results) return {};
  const map = {};
  stage1Results.forEach((result) => {
    map[result.id] = result.model;
  });
  return map;
}

// Build labelToModel mapping from labelToId + stage1Results
function buildLabelToModel(labelToId, stage1Results) {
  if (!labelToId || !stage1Results) return null;
  const idToModel = buildIdToModel(stage1Results);
  const labelToModel = {};
  Object.entries(labelToId).forEach(([label, id]) => {
    labelToModel[label] = idToModel[id] || id;
  });
  return labelToModel;
}

function deAnonymizeText(text, labelToModel) {
  if (!labelToModel) return text;

  let result = text;
  // Replace each "Response X" with the actual model name
  Object.entries(labelToModel).forEach(([label, model]) => {
    const modelShortName = model.split('/')[1] || model;
    result = result.replace(new RegExp(label, 'g'), `**${modelShortName}**`);
  });
  return result;
}

export default memo(function Stage2({ rankings, labelToId, aggregateRankings, stage1Results }) {
  const [activeTab, setActiveTab] = useState(0);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [copySuccess, setCopySuccess] = useState(false);

  // Build labelToModel from labelToId + stage1Results
  const labelToModel = useMemo(
    () => buildLabelToModel(labelToId, stage1Results),
    [labelToId, stage1Results]
  );

  // Build idToModel for aggregate rankings display
  const idToModel = useMemo(
    () => buildIdToModel(stage1Results),
    [stage1Results]
  );

  if (!rankings || rankings.length === 0) {
    return null;
  }

  // コピー機能（現在アクティブなタブのランキングをコピー）
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(rankings[activeTab].ranking);
      setCopySuccess(true);
      setTimeout(() => setCopySuccess(false), 2000);
    } catch (err) {
      console.error('Failed to copy:', err);
    }
  };

  return (
    <div className="stage stage2">
      <div className="stage-header">
        <h3 className="stage-title" onClick={() => setIsCollapsed(!isCollapsed)} style={{ cursor: 'pointer' }}>
          <span className="collapse-icon">{isCollapsed ? '▶' : '▼'}</span>
          Stage 2: Peer Rankings
        </h3>
        <button
          className="copy-button"
          onClick={handleCopy}
          title="ランキングをコピー"
        >
          {copySuccess ? '✓ コピー済み' : '📋 コピー'}
        </button>
      </div>

      {!isCollapsed && (
        <>
          <h4>Raw Evaluations</h4>
          <p className="stage-description">
            Each model evaluated all responses (anonymized as Response A, B, C, etc.) and provided rankings.
            Below, model names are shown in <strong>bold</strong> for readability, but the original evaluation used anonymous labels.
          </p>

          <div className="tabs">
            {rankings.map((rank, index) => (
              <button
                key={index}
                className={`tab ${activeTab === index ? 'active' : ''}`}
                onClick={() => setActiveTab(index)}
              >
                {rank.model.split('/')[1] || rank.model}
              </button>
            ))}
          </div>

          <div className="tab-content">
            <div className="ranking-model">
              {rankings[activeTab].model}
            </div>
            <div className="ranking-content markdown-content">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {deAnonymizeText(rankings[activeTab].ranking, labelToModel)}
              </ReactMarkdown>
            </div>

            {rankings[activeTab].parsed_ranking &&
             rankings[activeTab].parsed_ranking.length > 0 && (
              <div className="parsed-ranking">
                <strong>Extracted Ranking:</strong>
                <ol>
                  {rankings[activeTab].parsed_ranking.map((label, i) => (
                    <li key={i}>
                      {labelToModel && labelToModel[label]
                        ? labelToModel[label].split('/')[1] || labelToModel[label]
                        : label}
                    </li>
                  ))}
                </ol>
              </div>
            )}
          </div>

          {aggregateRankings && aggregateRankings.length > 0 && (
            <div className="aggregate-rankings">
              <h4>Aggregate Rankings (Street Cred)</h4>
              <p className="stage-description">
                Combined results across all peer evaluations (lower score is better):
              </p>
              <div className="aggregate-list">
                {aggregateRankings.map((agg, index) => {
                  const model = idToModel[agg.id] || agg.id;
                  const modelShortName = model.split('/')[1] || model;
                  return (
                    <div key={index} className="aggregate-item">
                      <span className="rank-position">#{index + 1}</span>
                      <span className="rank-model">{modelShortName}</span>
                      <span className="rank-score">
                        Avg: {agg.average_rank.toFixed(2)}
                      </span>
                      <span className="rank-count">
                        ({agg.rankings_count} votes)
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
});
