/**
 * API client for the LLM Council backend.
 */

// Use VITE_API_BASE env var for local dev, empty string for same-origin (Cloud Run)
const API_BASE = import.meta.env.VITE_API_BASE || '';

let projectId = localStorage.getItem('project_id') || 'default';
// 認証済みプロジェクトのパスワードを一時保存（セッション内）
let projectPassword = null;

// =========================================================================
// アクティブジョブの永続化（モバイルバックグラウンド/ページリロード対策）
// =========================================================================
const ACTIVE_JOB_KEY = 'llm_council_active_job';

/**
 * アクティブジョブ情報をlocalStorageに保存
 * モバイルでバックグラウンドに移行したりページがリロードされても
 * ジョブの追跡を再開できるようにする
 */
export function saveActiveJob(jobId, conversationId, projectId) {
  try {
    localStorage.setItem(ACTIVE_JOB_KEY, JSON.stringify({
      jobId,
      conversationId,
      projectId,
      startedAt: Date.now(),
    }));
  } catch (e) {
    console.warn('Failed to save active job to localStorage:', e);
  }
}

/**
 * アクティブジョブ情報をlocalStorageから取得
 */
export function getActiveJob() {
  try {
    const data = localStorage.getItem(ACTIVE_JOB_KEY);
    if (!data) return null;
    const parsed = JSON.parse(data);
    // 10分以上前のジョブは無視（タイムアウト相当）
    if (Date.now() - parsed.startedAt > 600000) {
      clearActiveJob();
      return null;
    }
    return parsed;
  } catch (e) {
    console.warn('Failed to read active job from localStorage:', e);
    return null;
  }
}

/**
 * アクティブジョブ情報をクリア（完了/失敗時に呼ぶ）
 */
export function clearActiveJob() {
  try {
    localStorage.removeItem(ACTIVE_JOB_KEY);
  } catch (e) {
    console.warn('Failed to clear active job from localStorage:', e);
  }
}

export function setProjectId(id, options = {}) {
  projectId = id || 'default';
  localStorage.setItem('project_id', projectId);
  // プロジェクト変更時にパスワードをクリア（必要な場合のみ）
  if (!options.preservePassword) {
    projectPassword = null;
  }
}

export function getProjectId() {
  return projectId;
}

/**
 * 認証済みパスワードを設定（セッション内でのみ有効）
 */
export function setProjectPassword(password) {
  projectPassword = password;
}

/**
 * 認証済みパスワードをクリア
 */
export function clearProjectPassword() {
  projectPassword = null;
}

function withProject(url) {
  const sep = url.includes('?') ? '&' : '?';
  return `${url}${sep}project_id=${encodeURIComponent(projectId)}`;
}

/**
 * 認証ヘッダーを含むヘッダーオブジェクトを生成
 */
function getAuthHeaders(contentType = 'application/json') {
  const headers = {};
  if (contentType) {
    headers['Content-Type'] = contentType;
  }
  if (projectPassword) {
    headers['X-Project-Password'] = projectPassword;
  }
  return headers;
}

/**
 * セッションメタデータを収集
 */
export function collectSessionMetadata() {
  return {
    device: /Mobile|Android|iPhone|iPad/.test(navigator.userAgent) ? 'Mobile' : 'Desktop',
    os: navigator.platform || navigator.userAgentData?.platform || 'Unknown',
    browser: getBrowserName(),
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    language: navigator.language,
  };
}

/**
 * ブラウザ名を取得
 */
function getBrowserName() {
  const ua = navigator.userAgent;
  if (ua.includes('Firefox')) return 'Firefox';
  if (ua.includes('Chrome')) return 'Chrome';
  if (ua.includes('Safari')) return 'Safari';
  if (ua.includes('Edge')) return 'Edge';
  return 'Unknown';
}

export const api = {
  /**
   * List all conversations.
   */
  async listConversations() {
    const response = await fetch(withProject(`${API_BASE}/api/conversations`));
    if (!response.ok) {
      throw new Error('Failed to list conversations');
    }
    return response.json();
  },

  /**
   * Create a new conversation.
   */
  async createConversation() {
    const response = await fetch(withProject(`${API_BASE}/api/conversations`), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({}),
    });
    if (!response.ok) {
      throw new Error('Failed to create conversation');
    }
    return response.json();
  },

  /**
   * Get a specific conversation.
   */
  async getConversation(conversationId) {
    const response = await fetch(
      withProject(`${API_BASE}/api/conversations/${conversationId}`)
    );
    if (!response.ok) {
      throw new Error('Failed to get conversation');
    }
    return response.json();
  },

  /**
   * 会話を削除
   */
  async deleteConversation(conversationId) {
    const response = await fetch(
      withProject(`${API_BASE}/api/conversations/${conversationId}`),
      { method: 'DELETE' }
    );
    if (!response.ok) {
      throw new Error('Failed to delete conversation');
    }
    return response.json();
  },

  /**
   * Send a message in a conversation.
   */
  async sendMessage(conversationId, content) {
    const response = await fetch(
      withProject(`${API_BASE}/api/conversations/${conversationId}/message`),
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content }),
      }
    );
    if (!response.ok) {
      throw new Error('Failed to send message');
    }
    return response.json();
  },

  /**
   * Get council configuration.
   */
  async getConfig() {
    const response = await fetch(withProject(`${API_BASE}/api/config`));
    if (!response.ok) {
      throw new Error('Failed to get config');
    }
    return response.json();
  },

  /**
   * Update council configuration.
   * パスワード保護プロジェクトでは認証ヘッダーが必要
   */
  async updateConfig(config) {
    const response = await fetch(withProject(`${API_BASE}/api/config`), {
      method: 'PUT',
      headers: getAuthHeaders(),
      body: JSON.stringify(config),
    });
    if (response.status === 401) {
      throw new Error('認証が必要です');
    }
    if (!response.ok) {
      throw new Error('Failed to update config');
    }
    return response.json();
  },

  /**
   * List projects.
   */
  async listProjects() {
    const response = await fetch(`${API_BASE}/api/projects`);
    if (!response.ok) {
      throw new Error('Failed to list projects');
    }
    return response.json();
  },

  /**
   * Create a new project.
   */
  async createProject(projectId) {
    const response = await fetch(`${API_BASE}/api/projects`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ project_id: projectId }),
    });
    if (!response.ok) {
      throw new Error('Failed to create project');
    }
    return response.json();
  },

  /**
   * Delete a project.
   */
  async deleteProject(id) {
    const response = await fetch(`${API_BASE}/api/projects/${encodeURIComponent(id)}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      throw new Error('Failed to delete project');
    }
    return response.json();
  },

  // ==========================================================================
  // プロジェクト認証API
  // ==========================================================================

  /**
   * プロジェクトの認証状態を取得
   */
  async getProjectAuthStatus(targetProjectId) {
    const response = await fetch(
      `${API_BASE}/api/projects/${encodeURIComponent(targetProjectId)}/auth/status`
    );
    if (!response.ok) {
      throw new Error('Failed to get auth status');
    }
    return response.json();
  },

  /**
   * プロジェクトのパスワードを検証
   */
  async verifyProjectPassword(targetProjectId, password) {
    const response = await fetch(
      `${API_BASE}/api/projects/${encodeURIComponent(targetProjectId)}/auth/verify`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      }
    );
    if (response.status === 401) {
      return { valid: false, error: 'Invalid password' };
    }
    if (!response.ok) {
      throw new Error('Failed to verify password');
    }
    return response.json();
  },

  /**
   * プロジェクトのパスワードを設定
   */
  async setProjectPassword(targetProjectId, password, currentPassword = null) {
    const response = await fetch(
      `${API_BASE}/api/projects/${encodeURIComponent(targetProjectId)}/auth/set`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password, current_password: currentPassword }),
      }
    );
    if (!response.ok) {
      const data = await response.json();
      throw new Error(data.detail || 'Failed to set password');
    }
    return response.json();
  },

  /**
   * プロジェクトのパスワードを削除
   */
  async removeProjectPassword(targetProjectId, password) {
    const response = await fetch(
      `${API_BASE}/api/projects/${encodeURIComponent(targetProjectId)}/auth`,
      {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      }
    );
    if (!response.ok) {
      throw new Error('Failed to remove password');
    }
    return response.json();
  },

  /**
   * Send a message and receive streaming updates.
   * @param {string} conversationId - The conversation ID
   * @param {string} content - The message content
   * @param {Array} userComments - ユーザーコメント（フィードバック）の配列
   * @param {function} onEvent - Callback function for each event: (eventType, data) => void
   * @returns {Promise<void>}
   */
  async sendMessageStream(conversationId, content, userComments, onEvent, abortSignal) {
    // セッションメタデータを収集して送信
    const sessionMetadata = collectSessionMetadata();

    const response = await fetch(
      withProject(`${API_BASE}/api/conversations/${conversationId}/message/stream`),
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          content,
          user_comments: userComments || [],
          session_metadata: sessionMetadata,
        }),
        signal: abortSignal, // AbortController対応
      }
    );

    if (!response.ok) {
      throw new Error('Failed to send message');
    }

    const reader = response.body.getReader();
    // stream: true でマルチバイト文字の分断を正しく処理
    const decoder = new TextDecoder('utf-8', { stream: true });
    // 不完全なSSEイベントを保持するバッファ
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          // ストリーム終了時、バッファに残ったデータがあれば警告
          if (buffer.trim()) {
            console.warn('SSE stream ended with incomplete data in buffer:', buffer);
          }
          break;
        }

        // チャンクをデコードしてバッファに追加
        buffer += decoder.decode(value, { stream: true });

        // SSEイベントは '\n\n' で区切られる
        // バッファから完全なイベントを抽出して処理
        let eventEndIndex;
        while ((eventEndIndex = buffer.indexOf('\n\n')) !== -1) {
          // 完全なイベント部分を取り出す
          const eventBlock = buffer.slice(0, eventEndIndex);
          // バッファを更新（処理済み部分を削除）
          buffer = buffer.slice(eventEndIndex + 2);

          // イベントブロックを行ごとに処理
          const lines = eventBlock.split('\n');
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6);
              // 空データはスキップ
              if (!data) continue;

              try {
                const event = JSON.parse(data);
                onEvent(event.type, event);
              } catch (e) {
                // JSONパースエラー時は詳細をログ出力
                console.error('Failed to parse SSE event JSON:', {
                  error: e.message,
                  dataPreview: data.length > 200 ? data.slice(0, 200) + '...' : data,
                  dataLength: data.length,
                });
              }
            }
          }
        }
      }
    } catch (e) {
      if (e.name === 'AbortError') {
        onEvent('aborted', { message: 'Request was cancelled' });
        return;
      }
      throw e;
    }
  },

  // ==========================================================================
  // メモリAPI（パスワード保護対応）
  // ==========================================================================

  /**
   * ユーザーメモリを取得
   */
  async getMemory() {
    const response = await fetch(withProject(`${API_BASE}/api/memory`), {
      headers: getAuthHeaders(null),
    });
    if (response.status === 401) {
      throw new Error('認証が必要です');
    }
    if (!response.ok) {
      throw new Error('Failed to get memory');
    }
    return response.json();
  },

  /**
   * メモリエントリを追加
   */
  async addMemory(category, key, value) {
    const response = await fetch(withProject(`${API_BASE}/api/memory`), {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ category, key, value }),
    });
    if (response.status === 401) {
      throw new Error('認証が必要です');
    }
    if (!response.ok) {
      throw new Error('Failed to add memory');
    }
    return response.json();
  },

  /**
   * メモリエントリを更新
   */
  async updateMemory(memoryId, updates) {
    const response = await fetch(
      withProject(`${API_BASE}/api/memory/${encodeURIComponent(memoryId)}`),
      {
        method: 'PUT',
        headers: getAuthHeaders(),
        body: JSON.stringify(updates),
      }
    );
    if (response.status === 401) {
      throw new Error('認証が必要です');
    }
    if (response.status === 404) {
      throw new Error('メモリエントリが見つかりません');
    }
    if (!response.ok) {
      throw new Error('Failed to update memory');
    }
    return response.json();
  },

  /**
   * メモリエントリを削除
   */
  async deleteMemory(memoryId) {
    const response = await fetch(
      withProject(`${API_BASE}/api/memory/${encodeURIComponent(memoryId)}`),
      {
        method: 'DELETE',
        headers: getAuthHeaders(null),
      }
    );
    if (response.status === 401) {
      throw new Error('認証が必要です');
    }
    if (response.status === 404) {
      throw new Error('メモリエントリが見つかりません');
    }
    if (!response.ok) {
      throw new Error('Failed to delete memory');
    }
    return response.json();
  },

  /**
   * 全メモリをクリア
   */
  async clearMemory() {
    const response = await fetch(withProject(`${API_BASE}/api/memory`), {
      method: 'DELETE',
      headers: getAuthHeaders(null),
    });
    if (response.status === 401) {
      throw new Error('認証が必要です');
    }
    if (!response.ok) {
      throw new Error('Failed to clear memory');
    }
    return response.json();
  },

  // ==========================================================================
  // サマリーAPI（パスワード保護対応）
  // ==========================================================================

  /**
   * 会話サマリー一覧を取得
   */
  async getSummaries() {
    const response = await fetch(withProject(`${API_BASE}/api/summaries`), {
      headers: getAuthHeaders(null),
    });
    if (response.status === 401) {
      throw new Error('認証が必要です');
    }
    if (!response.ok) {
      throw new Error('Failed to get summaries');
    }
    return response.json();
  },

  /**
   * 特定の会話サマリーを削除
   */
  async deleteSummary(conversationId) {
    const response = await fetch(
      withProject(`${API_BASE}/api/summaries/${encodeURIComponent(conversationId)}`),
      {
        method: 'DELETE',
        headers: getAuthHeaders(null),
      }
    );
    if (response.status === 401) {
      throw new Error('認証が必要です');
    }
    if (response.status === 404) {
      throw new Error('サマリーが見つかりません');
    }
    if (!response.ok) {
      throw new Error('Failed to delete summary');
    }
    return response.json();
  },

  /**
   * 全サマリーをクリア
   */
  async clearSummaries() {
    const response = await fetch(withProject(`${API_BASE}/api/summaries`), {
      method: 'DELETE',
      headers: getAuthHeaders(null),
    });
    if (response.status === 401) {
      throw new Error('認証が必要です');
    }
    if (!response.ok) {
      throw new Error('Failed to clear summaries');
    }
    return response.json();
  },

  // ==========================================================================
  // ジョブAPI（バックグラウンド実行）
  // ==========================================================================

  /**
   * メッセージを送信してジョブを作成（バックグラウンド実行）
   * @param {string} conversationId - 会話ID
   * @param {string} content - メッセージ内容
   * @param {Array} userComments - ユーザーコメント
   * @returns {Promise<Object>} - { job_id, status, message }
   */
  async sendMessageJob(conversationId, content, userComments) {
    const sessionMetadata = collectSessionMetadata();

    const response = await fetch(
      withProject(`${API_BASE}/api/conversations/${conversationId}/message/job`),
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          content,
          user_comments: userComments || [],
          session_metadata: sessionMetadata,
        }),
      }
    );

    if (!response.ok) {
      throw new Error('Failed to create job');
    }

    return response.json();
  },

  /**
   * ジョブの状態を取得
   * @param {string} jobId - ジョブID
   * @returns {Promise<Object>} - ジョブデータ
   */
  async getJobStatus(jobId) {
    const response = await fetch(withProject(`${API_BASE}/api/jobs/${jobId}`));

    if (!response.ok) {
      throw new Error('Failed to get job status');
    }

    return response.json();
  },

  /**
   * ジョブの完了をポーリング
   * モバイルバックグラウンド対策: visibilitychangeで即座にポーリング再開
   *
   * @param {string} jobId - ジョブID
   * @param {function} onUpdate - 更新時のコールバック (jobData) => void
   * @param {Object} options - オプション { interval: ポーリング間隔(ms), timeout: タイムアウト(ms) }
   * @returns {Promise<Object>} - 最終的なジョブデータ
   */
  async pollJob(jobId, onUpdate, options = {}) {
    const interval = options.interval || 1000; // デフォルト1秒
    const timeout = options.timeout || 300000; // デフォルト5分
    const startTime = Date.now();

    return new Promise((resolve, reject) => {
      let timeoutId = null;
      let stopped = false;

      // フォアグラウンド復帰時に即座にポーリングを再開するリスナー
      const handleVisibilityChange = () => {
        if (!document.hidden && !stopped) {
          // バックグラウンドから復帰: 待機中のタイマーをキャンセルして即座にポーリング
          if (timeoutId) {
            clearTimeout(timeoutId);
            timeoutId = null;
          }
          doPoll();
        }
      };

      document.addEventListener('visibilitychange', handleVisibilityChange);

      const cleanup = () => {
        stopped = true;
        if (timeoutId) {
          clearTimeout(timeoutId);
          timeoutId = null;
        }
        document.removeEventListener('visibilitychange', handleVisibilityChange);
      };

      const doPoll = async () => {
        if (stopped) return;

        // タイムアウトチェック
        if (Date.now() - startTime > timeout) {
          cleanup();
          reject(new Error('Job polling timeout'));
          return;
        }

        try {
          const jobData = await this.getJobStatus(jobId);

          if (onUpdate) {
            onUpdate(jobData);
          }

          // 完了または失敗したら終了
          if (jobData.status === 'completed' || jobData.status === 'failed') {
            cleanup();
            resolve(jobData);
            return;
          }

          // 次のポーリングをスケジュール
          if (!stopped) {
            timeoutId = setTimeout(doPoll, interval);
          }
        } catch (error) {
          console.error('Polling error:', error);
          // エラー時は少し待ってリトライ
          if (!stopped) {
            timeoutId = setTimeout(doPoll, interval * 2);
          }
        }
      };

      // 即座に最初のポーリングを開始
      doPoll();
    });
  },
};
