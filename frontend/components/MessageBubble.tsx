'use client';

import { ChatMessage } from '@/lib/api';

interface MessageBubbleProps {
  message: ChatMessage;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const hasResponse = message.response && message.response.trim().length > 0;
  
  return (
    <div className="space-y-4">
      {/* User message */}
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-lg rounded-tr-sm px-4 py-3 shadow-sm" style={{ backgroundColor: 'hsl(var(--chat-user-bg))', color: 'hsl(var(--chat-user-fg))' }}>
          <p className="text-base">{message.message}</p>
        </div>
      </div>
      
      {/* Bot response - only show if there's a response or show loading indicator */}
      {hasResponse ? (
        <div className="flex justify-start">
          <div className="max-w-[80%] rounded-lg rounded-tl-sm px-4 py-3 shadow-sm border border-border/50" style={{ backgroundColor: 'hsl(var(--chat-bot-bg))', color: 'hsl(var(--chat-bot-fg))' }}>
            <p className="text-base whitespace-pre-wrap">{message.response}</p>
            {message.intent_type && (
              <p className="mt-2 text-sm opacity-70">
                Intent: {message.intent_type}
              </p>
            )}
          </div>
        </div>
      ) : (
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
    </div>
  );
}

