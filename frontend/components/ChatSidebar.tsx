'use client';

import { ChatSession } from '@/lib/api';
import { Button } from '@/components/ui/button';

interface ChatSidebarProps {
  sessions: ChatSession[];
  currentSessionId: number | null;
  onNewChat: () => void;
  onSelectSession: (sessionId: number) => void;
  onDeleteSession?: (sessionId: number) => void;
  loading?: boolean;
}

export default function ChatSidebar({
  sessions,
  currentSessionId,
  onNewChat,
  onSelectSession,
  onDeleteSession,
  loading = false,
}: ChatSidebarProps) {
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className="flex h-full flex-col border-r border-border bg-card">
      {/* New Chat Button */}
      <div className="border-b border-border p-4">
        <Button
          onClick={onNewChat}
          disabled={loading}
          className="w-full"
          variant="default"
        >
          + New Chat
        </Button>
      </div>

      {/* Sessions List */}
      <div className="flex-1 overflow-y-auto">
        {sessions.length === 0 ? (
          <div className="p-4 text-center text-sm text-muted-foreground">
            No chats yet. Start a new conversation!
          </div>
        ) : (
          <div className="p-2">
            {sessions.map((session) => {
              const isActive = session.id === currentSessionId;
              return (
                <div
                  key={session.id}
                  className={`group relative mb-1 rounded-md p-3 cursor-pointer transition-colors ${
                    isActive
                      ? 'bg-accent text-accent-foreground'
                      : 'hover:bg-muted'
                  }`}
                  onClick={() => onSelectSession(session.id)}
                >
                  <div className="pr-8">
                    <p className="text-sm font-medium truncate">
                      {session.title || 'New Chat'}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      {formatDate(session.updated_at)}
                    </p>
                  </div>
                  {onDeleteSession && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        if (confirm('Delete this chat?')) {
                          onDeleteSession(session.id);
                        }
                      }}
                      className="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-destructive/10 text-destructive text-xs"
                      title="Delete chat"
                    >
                      ×
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
