import { useState, useEffect, useRef } from 'react';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
import Settings from './components/Settings';
import PasswordDialog from './components/PasswordDialog';
import { api, setProjectId as apiSetProjectId, getProjectId as apiGetProjectId } from './api';
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
        if (authStatus.has_password) {
          // パスワードダイアログを表示（初回認証）
          setPendingProjectId(projectId);
          setIsAuthRequired(true);
          setShowPasswordDialog(true);
          return; // 認証完了まで待機
        }
      } catch (error) {
        // エラー時（新規プロジェクト等）は認証不要として続行
        console.error('Failed to check auth status:', error);
      }

      // パスワードなし - 通常読み込み
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
  };

  const handleSendMessage = async (content) => {
    if (!currentConversationId) return;

    // AbortControllerを作成
    abortControllerRef.current = new AbortController();

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

      // Send message with streaming（ユーザーコメントを含む）
      const commentsToSend = [...userComments];
      setUserComments([]); // コメントをクリア

      await api.sendMessageStream(
        currentConversationId,
        content,
        commentsToSend,
        (eventType, event) => {
        switch (eventType) {
          case 'stage1_start':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastIdx = messages.length - 1;
              messages[lastIdx] = {
                ...messages[lastIdx],
                loading: { ...messages[lastIdx].loading, stage1: true },
              };
              return { ...prev, messages };
            });
            break;

          case 'stage1_complete':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastIdx = messages.length - 1;
              messages[lastIdx] = {
                ...messages[lastIdx],
                stage1: event.data,
                loading: { ...messages[lastIdx].loading, stage1: false },
              };
              return { ...prev, messages };
            });
            break;

          case 'stage2_start':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastIdx = messages.length - 1;
              messages[lastIdx] = {
                ...messages[lastIdx],
                loading: { ...messages[lastIdx].loading, stage2: true },
              };
              return { ...prev, messages };
            });
            break;

          case 'stage2_complete':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastIdx = messages.length - 1;
              messages[lastIdx] = {
                ...messages[lastIdx],
                stage2: event.data,
                metadata: event.metadata,
                loading: { ...messages[lastIdx].loading, stage2: false },
              };
              return { ...prev, messages };
            });
            break;

          case 'stage3_start':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastIdx = messages.length - 1;
              messages[lastIdx] = {
                ...messages[lastIdx],
                loading: { ...messages[lastIdx].loading, stage3: true },
              };
              return { ...prev, messages };
            });
            break;

          case 'stage3_complete':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastIdx = messages.length - 1;
              messages[lastIdx] = {
                ...messages[lastIdx],
                stage3: event.data,
                loading: { ...messages[lastIdx].loading, stage3: false },
              };
              return { ...prev, messages };
            });
            break;

          case 'title_complete':
            // Reload conversations to get updated title
            loadConversations();
            break;

          case 'complete':
            // Stream complete - 使用量データを保存
            if (event.usage) {
              setCurrentConversation((prev) => {
                const messages = [...prev.messages];
                const lastIdx = messages.length - 1;
                messages[lastIdx] = {
                  ...messages[lastIdx],
                  usage: event.usage,
                };
                return { ...prev, messages };
              });
            }
            // Reload conversations list
            loadConversations();
            setIsLoading(false);
            abortControllerRef.current = null;
            break;

          case 'aborted':
            // ユーザーによる中断
            console.log('Generation stopped by user');
            setIsLoading(false);
            abortControllerRef.current = null;
            break;

          case 'error':
            console.error('Stream error:', event.message);
            setIsLoading(false);
            abortControllerRef.current = null;
            break;

          default:
            console.log('Unknown event type:', eventType);
        }
      },
        abortControllerRef.current?.signal
      );
    } catch (error) {
      // AbortErrorはユーザーによる中断なのでエラー扱いしない
      if (error.name === 'AbortError') {
        console.log('Request aborted by user');
        setIsLoading(false);
        abortControllerRef.current = null;
        return;
      }
      console.error('Failed to send message:', error);
      // Remove optimistic messages on error
      setCurrentConversation((prev) => ({
        ...prev,
        messages: prev.messages.slice(0, -2),
      }));
      setIsLoading(false);
      abortControllerRef.current = null;
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
      {showSettings && <Settings onClose={() => setShowSettings(false)} />}
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
