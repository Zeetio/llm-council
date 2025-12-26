import { useState } from 'react';
import './UsageStats.css';

/**
 * LLM使用量統計を表示するコンポーネント
 *
 * @param {Object} props
 * @param {Object} props.usage - 使用量データ（complete イベントから取得）
 */
export default function UsageStats({ usage }) {
  const [expanded, setExpanded] = useState(false);

  // 使用量データがない場合は何も表示しない
  if (!usage || usage.total_calls === 0) return null;

  // ステージ名を日本語に変換
  const stageNames = {
    stage1: 'Stage 1 (回答収集)',
    stage2: 'Stage 2 (ランキング)',
    stage3: 'Stage 3 (統合)',
  };

  return (
    <div className="usage-stats">
      <div className="usage-stats__header" onClick={() => setExpanded(!expanded)}>
        <span className="usage-stats__icon">📊</span>
        <span className="usage-stats__title">使用量</span>
        <span className="usage-stats__toggle">{expanded ? '▼' : '▶'}</span>
      </div>

      <div className="usage-stats__summary">
        <div className="usage-stats__item">
          <span className="usage-stats__label">呼び出し</span>
          <span className="usage-stats__value">{usage.total_calls}回</span>
        </div>
        <div className="usage-stats__item">
          <span className="usage-stats__label">トークン</span>
          <span className="usage-stats__value">{usage.total_tokens?.toLocaleString() || 0}</span>
        </div>
        <div className="usage-stats__item">
          <span className="usage-stats__label">コスト</span>
          <span className="usage-stats__value">${usage.total_cost_usd?.toFixed(4) || '0.0000'}</span>
        </div>
        <div className="usage-stats__item">
          <span className="usage-stats__label">平均応答</span>
          <span className="usage-stats__value">{usage.average_response_time_ms || 0}ms</span>
        </div>
      </div>

      {/* ツール使用サマリー */}
      {usage.tool_calls && usage.tool_calls.length > 0 && (
        <div className="usage-stats__tools-summary">
          <span className="usage-stats__tools-icon">🔧</span>
          <span>ツール使用: {usage.tool_calls.length}回</span>
        </div>
      )}

      {expanded && (
        <div className="usage-stats__details">
          {/* ステージ別内訳 */}
          {usage.by_stage && Object.keys(usage.by_stage).length > 0 && (
            <div className="usage-stats__section">
              <h4 className="usage-stats__section-title">ステージ別</h4>
              <table className="usage-stats__table">
                <thead>
                  <tr>
                    <th>ステージ</th>
                    <th>呼び出し</th>
                    <th>トークン</th>
                    <th>コスト</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(usage.by_stage).map(([stage, data]) => (
                    <tr key={stage}>
                      <td>{stageNames[stage] || stage}</td>
                      <td>{data.calls}</td>
                      <td>{data.tokens?.toLocaleString()}</td>
                      <td>${data.cost_usd?.toFixed(4)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* モデル別内訳 */}
          {usage.by_model && Object.keys(usage.by_model).length > 0 && (
            <div className="usage-stats__section">
              <h4 className="usage-stats__section-title">モデル別</h4>
              <table className="usage-stats__table">
                <thead>
                  <tr>
                    <th>モデル</th>
                    <th>呼び出し</th>
                    <th>トークン</th>
                    <th>コスト</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(usage.by_model).map(([model, data]) => (
                    <tr key={model}>
                      <td className="usage-stats__model-name">{model.split('/')[1] || model}</td>
                      <td>{data.calls}</td>
                      <td>{data.tokens?.toLocaleString()}</td>
                      <td>${data.cost_usd?.toFixed(4)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* ツール実行詳細 */}
          {usage.tool_calls && usage.tool_calls.length > 0 && (
            <div className="usage-stats__section">
              <h4 className="usage-stats__section-title">ツール実行</h4>
              <ul className="usage-stats__tool-list">
                {usage.tool_calls.map((call, i) => (
                  <li key={i} className="usage-stats__tool-item">
                    <code className="usage-stats__tool-name">{call.tool_name}</code>
                    <span className="usage-stats__tool-args">
                      {JSON.stringify(call.arguments).substring(0, 60)}
                      {JSON.stringify(call.arguments).length > 60 ? '...' : ''}
                    </span>
                    <span className="usage-stats__tool-result">
                      {call.result_count > 0 && `${call.result_count}件`}
                      {call.execution_time_ms && ` · ${call.execution_time_ms}ms`}
                    </span>
                    {!call.success && (
                      <span className="usage-stats__tool-error">エラー</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
