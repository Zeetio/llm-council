import { useState } from 'react';
import { api, setProjectPassword as saveProjectPassword, clearProjectPassword } from '../api';
import './PasswordDialog.css';

/**
 * パスワード入力ダイアログ
 *
 * @param {Object} props
 * @param {string} props.projectId - 対象プロジェクトID
 * @param {'verify'|'set'|'change'|'remove'} props.mode - ダイアログモード
 * @param {function} props.onSuccess - 成功時コールバック
 * @param {function} props.onCancel - キャンセル時コールバック
 */
export default function PasswordDialog({
  projectId,
  mode,
  onSuccess,
  onCancel,
}) {
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [currentPassword, setCurrentPassword] = useState('');
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  // モードに応じたタイトル
  const titles = {
    verify: 'パスワードを入力',
    set: 'パスワードを設定',
    change: 'パスワードを変更',
    remove: 'パスワードを削除',
  };

  // モードに応じた説明
  const descriptions = {
    verify: `プロジェクト「${projectId}」はパスワードで保護されています。`,
    set: 'このプロジェクトにパスワードを設定します。忘れた場合は復旧できません。',
    change: '現在のパスワードを入力し、新しいパスワードを設定してください。',
    remove: 'パスワードを削除するには、現在のパスワードを入力してください。',
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (mode === 'verify') {
        // パスワード検証
        const result = await api.verifyProjectPassword(projectId, password);
        if (result.valid) {
          // 認証成功時にパスワードをセッションに保存
          saveProjectPassword(password);
          onSuccess();
        } else {
          setError('パスワードが正しくありません');
        }
      } else if (mode === 'set') {
        // 新規パスワード設定
        if (password !== confirmPassword) {
          setError('パスワードが一致しません');
          setLoading(false);
          return;
        }
        if (password.length < 1) {
          setError('パスワードを入力してください');
          setLoading(false);
          return;
        }
        await api.setProjectPassword(projectId, password);
        // 設定成功時にパスワードをセッションに保存
        saveProjectPassword(password);
        onSuccess();
      } else if (mode === 'change') {
        // パスワード変更
        if (password !== confirmPassword) {
          setError('新しいパスワードが一致しません');
          setLoading(false);
          return;
        }
        if (password.length < 1) {
          setError('新しいパスワードを入力してください');
          setLoading(false);
          return;
        }
        await api.setProjectPassword(projectId, password, currentPassword);
        // 変更成功時に新しいパスワードをセッションに保存
        saveProjectPassword(password);
        onSuccess();
      } else if (mode === 'remove') {
        // パスワード削除
        await api.removeProjectPassword(projectId, currentPassword);
        // 削除成功時にセッションのパスワードをクリア
        clearProjectPassword();
        onSuccess();
      }
    } catch (err) {
      setError(err.message || 'エラーが発生しました');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="password-overlay" onClick={onCancel}>
      <div className="password-modal" onClick={(e) => e.stopPropagation()}>
        <div className="password-header">
          <h2>{titles[mode]}</h2>
          <button className="close-btn" onClick={onCancel}>
            &times;
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="password-content">
            <p className="password-description">{descriptions[mode]}</p>

            {error && <div className="password-error">{error}</div>}

            {/* 現在のパスワード（変更/削除時） */}
            {(mode === 'change' || mode === 'remove') && (
              <div className="form-group">
                <label htmlFor="current-password">現在のパスワード</label>
                <input
                  id="current-password"
                  type="password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  autoFocus
                  disabled={loading}
                />
              </div>
            )}

            {/* パスワード入力（検証/設定/変更時） */}
            {(mode === 'verify' || mode === 'set' || mode === 'change') && (
              <div className="form-group">
                <label htmlFor="password">
                  {mode === 'verify' ? 'パスワード' : mode === 'change' ? '新しいパスワード' : 'パスワード'}
                </label>
                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoFocus={mode === 'verify' || mode === 'set'}
                  disabled={loading}
                />
              </div>
            )}

            {/* パスワード確認（設定/変更時） */}
            {(mode === 'set' || mode === 'change') && (
              <div className="form-group">
                <label htmlFor="confirm-password">パスワード確認</label>
                <input
                  id="confirm-password"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  disabled={loading}
                />
              </div>
            )}

            {/* 警告メッセージ */}
            {mode === 'set' && (
              <div className="password-warning">
                パスワードを忘れた場合、このプロジェクトにはアクセスできなくなります。
              </div>
            )}
          </div>

          <div className="password-footer">
            <button type="button" className="cancel-btn" onClick={onCancel} disabled={loading}>
              キャンセル
            </button>
            <button type="submit" className="submit-btn" disabled={loading}>
              {loading ? '処理中...' : mode === 'remove' ? '削除' : mode === 'verify' ? '確認' : '設定'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
