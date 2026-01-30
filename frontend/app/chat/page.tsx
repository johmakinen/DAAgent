'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { apiClient, ChatMessage, ChatSession } from '@/lib/api';
import MessageBubble from '@/components/MessageBubble';
import ChatInput from '@/components/ChatInput';
import ResetButton from '@/components/ResetButton';
import ChatSidebar from '@/components/ChatSidebar';

type ExampleQuestion = {
  text: string;
  accentColor: 'blue' | 'green' | 'yellow';
  hoverColor: string; // HSL color string for hover state
};

const EXAMPLE_QUESTIONS: ExampleQuestion[] = [
  {
    text: 'What are the averages of the petal lengths for each species in the dataset?',
    accentColor: 'blue',
    hoverColor: 'hsl(188, 30%, 82%)',
  },
  {
    text: 'What is the maximum sepal width for each species?',
    accentColor: 'green',
    hoverColor: 'hsl(95, 10%, 60%)',
  },
  {
    text: 'Is there a correlation between sepal length and width for any of the species?',
    accentColor: 'yellow',
    hoverColor: 'hsl(57, 87%, 78%)',
  },
  {
    text: 'What has been the trend development in the income of the postal code area 00100?',
    accentColor: 'blue',
    hoverColor: 'hsl(188, 30%, 82%)', // Fixed: was incorrectly using yellow
  },
  {
    text: 'What is the income to apartment size ratio for the postal code area 00100?',
    accentColor: 'green',
    hoverColor: 'hsl(95, 10%, 60%)', // Fixed: was incorrectly using yellow
  },
  {
    text: 'What was the population of the postal number 02650 in 2024?',
    accentColor: 'yellow',
    hoverColor: 'hsl(57, 87%, 78%)', // Fixed: was incorrectly using yellow
  },
];

export default function ChatPage() {
  const router = useRouter();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [loadingSessions, setLoadingSessions] = useState(true);
  const [currentChatSessionId, setCurrentChatSessionId] = useState<number | null>(null);
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    // Check authentication
    if (!apiClient.isAuthenticated()) {
      router.push('/login');
      return;
    }

    // Load chat sessions and initialize
    initializeChat();
  }, [router]);

  useEffect(() => {
    // Scroll to bottom when messages change
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleNewChat = async () => {
    try {
      const response = await apiClient.createChatSession();
      const newSession = response.session;
      setChatSessions((prev) => [newSession, ...prev]);
      setCurrentChatSessionId(newSession.id);
      setMessages([]);
      return newSession.id;
    } catch (error) {
      console.error('Failed to create new chat session:', error);
      alert(error instanceof Error ? error.message : 'Failed to create new chat');
      return null;
    }
  };

  const loadSessions = async () => {
    try {
      setLoadingSessions(true);
      const response = await apiClient.getChatSessions();
      setChatSessions(response.sessions);
      
      // If no sessions exist, create one
      if (response.sessions.length === 0) {
        const newSessionId = await handleNewChat();
        if (newSessionId) {
          setCurrentChatSessionId(newSessionId);
        }
      } else if (!currentChatSessionId) {
        // Set the first session as current if none is selected
        setCurrentChatSessionId(response.sessions[0].id);
      }
    } catch (error) {
      console.error('Failed to load chat sessions:', error);
      if (error instanceof Error && error.message.includes('401')) {
        router.push('/login');
      }
    } finally {
      setLoadingSessions(false);
    }
  };

  const initializeChat = async () => {
    await loadSessions();
  };

  const loadHistory = async (chatSessionId: number) => {
    try {
      setLoadingHistory(true);
      const history = await apiClient.getChatHistory(chatSessionId);
      setMessages(history.messages);
    } catch (error) {
      console.error('Failed to load chat history:', error);
      if (error instanceof Error && error.message.includes('401')) {
        router.push('/login');
      }
    } finally {
      setLoadingHistory(false);
    }
  };

  useEffect(() => {
    if (currentChatSessionId) {
      loadHistory(currentChatSessionId);
    }
  }, [currentChatSessionId]);

  const handleSend = async () => {
    if (!input.trim() || loading || !currentChatSessionId) return;

    const userMessage = input.trim();
    setInput('');
    
    // Optimistically add the user's message immediately
    const optimisticMessage: ChatMessage = {
      id: Date.now(), // Temporary ID
      message: userMessage,
      response: '', // Will be filled when response arrives
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimisticMessage]);
    setLoading(true);

    // Create AbortController for this request
    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    try {
      await apiClient.chat(userMessage, currentChatSessionId, abortController.signal);
      
      // Reload history to get the message with proper database ID and response
      await loadHistory(currentChatSessionId);
      // Reload sessions to update titles/timestamps
      await loadSessions();
    } catch (error) {
      // Don't show error if request was aborted
      if (error instanceof Error && error.name === 'AbortError') {
        console.log('Request aborted by user');
        // Remove the optimistic message on abort
        setMessages((prev) => prev.filter((msg) => msg.id !== optimisticMessage.id));
      } else {
        console.error('Failed to send message:', error);
        // Remove the optimistic message on error
        setMessages((prev) => prev.filter((msg) => msg.id !== optimisticMessage.id));
        alert(error instanceof Error ? error.message : 'Failed to send message');
      }
    } finally {
      setLoading(false);
      abortControllerRef.current = null;
    }
  };

  const handleStop = async () => {
    if (abortControllerRef.current && currentChatSessionId) {
      // Cancel the frontend request
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      
      // Also signal the backend to stop processing
      try {
        await apiClient.cancelChatRequest(currentChatSessionId);
      } catch (error) {
        console.error('Failed to cancel request on backend:', error);
        // Continue anyway - frontend cancellation is already done
      }
      
      setLoading(false);
    }
  };

  const handleReset = async () => {
    if (!currentChatSessionId) return;
    if (!confirm('Are you sure you want to reset the chat history?')) {
      return;
    }

    try {
      await apiClient.resetChatHistory(currentChatSessionId);
      setMessages([]);
    } catch (error) {
      console.error('Failed to reset chat history:', error);
      alert(error instanceof Error ? error.message : 'Failed to reset chat history');
    }
  };

  const handleLogout = () => {
    apiClient.logout();
    router.push('/login');
  };

  const handleExampleClick = async (question: string) => {
    if (loading || !currentChatSessionId) return;

    // Optimistically add the user's message immediately
    const optimisticMessage: ChatMessage = {
      id: Date.now(), // Temporary ID
      message: question,
      response: '', // Will be filled when response arrives
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimisticMessage]);
    setLoading(true);

    // Create AbortController for this request
    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    try {
      await apiClient.chat(question, currentChatSessionId, abortController.signal);
      
      // Reload history to get the message with proper database ID and response
      await loadHistory(currentChatSessionId);
      // Reload sessions to update titles/timestamps
      await loadSessions();
    } catch (error) {
      // Don't show error if request was aborted
      if (error instanceof Error && error.name === 'AbortError') {
        console.log('Request aborted by user');
        // Remove the optimistic message on abort
        setMessages((prev) => prev.filter((msg) => msg.id !== optimisticMessage.id));
      } else {
        console.error('Failed to send message:', error);
        // Remove the optimistic message on error
        setMessages((prev) => prev.filter((msg) => msg.id !== optimisticMessage.id));
        alert(error instanceof Error ? error.message : 'Failed to send message');
      }
    } finally {
      setLoading(false);
      abortControllerRef.current = null;
    }
  };

  const handleSwitchSession = (sessionId: number) => {
    setCurrentChatSessionId(sessionId);
  };

  const handleDeleteSession = async (sessionId: number) => {
    try {
      await apiClient.deleteChatSession(sessionId);
      setChatSessions((prev) => prev.filter((s) => s.id !== sessionId));
      
      // If deleted session was current, switch to first available or create new
      if (currentChatSessionId === sessionId) {
        const remainingSessions = chatSessions.filter((s) => s.id !== sessionId);
        if (remainingSessions.length > 0) {
          setCurrentChatSessionId(remainingSessions[0].id);
        } else {
          await handleNewChat();
        }
      }
    } catch (error) {
      console.error('Failed to delete chat session:', error);
      alert(error instanceof Error ? error.message : 'Failed to delete chat');
    }
  };

  if (loadingHistory || loadingSessions) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="text-center">
          <div className="mb-4 h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent mx-auto"></div>
          <p className="text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-background">
      {/* Sidebar */}
      <div className="w-64 flex-shrink-0">
        <ChatSidebar
          sessions={chatSessions}
          currentSessionId={currentChatSessionId}
          onNewChat={handleNewChat}
          onSelectSession={handleSwitchSession}
          onDeleteSession={handleDeleteSession}
          loading={loading}
        />
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header className="border-b border-border px-4 py-3 shadow-sm" style={{ backgroundColor: 'hsl(var(--header-bg))', color: 'hsl(var(--header-fg))' }}>
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold">Agent app</h1>
            <div className="flex gap-2">
              <ResetButton onReset={handleReset} disabled={loading || messages.length === 0 || !currentChatSessionId} />
              <button
                onClick={handleLogout}
                className="rounded-md border border-input bg-background px-4 py-2 text-sm font-medium hover:bg-accent hover:text-accent-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
              >
                Logout
              </button>
            </div>
          </div>
        </header>

        {/* Messages area */}
        <div className="flex-1 overflow-y-auto px-4 py-6">
        {messages.length === 0 ? (
          <div className="flex h-full min-h-[calc(100vh-200px)] flex-col items-center justify-center">
            <div className="mx-auto w-full max-w-2xl space-y-4">
              <p className="mb-6 text-center text-muted-foreground text-lg">
                No messages yet. Start a conversation!
              </p>
              <p className="text-base font-medium text-foreground mb-4">
                Try asking one of these questions:
              </p>
              <div className="space-y-3">
                {EXAMPLE_QUESTIONS.map((question, index) => (
                  <button
                    key={index}
                    onClick={() => handleExampleClick(question.text)}
                    disabled={loading}
                    className="w-full rounded-md border border-input px-4 py-3 text-left text-base shadow-sm transition-all hover:border-ring hover:shadow-md focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
                    style={{ 
                      backgroundColor: `hsl(var(--accent-${question.accentColor}))`,
                      color: 'hsl(var(--foreground))',
                    }}
                    onMouseEnter={(e) => {
                      if (!loading) e.currentTarget.style.backgroundColor = question.hoverColor;
                    }}
                    onMouseLeave={(e) => {
                      if (!loading) e.currentTarget.style.backgroundColor = `hsl(var(--accent-${question.accentColor}))`;
                    }}
                  >
                    {question.text}
                  </button>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="mx-auto max-w-4xl space-y-6">
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
            {/* Only show loading indicator if there are no optimistic messages waiting for response */}
            {loading && messages.length > 0 && messages[messages.length - 1].response && (
              <div className="flex justify-start">
                <div className="max-w-[80%] rounded-lg rounded-tl-sm px-4 py-3 shadow-sm border border-border/50" style={{ backgroundColor: 'hsl(var(--chat-bot-bg))', color: 'hsl(var(--chat-bot-fg))' }}>
                  <div className="flex items-center gap-2">
                    <div className="h-2 w-2 animate-bounce rounded-full opacity-60"></div>
                    <div className="h-2 w-2 animate-bounce rounded-full opacity-60" style={{ animationDelay: '0.2s' }}></div>
                    <div className="h-2 w-2 animate-bounce rounded-full opacity-60" style={{ animationDelay: '0.4s' }}></div>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

        {/* Input area */}
        <div className="border-t border-border bg-card px-4 py-4 shadow-sm">
          <div className="mx-auto max-w-4xl">
            <div className="flex gap-2 items-center">
              <div className="flex-1">
                <ChatInput
                  value={input}
                  onChange={setInput}
                  onSubmit={handleSend}
                  disabled={loading || !currentChatSessionId}
                />
              </div>
              {loading && (
                <button
                  onClick={handleStop}
                  className="rounded-md border border-destructive bg-destructive/10 px-4 py-2 text-sm font-medium text-destructive hover:bg-destructive/20 focus:outline-none focus:ring-2 focus:ring-destructive focus:ring-offset-2 transition-colors"
                  aria-label="Stop generation"
                >
                  Stop generation
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

