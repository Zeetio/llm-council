import { useState, useEffect, useRef } from 'react';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
import Settings from './components/Settings';
import PasswordDialog from './components/PasswordDialog';
import {
  api,
  getProjectId as apiGetProjectId,
  setProjectId as apiSetProjectId,
  getActiveJob,
  saveActiveJob,
  clearActiveJob,
  hasProjectPassword
} from './api';
import useNotification from './hooks/useNotification';
import './App.css';

function App() {
  const [conversations, setConversations] = useState([]);
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const [currentConversation, setCurrentConversation] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [projectId, setProjectId] = useState(apiGetProjectId());
  const [projects, setProjects] = useState([]);
  const [isMobile, setIsMobile] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const lastIsMobileRef = useRef(null);
  const preservePasswordRef = useRef(false);

  // Notification hook
  const { sendNotification, requestPermission, permission } = useNotification();

  // パスワードダイアログ関連の状態
  const [showPasswordDialog, setShowPasswordDialog] = useState(false);
  const [pendingProjectId, setPendingProjectId] = useState(null);
  const [isAuthRequired, setIsAuthRequired] = useState(false); // 初回認証待ち状態

  // ユーザーコメント（フィードバック）状態
  // 構造: [{ id, selectedText, comment, createdAt }]
  const [userComments, setUserComments] = useState([]);

  // 生成中断用のAbortController
  const abortControllerRef = useRef(null);

  // Load conversations on mount（パスワード確認付き）
  useEffect(() => {
    const initializeProject = async () => {
      apiSetProjectId(projectId, { preservePassword: preservePasswordRef.current });
      preservePasswordRef.current = false;

      // パスワード保護状態を確認
      try {
        const authStatus = await api.getProjectAuthStatus(projectId);
        if (authStatus.has_password && !hasProjectPassword()) {
          // パスワード未入力 → ダイアログを表示
          setPendingProjectId(projectId);
          setIsAuthRequired(true);
          setShowPasswordDialog(true);
          return; // 認証完了まで待機
        }
      } catch (error) {
        // エラー時（新規プロジェクト等）は認証不要として続行
        console.error('Failed to check auth status:', error);
      }

      // パスワードなし or 認証済み → 通常読み込み
      setIsAuthRequired(false);
      loadConversations();
      loadProjects();
    };

    initializeProject();
  }, [projectId]);

  useEffect(() => {
    const updateLayout = () => {
      if (typeof window === 'undefined') return;
      const mobile = window.innerWidth <= 900;
      setIsMobile(mobile);
      const lastIsMobile = lastIsMobileRef.current;
      if (lastIsMobile === null || lastIsMobile !== mobile) {
        setIsSidebarOpen(!mobile);
      }
      lastIsMobileRef.current = mobile;
    };

    updateLayout();
    window.addEventListener('resize', updateLayout);
    return () => window.removeEventListener('resize', updateLayout);
  }, []);

  // Page Visibility API: フォアグラウンド復帰時に会話リストを最新化
  // （ポーリングの即時再開はpollJob内部のvisibilitychangeリスナーが担当）
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (!document.hidden) {
        // フォアグラウンドに復帰時、会話リストを最新化
        loadConversations();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, []);

  const loadProjects = async () => {
    try {
      const list = await api.listProjects();
      setProjects(list.includes(projectId) ? list : [projectId, ...list]);
    } catch (error) {
      console.error('Failed to list projects:', error);
    }
  };

  // Load conversation details when selected
  useEffect(() => {
    if (currentConversationId) {
      loadConversation(currentConversationId);
    }
  }, [currentConversationId]);

  const loadConversations = async () => {
    try {
      const convs = await api.listConversations();
      setConversations(convs);
    } catch (error) {
      console.error('Failed to load conversations:', error);
    }
  };

  const loadConversation = async (id) => {
    try {
      const conv = await api.getConversation(id);
      setCurrentConversation(conv);
    } catch (error) {
      console.error('Failed to load conversation:', error);
    }
  };

  const handleNewConversation = async () => {
    try {
      const newConv = await api.createConversation();
      setConversations([
        { id: newConv.id, created_at: newConv.created_at, message_count: 0 },
        ...conversations,
      ]);
      setCurrentConversationId(newConv.id);
    } catch (error) {
      console.error('Failed to create conversation:', error);
    }
  };

  const handleSelectConversation = (id) => {
    setCurrentConversationId(id);
    // モバイルでは会話選択時にサイドバーを自動的に閉じる
    if (isMobile) {
      setIsSidebarOpen(false);
    }
  };

  // プロジェクト切り替え完了処理
  const completeProjectChange = (id) => {
    setProjectId(id);
    setCurrentConversationId(null);
    setCurrentConversation(null);
    setShowPasswordDialog(false);
    setPendingProjectId(null);
  };

  // パスワード認証成功時の処理
  const handlePasswordSuccess = () => {
    if (pendingProjectId) {
      if (isAuthRequired && pendingProjectId === projectId) {
        // 初回認証成功 - 現在のプロジェクトでデータ読み込み
        setShowPasswordDialog(false);
        setPendingProjectId(null);
        setIsAuthRequired(false);
        loadConversations();
        loadProjects();
      } else {
        // プロジェクト切り替え時の認証成功
        preservePasswordRef.current = true;
        completeProjectChange(pendingProjectId);
      }
    }
  };

  // パスワードダイアログキャンセル時の処理
  const handlePasswordCancel = () => {
    if (isAuthRequired) {
      // 初回認証キャンセル - defaultプロジェクトに切り替え
      setShowPasswordDialog(false);
      setPendingProjectId(null);
      setIsAuthRequired(false);
      if (projectId !== 'default') {
        setProjectId('default');
      } else {
        // defaultプロジェクトの場合は直接読み込み
        loadConversations();
        loadProjects();
      }
    } else {
      // プロジェクト切り替えキャンセル - 何もしない
      setShowPasswordDialog(false);
      setPendingProjectId(null);
    }
  };

  const handleProjectChange = async (id) => {
    const next = id?.trim() || 'default';

    // 現在のプロジェクトと同じなら何もしない
    if (next === projectId) return;

    try {
      // パスワード状態を確認
      const authStatus = await api.getProjectAuthStatus(next);
      if (authStatus.has_password) {
        // パスワードダイアログを表示
        setPendingProjectId(next);
        setShowPasswordDialog(true);
      } else {
        // パスワードなし - 直接切り替え
        completeProjectChange(next);
      }
    } catch (error) {
      console.error('Failed to check auth status:', error);
      // エラー時も切り替えを試みる（新規プロジェクトの場合など）
      completeProjectChange(next);
    }
  };

  const handleDeleteProject = async () => {
    const target = projectId;
    if (target === 'default') return;
    if (!confirm(`Delete project "${target}"?`)) return;
    try {
      await api.deleteProject(target);
      setProjectId('default');
      setCurrentConversation(null);
      setCurrentConversationId(null);
      await loadProjects();
      await loadConversations();
    } catch (error) {
      console.error('Failed to delete project:', error);
    }
  };

  const handleCreateProject = async () => {
    const name = prompt('Enter new project name:');
    if (!name || !name.trim()) return;
    try {
      await api.createProject(name.trim());
      await loadProjects();
      setProjectId(name.trim());
    } catch (error) {
      console.error('Failed to create project:', error);
    }
  };

  // 会話削除ハンドラー
  const handleDeleteConversation = async (conversationId, title) => {
    if (!confirm(`「${title || 'New Conversation'}」を削除しますか？`)) return;
    try {
      await api.deleteConversation(conversationId);
      await loadConversations();
      // 削除した会話が現在選択中の場合は選択を解除
      if (currentConversationId === conversationId) {
        setCurrentConversationId(null);
        setCurrentConversation(null);
      }
    } catch (error) {
      console.error('Failed to delete conversation:', error);
    }
  };

  // コメント追加ハンドラー
  const handleAddComment = ({ selectedText, comment }) => {
    const newComment = {
      id: `comment-${Date.now()}`,
      selectedText,
      comment,
      createdAt: new Date().toISOString(),
    };
    setUserComments((prev) => [...prev, newComment]);
    console.log('Comment added:', newComment);
  };

  // コメント削除ハンドラー
  const handleDeleteComment = (commentId) => {
    setUserComments((prev) => prev.filter((c) => c.id !== commentId));
  };

  // 生成を停止する
  const handleStopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    // ローディング状態をリセット
    setIsLoading(false);
    // 未完了のassistantメッセージのloadingフラグをクリア
    setCurrentConversation((prev) => {
      if (!prev) return prev;
      const messages = [...prev.messages];
      const lastIdx = messages.length - 1;
      if (lastIdx >= 0 && messages[lastIdx].role === 'assistant') {
        messages[lastIdx] = {
          ...messages[lastIdx],
          loading: { stage1: false, stage2: false, stage3: false },
        };
      }
      return { ...prev, messages };
    });
    // アクティブジョブをクリア
    clearActiveJob();
  };

  /**
   * ジョブのポーリングとUI更新を行う共通処理
   * 新規送信とページリロード後の復元の両方で使用
   */
  const pollJobAndUpdateUI = async (jobId) => {
    // 前回のステージを記憶（重複更新を防ぐ）
    let lastStage = null;

    await api.pollJob(
      jobId,
      (jobData) => {
        const { progress, status } = jobData;

        // ステージ1の更新
        if (progress?.stage1?.status === 'running' && lastStage !== 'stage1-running') {
          lastStage = 'stage1-running';
          setCurrentConversation((prev) => {
            if (!prev) return prev;
            const messages = [...prev.messages];
            const lastIdx = messages.length - 1;
            if (lastIdx < 0 || messages[lastIdx].role !== 'assistant') return prev;
            messages[lastIdx] = {
              ...messages[lastIdx],
              loading: { ...messages[lastIdx].loading, stage1: true },
            };
            return { ...prev, messages };
          });
        }

        if (progress?.stage1?.status === 'completed' && progress?.stage1?.data && lastStage !== 'stage1-completed') {
          lastStage = 'stage1-completed';
          setCurrentConversation((prev) => {
            if (!prev) return prev;
            const messages = [...prev.messages];
            const lastIdx = messages.length - 1;
            if (lastIdx < 0 || messages[lastIdx].role !== 'assistant') return prev;
            messages[lastIdx] = {
              ...messages[lastIdx],
              stage1: progress.stage1.data,
              loading: { ...messages[lastIdx].loading, stage1: false },
            };
            return { ...prev, messages };
          });
        }

        // ステージ2の更新
        if (progress?.stage2?.status === 'running' && lastStage !== 'stage2-running') {
          lastStage = 'stage2-running';
          setCurrentConversation((prev) => {
            if (!prev) return prev;
            const messages = [...prev.messages];
            const lastIdx = messages.length - 1;
            if (lastIdx < 0 || messages[lastIdx].role !== 'assistant') return prev;
            messages[lastIdx] = {
              ...messages[lastIdx],
              loading: { ...messages[lastIdx].loading, stage2: true },
            };
            return { ...prev, messages };
          });
        }

        if (progress?.stage2?.status === 'completed' && progress?.stage2?.data && lastStage !== 'stage2-completed') {
          lastStage = 'stage2-completed';
          setCurrentConversation((prev) => {
            if (!prev) return prev;
            const messages = [...prev.messages];
            const lastIdx = messages.length - 1;
            if (lastIdx < 0 || messages[lastIdx].role !== 'assistant') return prev;
            messages[lastIdx] = {
              ...messages[lastIdx],
              stage2: progress.stage2.data,
              metadata: progress.stage2.metadata,
              loading: { ...messages[lastIdx].loading, stage2: false },
            };
            return { ...prev, messages };
          });
        }

        // ステージ3の更新
        if (progress?.stage3?.status === 'running' && lastStage !== 'stage3-running') {
          lastStage = 'stage3-running';
          setCurrentConversation((prev) => {
            if (!prev) return prev;
            const messages = [...prev.messages];
            const lastIdx = messages.length - 1;
            if (lastIdx < 0 || messages[lastIdx].role !== 'assistant') return prev;
            messages[lastIdx] = {
              ...messages[lastIdx],
              loading: { ...messages[lastIdx].loading, stage3: true },
            };
            return { ...prev, messages };
          });
        }

        if (progress?.stage3?.status === 'completed' && progress?.stage3?.data && lastStage !== 'stage3-completed') {
          lastStage = 'stage3-completed';
          setCurrentConversation((prev) => {
            if (!prev) return prev;
            const messages = [...prev.messages];
            const lastIdx = messages.length - 1;
            if (lastIdx < 0 || messages[lastIdx].role !== 'assistant') return prev;
            messages[lastIdx] = {
              ...messages[lastIdx],
              stage3: progress.stage3.data,
              loading: { ...messages[lastIdx].loading, stage3: false },
            };
            return { ...prev, messages };
          });
        }

        // 完了時の処理
        if (status === 'completed') {
          setCurrentConversation((prev) => {
            if (!prev) return prev;
            const messages = [...prev.messages];
            const lastIdx = messages.length - 1;
            if (lastIdx < 0 || messages[lastIdx].role !== 'assistant') return prev;

            // usageがない場合はデフォルト値を設定
            const usageData = jobData.usage || {
              total_calls: 0,
              total_tokens: 0,
              total_cost_usd: 0,
              by_stage: {},
              by_model: {}
            };

            messages[lastIdx] = {
              ...messages[lastIdx],
              usage: usageData,
            };
            return { ...prev, messages };
          });

          // 通知を送信
          sendNotification('LLM Council: 生成が完了しました', {
            body: 'すべてのステージの処理が終了しました。クリックして結果を確認してください。',
            tag: jobId // 同じジョブの通知は上書き
          });
        }
      },
      { interval: 1000, timeout: 300000 }
    );
  };

  // ページロード時にアクティブジョブがあれば復元する
  useEffect(() => {
    const resumeActiveJob = async () => {
      const activeJob = getActiveJob();
      if (!activeJob) return;

      const { jobId, conversationId, projectId: jobProjectId } = activeJob;

      // 現在のプロジェクトと一致しない場合はスキップ
      if (jobProjectId !== projectId) return;

      console.log('Resuming active job:', jobId);

      try {
        // ジョブの現在の状態を確認
        const jobData = await api.getJobStatus(jobId);

        if (jobData.status === 'completed' || jobData.status === 'failed') {
          // 既に完了/失敗している場合はクリアして会話をリロード
          clearActiveJob();
          setCurrentConversationId(conversationId);
          return;
        }

        // まだ実行中 → 会話を読み込んでポーリングを再開
        setCurrentConversationId(conversationId);
        setIsLoading(true);

        // 会話データを読み込み（サーバー側で保存済みのメッセージを反映）
        const conv = await api.getConversation(conversationId);
        setCurrentConversation(conv);

        // 最後のメッセージにloading状態を追加
        setCurrentConversation((prev) => {
          if (!prev) return prev;
          const messages = [...prev.messages];
          const lastIdx = messages.length - 1;
          if (lastIdx >= 0 && messages[lastIdx].role === 'assistant') {
            messages[lastIdx] = {
              ...messages[lastIdx],
              loading: {
                stage1: jobData.progress?.stage1?.status === 'running',
                stage2: jobData.progress?.stage2?.status === 'running',
                stage3: jobData.progress?.stage3?.status === 'running',
              },
            };
            return { ...prev, messages };
          }
          return prev;
        });

        // ポーリングを再開
        await pollJobAndUpdateUI(jobId);

        clearActiveJob();
        loadConversations();
        setIsLoading(false);
      } catch (error) {
        console.error('Failed to resume active job:', error);
        clearActiveJob();
        setIsLoading(false);
      }
    };

    resumeActiveJob();
  }, []); // マウント時に1回のみ実行

  // ジョブベースのメッセージ送信（バックグラウンド実行対応）
  const handleSendMessage = async (content) => {
    if (!currentConversationId) return;

    // 通知許可をリクエスト（ユーザーアクション内なので許可されやすい）
    if (permission === 'default') {
      requestPermission();
    }

    setIsLoading(true);
    try {
      // Optimistically add user message to UI
      const userMessage = { role: 'user', content };
      setCurrentConversation((prev) => ({
        ...prev,
        messages: [...prev.messages, userMessage],
      }));

      // Create a partial assistant message that will be updated progressively
      const assistantMessage = {
        role: 'assistant',
        stage1: null,
        stage2: null,
        stage3: null,
        metadata: null,
        loading: {
          stage1: false,
          stage2: false,
          stage3: false,
        },
      };

      // Add the partial assistant message
      setCurrentConversation((prev) => ({
        ...prev,
        messages: [...prev.messages, assistantMessage],
      }));

      // ユーザーコメントを準備してクリア
      const commentsToSend = [...userComments];
      setUserComments([]);

      // ジョブを作成
      const jobResponse = await api.sendMessageJob(
        currentConversationId,
        content,
        commentsToSend
      );

      const jobId = jobResponse.job_id;
      console.log('Job created:', jobId);

      // ジョブ情報をlocalStorageに保存（モバイルバックグラウンド/リロード対策）
      saveActiveJob(jobId, currentConversationId, projectId);

      // ジョブをポーリング
      await pollJobAndUpdateUI(jobId);

      // 完了 - ジョブ情報をクリア
      clearActiveJob();
      loadConversations();
      setIsLoading(false);
    } catch (error) {
      console.error('Failed to send message:', error);
      clearActiveJob();
      // Remove optimistic messages on error
      setCurrentConversation((prev) => ({
        ...prev,
        messages: prev.messages.slice(0, -2),
      }));
      setIsLoading(false);
    }
  };

  return (
    <div className="app">
      <Sidebar
        conversations={conversations}
        currentConversationId={currentConversationId}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
        onOpenSettings={() => setShowSettings(true)}
        onDeleteConversation={handleDeleteConversation}
        projectId={projectId}
        onProjectChange={handleProjectChange}
        projects={projects}
        onRefreshProjects={loadProjects}
        onDeleteProject={handleDeleteProject}
        onCreateProject={handleCreateProject}
        isMobile={isMobile}
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
      />
      {isMobile && isSidebarOpen && (
        <button
          type="button"
          className="sidebar-overlay"
          aria-label="Close sidebar"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}
      <ChatInterface
        conversation={currentConversation}
        onSendMessage={handleSendMessage}
        isLoading={isLoading}
        onAddComment={handleAddComment}
        onDeleteComment={handleDeleteComment}
        onStopGeneration={handleStopGeneration}
        pendingComments={userComments}
        onToggleSidebar={() => setIsSidebarOpen((prev) => !prev)}
        isMobile={isMobile}
        isSidebarOpen={isSidebarOpen}
      />
      {showSettings && (
        <Settings
          onClose={() => setShowSettings(false)}
          requestNotificationPermission={requestPermission}
          notificationPermission={permission}
        />
      )}
      {showPasswordDialog && pendingProjectId && (
        <PasswordDialog
          projectId={pendingProjectId}
          mode="verify"
          onSuccess={handlePasswordSuccess}
          onCancel={handlePasswordCancel}
        />
      )}
    </div>
  );
}

export default App;
