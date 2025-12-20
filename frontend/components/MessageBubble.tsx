import { ChatMessage } from '@/lib/api';

interface MessageBubbleProps {
  message: ChatMessage;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  return (
    <div className="space-y-4">
      {/* User message */}
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-2xl rounded-tr-sm bg-indigo-600 px-4 py-2 text-white shadow-md dark:bg-indigo-500">
          <p className="text-sm">{message.message}</p>
        </div>
      </div>
      
      {/* Bot response */}
      <div className="flex justify-start">
        <div className="max-w-[80%] rounded-2xl rounded-tl-sm bg-gray-100 px-4 py-2 shadow-md dark:bg-gray-700 dark:text-gray-100">
          <p className="text-sm whitespace-pre-wrap">{message.response}</p>
          {message.intent_type && (
            <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
              Intent: {message.intent_type}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

