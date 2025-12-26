import { useState, useEffect } from 'react';
import { api, getProjectId, setProjectPassword } from '../api';
import { getTheme, setTheme } from '../theme';
import PasswordDialog from './PasswordDialog';
import './Settings.css';

// カテゴリのラベルマッピング
const CATEGORY_LABELS = {
  personal: '個人情報',
  preference: '好み・スタイル',
  goal: '目標・プロジェクト',
  skill: 'スキル・経験',
  context: '現在の文脈',
};

export default function Settings({ onClose }) {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  // パスワード関連の状態
  const [hasPassword, setHasPassword] = useState(false);
  const [showPasswordDialog, setShowPasswordDialog] = useState(false);
  const [passwordDialogMode, setPasswordDialogMode] = useState('set');
  const currentProjectId = getProjectId();

  // テーマ関連の状態
  const [currentTheme, setCurrentTheme] = useState(getTheme());

  // メモリ関連の状態
  const [memoryTab, setMemoryTab] = useState('memory'); // 'memory' | 'summaries'
  const [memoryData, setMemoryData] = useState(null);
  const [summariesData, setSummariesData] = useState(null);
  const [memoryLoading, setMemoryLoading] = useState(false);
  const [editingMemory, setEditingMemory] = useState(null);
  const [newMemory, setNewMemory] = useState({ category: 'context', key: '', value: '' });
  const [showAddMemory, setShowAddMemory] = useState(false);

  useEffect(() => {
    loadConfig();
    loadAuthStatus();
    loadMemoryData();
  }, []);

  const loadConfig = async () => {
    try {
      setLoading(true);
      const cfg = await api.getConfig();
      setConfig(cfg);
      setError(null);
    } catch (err) {
      setError('Failed to load configuration');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const loadAuthStatus = async () => {
    try {
      const status = await api.getProjectAuthStatus(currentProjectId);
      setHasPassword(status.has_password);
    } catch (err) {
      console.error('Failed to load auth status:', err);
    }
  };

  const handlePasswordDialogSuccess = () => {
    setShowPasswordDialog(false);
    loadAuthStatus();
  };

  // テーマ変更ハンドラ
  const handleThemeChange = (mode) => {
    setTheme(mode);
    setCurrentTheme(mode);
  };

  const saveConfig = async () => {
    try {
      setSaving(true);
      await api.updateConfig(config);
      setError(null);
      onClose();
    } catch (err) {
      setError('Failed to save configuration');
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  const addMember = () => {
    const newId = `member-${Date.now()}`;
    setConfig({
      ...config,
      council_members: [
        ...config.council_members,
        {
          id: newId,
          name: 'New Agent',
          model: 'openai/gpt-4o',
          system_prompt: null,
        },
      ],
    });
  };

  const removeMember = (index) => {
    const members = [...config.council_members];
    members.splice(index, 1);
    setConfig({ ...config, council_members: members });
  };

  const updateMember = (index, field, value) => {
    const members = [...config.council_members];
    members[index] = { ...members[index], [field]: value || null };
    setConfig({ ...config, council_members: members });
  };

  const updateChairman = (field, value) => {
    setConfig({
      ...config,
      chairman: { ...config.chairman, [field]: value || null },
    });
  };

  // メモリ設定を更新
  const updateMemorySettings = (field, value) => {
    const memorySettings = config.memory_settings || {
      enabled: true,
      utility_model: 'deepseek/deepseek-r1-distill-qwen-8b',
      auto_extract: true,
      max_summaries: 15,
      max_history_messages: 10,
    };
    setConfig({
      ...config,
      memory_settings: { ...memorySettings, [field]: value },
    });
  };

  // メモリデータをロード
  const loadMemoryData = async () => {
    setMemoryLoading(true);
    try {
      const [memory, summaries] = await Promise.all([
        api.getMemory().catch(() => ({ entries: [] })),
        api.getSummaries().catch(() => ({ entries: [] })),
      ]);
      setMemoryData(memory);
      setSummariesData(summaries);
    } catch (err) {
      console.error('Failed to load memory data:', err);
    } finally {
      setMemoryLoading(false);
    }
  };

  // メモリエントリを追加
  const handleAddMemory = async () => {
    if (!newMemory.key || !newMemory.value) return;
    try {
      await api.addMemory(newMemory.category, newMemory.key, newMemory.value);
      setNewMemory({ category: 'context', key: '', value: '' });
      setShowAddMemory(false);
      await loadMemoryData();
    } catch (err) {
      setError(err.message);
    }
  };

  // メモリエントリを更新
  const handleUpdateMemory = async () => {
    if (!editingMemory) return;
    try {
      await api.updateMemory(editingMemory.id, {
        category: editingMemory.category,
        key: editingMemory.key,
        value: editingMemory.value,
      });
      setEditingMemory(null);
      await loadMemoryData();
    } catch (err) {
      setError(err.message);
    }
  };

  // メモリエントリを削除
  const handleDeleteMemory = async (memoryId) => {
    if (!confirm('このメモリエントリを削除しますか？')) return;
    try {
      await api.deleteMemory(memoryId);
      await loadMemoryData();
    } catch (err) {
      setError(err.message);
    }
  };

  // 全メモリをクリア
  const handleClearMemory = async () => {
    if (!confirm('全てのメモリを削除しますか？この操作は取り消せません。')) return;
    try {
      await api.clearMemory();
      await loadMemoryData();
    } catch (err) {
      setError(err.message);
    }
  };

  // サマリーを削除
  const handleDeleteSummary = async (conversationId) => {
    if (!confirm('このサマリーを削除しますか？')) return;
    try {
      await api.deleteSummary(conversationId);
      await loadMemoryData();
    } catch (err) {
      setError(err.message);
    }
  };

  // 全サマリーをクリア
  const handleClearSummaries = async () => {
    if (!confirm('全てのサマリーを削除しますか？この操作は取り消せません。')) return;
    try {
      await api.clearSummaries();
      await loadMemoryData();
    } catch (err) {
      setError(err.message);
    }
  };

  if (loading) {
    return (
      <div className="settings-overlay">
        <div className="settings-modal">
          <div className="settings-loading">Loading...</div>
        </div>
      </div>
    );
  }

  if (!config) {
    return (
      <div className="settings-overlay" onClick={onClose}>
        <div className="settings-modal" onClick={(e) => e.stopPropagation()}>
          <div className="settings-header">
            <h2>Council Settings</h2>
            <button className="close-btn" onClick={onClose}>
              &times;
            </button>
          </div>
          <div className="settings-error">
            {error || 'Failed to load configuration. Is the backend running?'}
          </div>
          <div className="settings-footer">
            <button className="cancel-btn" onClick={onClose}>
              Close
            </button>
            <button className="save-btn" onClick={loadConfig}>
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="settings-overlay" onClick={onClose}>
      <div className="settings-modal" onClick={(e) => e.stopPropagation()}>
        <div className="settings-header">
          <h2>Council Settings</h2>
          <button className="close-btn" onClick={onClose}>
            &times;
          </button>
        </div>

        {error && <div className="settings-error">{error}</div>}

        <div className="settings-content">
          <section className="settings-section">
            <div className="section-header">
              <h3>Council Members</h3>
              <button className="add-btn" onClick={addMember}>
                + Add Member
              </button>
            </div>

            <div className="members-list">
              {config.council_members.map((member, index) => (
                <div key={member.id} className="member-card">
                  <div className="member-header">
                    <span className="member-index">#{index + 1}</span>
                    <button
                      className="remove-btn"
                      onClick={() => removeMember(index)}
                      disabled={config.council_members.length <= 1}
                    >
                      Remove
                    </button>
                  </div>

                  <div className="form-group">
                    <label>ID</label>
                    <input
                      type="text"
                      value={member.id}
                      onChange={(e) => updateMember(index, 'id', e.target.value)}
                      placeholder="unique-id"
                    />
                  </div>

                  <div className="form-group">
                    <label>Display Name</label>
                    <input
                      type="text"
                      value={member.name || ''}
                      onChange={(e) => updateMember(index, 'name', e.target.value)}
                      placeholder="Display name"
                    />
                  </div>

                  <div className="form-group">
                    <label>Model</label>
                    <input
                      type="text"
                      value={member.model}
                      onChange={(e) => updateMember(index, 'model', e.target.value)}
                      placeholder="e.g., openai/gpt-4o"
                    />
                  </div>

                  <div className="form-group">
                    <label>System Prompt (optional)</label>
                    <textarea
                      value={member.system_prompt || ''}
                      onChange={(e) =>
                        updateMember(index, 'system_prompt', e.target.value)
                      }
                      placeholder="Custom instructions for this agent..."
                      rows={3}
                    />
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="settings-section">
            <h3>Chairman</h3>
            <p className="section-description">
              The chairman synthesizes all responses into a final answer.
            </p>

            <div className="chairman-card">
              <div className="form-group">
                <label>Display Name</label>
                <input
                  type="text"
                  value={config.chairman.name || ''}
                  onChange={(e) => updateChairman('name', e.target.value)}
                  placeholder="Chairman"
                />
              </div>

              <div className="form-group">
                <label>Model</label>
                <input
                  type="text"
                  value={config.chairman.model}
                  onChange={(e) => updateChairman('model', e.target.value)}
                  placeholder="e.g., openai/gpt-4o"
                />
              </div>

              <div className="form-group">
                <label>System Prompt (optional)</label>
                <textarea
                  value={config.chairman.system_prompt || ''}
                  onChange={(e) => updateChairman('system_prompt', e.target.value)}
                  placeholder="Custom instructions for the chairman..."
                  rows={3}
                />
              </div>
            </div>
          </section>

          <section className="settings-section">
            <h3>Security</h3>
            <p className="section-description">
              プロジェクト「{currentProjectId}」のパスワード設定
            </p>

            <div className="security-card">
              {hasPassword ? (
                <>
                  <p className="security-status">
                    このプロジェクトはパスワードで保護されています。
                  </p>
                  <div className="security-buttons">
                    <button
                      className="security-btn"
                      onClick={() => {
                        setPasswordDialogMode('change');
                        setShowPasswordDialog(true);
                      }}
                    >
                      パスワードを変更
                    </button>
                    <button
                      className="security-btn danger"
                      onClick={() => {
                        setPasswordDialogMode('remove');
                        setShowPasswordDialog(true);
                      }}
                    >
                      パスワードを削除
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <p className="security-status">
                    このプロジェクトにはパスワードが設定されていません。
                  </p>
                  <div className="security-buttons">
                    <button
                      className="security-btn"
                      onClick={() => {
                        setPasswordDialogMode('set');
                        setShowPasswordDialog(true);
                      }}
                    >
                      パスワードを設定
                    </button>
                  </div>
                </>
              )}
            </div>
          </section>

          {/* テーマセクション */}
          <section className="settings-section">
            <h3>Appearance</h3>
            <p className="section-description">
              アプリケーションの外観をカスタマイズします
            </p>

            <div className="theme-card">
              <div className="theme-options">
                <label className="theme-option">
                  <input
                    type="radio"
                    name="theme"
                    value="light"
                    checked={currentTheme === 'light'}
                    onChange={() => handleThemeChange('light')}
                  />
                  <span>ライト</span>
                </label>
                <label className="theme-option">
                  <input
                    type="radio"
                    name="theme"
                    value="dark"
                    checked={currentTheme === 'dark'}
                    onChange={() => handleThemeChange('dark')}
                  />
                  <span>ダーク</span>
                </label>
                <label className="theme-option">
                  <input
                    type="radio"
                    name="theme"
                    value="auto"
                    checked={currentTheme === 'auto'}
                    onChange={() => handleThemeChange('auto')}
                  />
                  <span>自動（システム設定）</span>
                </label>
              </div>
            </div>
          </section>

          {/* メモリセクション */}
          <section className="settings-section">
            <h3>Memory</h3>
            <p className="section-description">
              会話からユーザー情報を自動抽出し、パーソナライズに活用します
            </p>

            {/* メモリ設定 */}
            <div className="memory-settings-card">
              <div className="form-row">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={config.memory_settings?.enabled !== false}
                    onChange={(e) => updateMemorySettings('enabled', e.target.checked)}
                  />
                  メモリ機能を有効化
                </label>
              </div>

              <div className="form-row">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={config.memory_settings?.auto_extract !== false}
                    onChange={(e) => updateMemorySettings('auto_extract', e.target.checked)}
                  />
                  会話から自動抽出
                </label>
              </div>

              <div className="form-group">
                <label>ユーティリティモデル（メモリ抽出・サマリー生成用）</label>
                <input
                  type="text"
                  value={config.memory_settings?.utility_model || 'deepseek/deepseek-r1-distill-qwen-8b'}
                  onChange={(e) => updateMemorySettings('utility_model', e.target.value)}
                  placeholder="deepseek/deepseek-r1-distill-qwen-8b"
                />
              </div>

              <div className="form-row-inline">
                <div className="form-group small">
                  <label>最大サマリー数</label>
                  <input
                    type="number"
                    min="1"
                    max="50"
                    value={config.memory_settings?.max_summaries || 15}
                    onChange={(e) => updateMemorySettings('max_summaries', parseInt(e.target.value) || 15)}
                  />
                </div>
                <div className="form-group small">
                  <label>会話履歴の最大メッセージ数</label>
                  <input
                    type="number"
                    min="1"
                    max="100"
                    value={config.memory_settings?.max_history_messages || 10}
                    onChange={(e) => updateMemorySettings('max_history_messages', parseInt(e.target.value) || 10)}
                  />
                </div>
              </div>
            </div>

            {/* メモリ/サマリータブ */}
            <div className="memory-tabs">
              <button
                className={`memory-tab ${memoryTab === 'memory' ? 'active' : ''}`}
                onClick={() => setMemoryTab('memory')}
              >
                ユーザーメモリ ({memoryData?.entries?.length || 0})
              </button>
              <button
                className={`memory-tab ${memoryTab === 'summaries' ? 'active' : ''}`}
                onClick={() => setMemoryTab('summaries')}
              >
                会話サマリー ({summariesData?.entries?.length || 0})
              </button>
            </div>

            {memoryLoading ? (
              <div className="memory-loading">読み込み中...</div>
            ) : memoryTab === 'memory' ? (
              <div className="memory-content">
                <div className="memory-header">
                  <button className="add-btn small" onClick={() => setShowAddMemory(true)}>
                    + 手動追加
                  </button>
                  <button
                    className="danger-btn small"
                    onClick={handleClearMemory}
                    disabled={!memoryData?.entries?.length}
                  >
                    全削除
                  </button>
                </div>

                {showAddMemory && (
                  <div className="memory-add-form">
                    <select
                      value={newMemory.category}
                      onChange={(e) => setNewMemory({ ...newMemory, category: e.target.value })}
                    >
                      {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
                        <option key={key} value={key}>{label}</option>
                      ))}
                    </select>
                    <input
                      type="text"
                      placeholder="キー（例：名前）"
                      value={newMemory.key}
                      onChange={(e) => setNewMemory({ ...newMemory, key: e.target.value })}
                    />
                    <input
                      type="text"
                      placeholder="値"
                      value={newMemory.value}
                      onChange={(e) => setNewMemory({ ...newMemory, value: e.target.value })}
                    />
                    <button className="save-btn small" onClick={handleAddMemory}>追加</button>
                    <button className="cancel-btn small" onClick={() => setShowAddMemory(false)}>キャンセル</button>
                  </div>
                )}

                {memoryData?.entries?.length === 0 ? (
                  <div className="memory-empty">メモリがありません</div>
                ) : (
                  <div className="memory-list">
                    {memoryData?.entries?.map((entry) => (
                      <div key={entry.id} className="memory-entry">
                        {editingMemory?.id === entry.id ? (
                          <div className="memory-edit-form">
                            <select
                              value={editingMemory.category}
                              onChange={(e) => setEditingMemory({ ...editingMemory, category: e.target.value })}
                            >
                              {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
                                <option key={key} value={key}>{label}</option>
                              ))}
                            </select>
                            <input
                              type="text"
                              value={editingMemory.key}
                              onChange={(e) => setEditingMemory({ ...editingMemory, key: e.target.value })}
                            />
                            <input
                              type="text"
                              value={editingMemory.value}
                              onChange={(e) => setEditingMemory({ ...editingMemory, value: e.target.value })}
                            />
                            <button className="save-btn small" onClick={handleUpdateMemory}>保存</button>
                            <button className="cancel-btn small" onClick={() => setEditingMemory(null)}>キャンセル</button>
                          </div>
                        ) : (
                          <>
                            <span className="memory-category">{CATEGORY_LABELS[entry.category] || entry.category}</span>
                            <span className="memory-key">{entry.key}</span>
                            <span className="memory-value">{entry.value}</span>
                            <div className="memory-actions">
                              <button className="edit-btn" onClick={() => setEditingMemory({ ...entry })}>編集</button>
                              <button className="delete-btn" onClick={() => handleDeleteMemory(entry.id)}>削除</button>
                            </div>
                          </>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="memory-content">
                <div className="memory-header">
                  <button
                    className="danger-btn small"
                    onClick={handleClearSummaries}
                    disabled={!summariesData?.entries?.length}
                  >
                    全削除
                  </button>
                </div>

                {summariesData?.entries?.length === 0 ? (
                  <div className="memory-empty">サマリーがありません</div>
                ) : (
                  <div className="summaries-list">
                    {summariesData?.entries?.map((summary) => (
                      <div key={summary.conversation_id} className="summary-entry">
                        <div className="summary-header">
                          <span className="summary-title">{summary.title}</span>
                          <button
                            className="delete-btn"
                            onClick={() => handleDeleteSummary(summary.conversation_id)}
                          >
                            削除
                          </button>
                        </div>
                        <p className="summary-text">{summary.summary}</p>
                        {summary.key_topics?.length > 0 && (
                          <div className="summary-topics">
                            {summary.key_topics.map((topic, i) => (
                              <span key={i} className="topic-tag">{topic}</span>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </section>

          {/* ツールセクション */}
          <section className="settings-section">
            <h3>Tools</h3>
            <p className="section-description">
              Council メンバーが使用できるツールを設定します
            </p>

            <div className="tools-card">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={config.tools_enabled || false}
                  onChange={(e) => setConfig({ ...config, tools_enabled: e.target.checked })}
                />
                Web検索を有効化
              </label>
              <p className="tools-hint">
                有効にすると、Council メンバーがインターネット検索を行い、最新情報を取得できます。
                バックエンドに TAVILY_API_KEY の設定が必要です（月1000回無料）。
              </p>
            </div>
          </section>
        </div>

        <div className="settings-footer">
          <button className="cancel-btn" onClick={onClose}>
            Cancel
          </button>
          <button className="save-btn" onClick={saveConfig} disabled={saving}>
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>

        {showPasswordDialog && (
          <PasswordDialog
            projectId={currentProjectId}
            mode={passwordDialogMode}
            onSuccess={handlePasswordDialogSuccess}
            onCancel={() => setShowPasswordDialog(false)}
          />
        )}
      </div>
    </div>
  );
}
