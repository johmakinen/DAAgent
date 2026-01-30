const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface ChatMessage {
  id: number;
  message: string;
  response: string;
  intent_type?: string | null;
  metadata?: any;
  plot_spec?: {
    spec: any;
    plot_type?: string;
  } | null;
  created_at: string;
}

export interface ChatSession {
  id: number;
  user_id: number;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface ToolCall {
  inputs?: {
    sql_query?: string;
  };
  outputs?: {
    success?: boolean;
    error?: string;
    row_count?: number;
    data?: any[];
  };
  error?: string;
  duration_ms?: number;
}

class ApiClient {
  private token: string | null = null;

  constructor() {
    if (typeof window !== 'undefined') {
      this.token = localStorage.getItem('access_token');
    }
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`;
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string> || {}),
    };

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const response = await fetch(url, {
      ...options,
      headers: headers as HeadersInit,
    });

    if (response.status === 401) {
      this.logout();
      throw new Error('401 Unauthorized');
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Request failed' }));
      throw new Error(error.detail || `HTTP error! status: ${response.status}`);
    }

    return response.json();
  }

  isAuthenticated(): boolean {
    return !!this.token;
  }

  async login(credentials: { username: string }): Promise<void> {
    const response = await this.request<{
      access_token: string;
      token_type: string;
      user_id: number;
      username: string;
    }>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify(credentials),
    });

    this.token = response.access_token;
    if (typeof window !== 'undefined') {
      localStorage.setItem('access_token', response.access_token);
    }
  }

  logout(): void {
    this.token = null;
    if (typeof window !== 'undefined') {
      localStorage.removeItem('access_token');
    }
  }

  async chat(message: string, chatSessionId: number, signal?: AbortSignal): Promise<{ response: string }> {
    return this.request<{ response: string }>('/api/chat', {
      method: 'POST',
      body: JSON.stringify({
        message,
        chat_session_id: chatSessionId,
      }),
      signal,
    });
  }

  async getChatHistory(chatSessionId: number): Promise<{ messages: ChatMessage[]; chat_session_id: number }> {
    return this.request<{ messages: ChatMessage[]; chat_session_id: number }>(
      `/api/chat/history?chat_session_id=${chatSessionId}`
    );
  }

  async resetChatHistory(chatSessionId: number): Promise<{ message: string; deleted_count: number }> {
    return this.request<{ message: string; deleted_count: number }>(
      `/api/chat/reset?chat_session_id=${chatSessionId}`,
      {
        method: 'POST',
      }
    );
  }

  async createChatSession(title?: string): Promise<{ session: ChatSession }> {
    return this.request<{ session: ChatSession }>('/api/chat/sessions', {
      method: 'POST',
      body: JSON.stringify({ title }),
    });
  }

  async getChatSessions(): Promise<{ sessions: ChatSession[] }> {
    return this.request<{ sessions: ChatSession[] }>('/api/chat/sessions');
  }

  async getChatSession(sessionId: number): Promise<ChatSession> {
    return this.request<ChatSession>(`/api/chat/sessions/${sessionId}`);
  }

  async deleteChatSession(sessionId: number): Promise<{ message: string; deleted_count: number }> {
    return this.request<{ message: string; deleted_count: number }>(
      `/api/chat/sessions/${sessionId}`,
      {
        method: 'DELETE',
      }
    );
  }

  async cancelChatRequest(chatSessionId: number): Promise<{ message: string; cancelled: boolean }> {
    return this.request<{ message: string; cancelled: boolean }>(
      `/api/chat/cancel?chat_session_id=${chatSessionId}`,
      {
        method: 'POST',
      }
    );
  }
}

export const apiClient = new ApiClient();
