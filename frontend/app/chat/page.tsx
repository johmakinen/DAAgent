'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { apiClient, ChatMessage } from '@/lib/api';
import MessageBubble from '@/components/MessageBubble';
import ChatInput from '@/components/ChatInput';
import ResetButton from '@/components/ResetButton';

export default function ChatPage() {
  const router = useRouter();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Check authentication
    if (!apiClient.isAuthenticated()) {
      router.push('/login');
      return;
    }

    // Load chat history
    loadHistory();
  }, [router]);

  useEffect(() => {
    // Scroll to bottom when messages change
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadHistory = async () => {
    try {
      setLoadingHistory(true);
      const history = await apiClient.getChatHistory();
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

  const handleSend = async () => {
    if (!input.trim() || loading) return;

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

    try {
      const response = await apiClient.chat(userMessage);
      
      // Reload history to get the message with proper database ID and response
      await loadHistory();
    } catch (error) {
      console.error('Failed to send message:', error);
      // Remove the optimistic message on error
      setMessages((prev) => prev.filter((msg) => msg.id !== optimisticMessage.id));
      alert(error instanceof Error ? error.message : 'Failed to send message');
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async () => {
    if (!confirm('Are you sure you want to reset the chat history?')) {
      return;
    }

    try {
      await apiClient.resetChatHistory();
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
    if (loading) return;

    // Optimistically add the user's message immediately
    const optimisticMessage: ChatMessage = {
      id: Date.now(), // Temporary ID
      message: question,
      response: '', // Will be filled when response arrives
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimisticMessage]);
    setLoading(true);

    try {
      await apiClient.chat(question);
      
      // Reload history to get the message with proper database ID and response
      await loadHistory();
    } catch (error) {
      console.error('Failed to send message:', error);
      // Remove the optimistic message on error
      setMessages((prev) => prev.filter((msg) => msg.id !== optimisticMessage.id));
      alert(error instanceof Error ? error.message : 'Failed to send message');
    } finally {
      setLoading(false);
    }
  };

  if (loadingHistory) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background">
        <div className="text-center">
          <div className="mb-4 h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent mx-auto"></div>
          <p className="text-muted-foreground">Loading chat history...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col bg-background">
      {/* Header */}
      <header className="border-b border-border px-4 py-3 shadow-sm" style={{ backgroundColor: 'hsl(var(--header-bg))', color: 'hsl(var(--header-fg))' }}>
        <div className="mx-auto flex max-w-4xl items-center justify-between">
          <h1 className="text-2xl font-bold">Agent app</h1>
          <div className="flex gap-2">
            <ResetButton onReset={handleReset} disabled={loading || messages.length === 0} />
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
                <button
                  onClick={() => handleExampleClick('What are the averages of the petal lengths for each species in the dataset?')}
                  disabled={loading}
                  className="w-full rounded-md border border-input px-4 py-3 text-left text-base shadow-sm transition-all hover:border-ring hover:shadow-md focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
                  style={{ 
                    backgroundColor: 'hsl(var(--accent-blue))',
                    color: 'hsl(var(--foreground))',
                  }}
                  onMouseEnter={(e) => {
                    if (!loading) e.currentTarget.style.backgroundColor = 'hsl(188, 30%, 82%)';
                  }}
                  onMouseLeave={(e) => {
                    if (!loading) e.currentTarget.style.backgroundColor = 'hsl(var(--accent-blue))';
                  }}
                >
                  What are the averages of the petal lengths for each species in the dataset?
                </button>
                <button
                  onClick={() => handleExampleClick('What is the maximum sepal width for each species?')}
                  disabled={loading}
                  className="w-full rounded-md border border-input px-4 py-3 text-left text-base shadow-sm transition-all hover:border-ring hover:shadow-md focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
                  style={{ 
                    backgroundColor: 'hsl(var(--accent-green))',
                    color: 'hsl(var(--foreground))',
                  }}
                  onMouseEnter={(e) => {
                    if (!loading) e.currentTarget.style.backgroundColor = 'hsl(95, 10%, 60%)';
                  }}
                  onMouseLeave={(e) => {
                    if (!loading) e.currentTarget.style.backgroundColor = 'hsl(var(--accent-green))';
                  }}
                >
                  What is the maximum sepal width for each species?
                </button>
                <button
                  onClick={() => handleExampleClick('Is there a correlation between sepal length and width for any of the species?')}
                  disabled={loading}
                  className="w-full rounded-md border border-input px-4 py-3 text-left text-base shadow-sm transition-all hover:border-ring hover:shadow-md focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
                  style={{ 
                    backgroundColor: 'hsl(var(--accent-yellow))',
                    color: 'hsl(var(--foreground))',
                  }}
                  onMouseEnter={(e) => {
                    if (!loading) e.currentTarget.style.backgroundColor = 'hsl(57, 87%, 78%)';
                  }}
                  onMouseLeave={(e) => {
                    if (!loading) e.currentTarget.style.backgroundColor = 'hsl(var(--accent-yellow))';
                  }}
                >
                  Is there a correlation between sepal length and width for any of the species?
                </button>
                <button
                  onClick={() => handleExampleClick('What has been the trend development in the income of the postal code area 00100?')}
                  disabled={loading}
                  className="w-full rounded-md border border-input px-4 py-3 text-left text-base shadow-sm transition-all hover:border-ring hover:shadow-md focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
                  style={{ 
                    backgroundColor: 'hsl(var(--accent-blue))',
                    color: 'hsl(var(--foreground))',
                  }}
                  onMouseEnter={(e) => {
                    if (!loading) e.currentTarget.style.backgroundColor = 'hsl(57, 87%, 78%)';
                  }}
                  onMouseLeave={(e) => {
                    if (!loading) e.currentTarget.style.backgroundColor = 'hsl(var(--accent-yellow))';
                  }}
                >
                  What has been the trend development in the income of the postal code area 00100?
                </button>
                <button
                  onClick={() => handleExampleClick('What is the income to apartment size ratio for the postal code area 00100?')}
                  disabled={loading}
                  className="w-full rounded-md border border-input px-4 py-3 text-left text-base shadow-sm transition-all hover:border-ring hover:shadow-md focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
                  style={{ 
                    backgroundColor: 'hsl(var(--accent-green))',
                    color: 'hsl(var(--foreground))',
                  }}
                  onMouseEnter={(e) => {
                    if (!loading) e.currentTarget.style.backgroundColor = 'hsl(57, 87%, 78%)';
                  }}
                  onMouseLeave={(e) => {
                    if (!loading) e.currentTarget.style.backgroundColor = 'hsl(var(--accent-yellow))';
                  }}
                >
                  What is the income to apartment size ratio for the postal code area 00100?
                </button>
                <button
                  onClick={() => handleExampleClick('What was the population of the postal number 02650 in 2024?')}
                  disabled={loading}
                  className="w-full rounded-md border border-input px-4 py-3 text-left text-base shadow-sm transition-all hover:border-ring hover:shadow-md focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
                  style={{ 
                    backgroundColor: 'hsl(var(--accent-green))',
                    color: 'hsl(var(--foreground))',
                  }}
                  onMouseEnter={(e) => {
                    if (!loading) e.currentTarget.style.backgroundColor = 'hsl(57, 87%, 78%)';
                  }}
                  onMouseLeave={(e) => {
                    if (!loading) e.currentTarget.style.backgroundColor = 'hsl(var(--accent-yellow))';
                  }}
                >
                  What was the population of the postal number 02650 in 2024?
                </button>
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
          <ChatInput
            value={input}
            onChange={setInput}
            onSubmit={handleSend}
            disabled={loading}
          />
        </div>
      </div>
    </div>
  );
}

