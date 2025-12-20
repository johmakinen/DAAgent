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
    setLoading(true);

    try {
      const response = await apiClient.chat(userMessage);
      
      // Reload history to get the message with proper database ID
      await loadHistory();
    } catch (error) {
      console.error('Failed to send message:', error);
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

    setLoading(true);

    try {
      await apiClient.chat(question);
      
      // Reload history to get the message with proper database ID
      await loadHistory();
    } catch (error) {
      console.error('Failed to send message:', error);
      alert(error instanceof Error ? error.message : 'Failed to send message');
    } finally {
      setLoading(false);
    }
  };

  if (loadingHistory) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50 dark:bg-gray-900">
        <div className="text-center">
          <div className="mb-4 h-8 w-8 animate-spin rounded-full border-4 border-indigo-600 border-t-transparent mx-auto"></div>
          <p className="text-gray-600 dark:text-gray-400">Loading chat history...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <header className="border-b border-gray-200 bg-white px-4 py-3 shadow-sm dark:border-gray-700 dark:bg-gray-800">
        <div className="mx-auto flex max-w-4xl items-center justify-between">
          <h1 className="text-xl font-bold text-gray-900 dark:text-white">Agent app</h1>
          <div className="flex gap-2">
            <ResetButton onReset={handleReset} disabled={loading || messages.length === 0} />
            <button
              onClick={handleLogout}
              className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:bg-gray-600"
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
              <p className="mb-6 text-center text-gray-500 dark:text-gray-400">
                No messages yet. Start a conversation!
              </p>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-4">
                Try asking one of these questions:
              </p>
              <div className="space-y-3">
                <button
                  onClick={() => handleExampleClick('What are the averages of the petal lengths for each species in the dataset?')}
                  disabled={loading}
                  className="w-full rounded-lg border border-gray-200 bg-white px-4 py-3 text-left text-sm text-gray-700 shadow-sm transition-all hover:border-indigo-300 hover:bg-indigo-50 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:border-indigo-500 dark:hover:bg-gray-600"
                >
                  What are the averages of the petal lengths for each species in the dataset?
                </button>
                <button
                  onClick={() => handleExampleClick('What is the maximum sepal width for each species?')}
                  disabled={loading}
                  className="w-full rounded-lg border border-gray-200 bg-white px-4 py-3 text-left text-sm text-gray-700 shadow-sm transition-all hover:border-indigo-300 hover:bg-indigo-50 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:border-indigo-500 dark:hover:bg-gray-600"
                >
                  What is the maximum sepal width for each species?
                </button>
                <button
                  onClick={() => handleExampleClick('How many records are there for each species in the dataset?')}
                  disabled={loading}
                  className="w-full rounded-lg border border-gray-200 bg-white px-4 py-3 text-left text-sm text-gray-700 shadow-sm transition-all hover:border-indigo-300 hover:bg-indigo-50 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200 dark:hover:border-indigo-500 dark:hover:bg-gray-600"
                >
                  How many records are there for each species in the dataset?
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="mx-auto max-w-4xl space-y-6">
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="max-w-[80%] rounded-2xl rounded-tl-sm bg-gray-100 px-4 py-2 shadow-md dark:bg-gray-700">
                  <div className="flex items-center gap-2">
                    <div className="h-2 w-2 animate-bounce rounded-full bg-gray-400"></div>
                    <div className="h-2 w-2 animate-bounce rounded-full bg-gray-400" style={{ animationDelay: '0.2s' }}></div>
                    <div className="h-2 w-2 animate-bounce rounded-full bg-gray-400" style={{ animationDelay: '0.4s' }}></div>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input area */}
      <div className="border-t border-gray-200 bg-white px-4 py-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
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

