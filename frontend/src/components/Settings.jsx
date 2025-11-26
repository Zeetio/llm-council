import { useState, useEffect } from 'react';
import { api } from '../api';
import './Settings.css';

export default function Settings({ onClose }) {
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    loadConfig();
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
        </div>

        <div className="settings-footer">
          <button className="cancel-btn" onClick={onClose}>
            Cancel
          </button>
          <button className="save-btn" onClick={saveConfig} disabled={saving}>
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>
  );
}
