import './Sidebar.css';

export default function Sidebar({
  conversations,
  currentConversationId,
  onSelectConversation,
  onNewConversation,
  onOpenSettings,
  onDeleteConversation,
  projectId,
  onProjectChange,
  projects,
  onRefreshProjects,
  onDeleteProject,
  onCreateProject,
  isMobile = false,
  isOpen = true,
  onClose,
}) {
  return (
    <div className={`sidebar ${isMobile ? 'sidebar--mobile' : ''} ${isOpen ? 'sidebar--open' : ''}`}>
      <div className="sidebar-header">
        <div className="header-top">
          <h1>James Council</h1>
          <div className="header-actions">
            <button className="settings-btn" onClick={onOpenSettings} title="Settings">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="3"/>
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
              </svg>
            </button>
            {isMobile && (
              <button className="sidebar-close-btn" onClick={onClose} title="Close">
                ×
              </button>
            )}
          </div>
        </div>
        <button className="new-conversation-btn" onClick={onNewConversation}>
          + New Conversation
        </button>

        <div className="project-selector">
          <label htmlFor="project-id">Project</label>
          <div className="project-row">
            <select
              id="project-id"
              value={projectId}
              onChange={(e) => onProjectChange(e.target.value)}
            >
              {[...new Set(['default', ...(projects || [])])].map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
            <button className="icon-btn" onClick={onCreateProject} title="New project">
              +
            </button>
            <button className="icon-btn" onClick={onRefreshProjects} title="Refresh projects">
              ↻
            </button>
            <button
              className="icon-btn danger"
              onClick={onDeleteProject}
              title="Delete current project"
              disabled={projectId === 'default'}
            >
              🗑
            </button>
          </div>
        </div>
      </div>

      <div className="conversation-list">
        {conversations.length === 0 ? (
          <div className="no-conversations">No conversations yet</div>
        ) : (
          conversations.map((conv) => (
            <div
              key={conv.id}
              className={`conversation-item ${
                conv.id === currentConversationId ? 'active' : ''
              }`}
              onClick={() => onSelectConversation(conv.id)}
            >
              <div className="conversation-content">
                <div className="conversation-title">
                  {conv.title || 'New Conversation'}
                </div>
                <div className="conversation-meta">
                  {conv.message_count} messages
                </div>
              </div>
              <button
                className="conversation-delete-btn"
                onClick={(e) => {
                  e.stopPropagation();
                  onDeleteConversation(conv.id, conv.title);
                }}
                title="削除"
              >
                ×
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
