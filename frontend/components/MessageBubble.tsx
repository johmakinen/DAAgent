'use client';

import { ChatMessage } from '@/lib/api';
import PlotlyPlot from './PlotlyPlot';
import { useMemo } from 'react';

interface MessageBubbleProps {
  message: ChatMessage;
}

interface ParsedContent {
  parts: Array<{ type: 'text' | 'table'; content: string | string[][] }>;
}

function parseMarkdownTables(text: string): ParsedContent {
  // Match markdown tables: | col1 | col2 | ... |
  const tableRegex = /(\|.+\|\n(?:\|[\s\-:]+\|\n)?(?:\|.+\|\n?)+)/g;
  const parts: ParsedContent['parts'] = [];
  let lastIndex = 0;
  let match;

  while ((match = tableRegex.exec(text)) !== null) {
    // Add text before table
    if (match.index > lastIndex) {
      const textPart = text.substring(lastIndex, match.index);
      if (textPart.trim()) {
        parts.push({ type: 'text', content: textPart });
      }
    }

    // Parse table
    const tableText = match[0];
    const lines = tableText.trim().split('\n').filter(line => line.trim());
    
    if (lines.length >= 2) {
      // First line is header
      const header = lines[0].split('|').map(cell => cell.trim()).filter(cell => cell);
      // Second line is separator (skip it)
      // Remaining lines are data rows
      const rows: string[][] = [];
      for (let i = 2; i < lines.length; i++) {
        const row = lines[i].split('|').map(cell => cell.trim()).filter(cell => cell);
        if (row.length > 0) {
          rows.push(row);
        }
      }
      
      if (header.length > 0) {
        parts.push({ type: 'table', content: [header, ...rows] });
      }
    }

    lastIndex = match.index + match[0].length;
  }

  // Add remaining text
  if (lastIndex < text.length) {
    const textPart = text.substring(lastIndex);
    if (textPart.trim()) {
      parts.push({ type: 'text', content: textPart });
    }
  }

  // If no tables found, return entire text as single part
  if (parts.length === 0) {
    parts.push({ type: 'text', content: text });
  }

  return { parts };
}

function renderContent(parsed: ParsedContent) {
  return parsed.parts.map((part, idx) => {
    if (part.type === 'table') {
      const [header, ...rows] = part.content as string[][];
      return (
        <div key={idx} className="my-3 overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-muted">
                {header.map((cell, cellIdx) => (
                  <th key={cellIdx} className="border border-border px-3 py-2 text-left font-medium">
                    {cell}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, rowIdx) => (
                <tr key={rowIdx} className="bg-card">
                  {row.map((cell, cellIdx) => (
                    <td key={cellIdx} className="border border-border px-3 py-2">
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    } else {
      return (
        <span key={idx} className="whitespace-pre-wrap">
          {part.content as string}
        </span>
      );
    }
  });
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const hasResponse = message.response && message.response.trim().length > 0;
  
  const parsedContent = useMemo(() => {
    if (!hasResponse) return null;
    return parseMarkdownTables(message.response);
  }, [message.response, hasResponse]);
  
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
        <>
          {/* Plot as full-width container - shown first if available */}
          {message.plot_spec && message.plot_spec.spec && (
            <div className="w-full -mx-4 px-4">
              <PlotlyPlot spec={message.plot_spec.spec} plotType={message.plot_spec.plot_type} />
            </div>
          )}
          {/* Text response as separate message bubble */}
          <div className="flex justify-start">
            <div className="max-w-[80%] rounded-lg rounded-tl-sm px-4 py-3 shadow-sm border border-border/50" style={{ backgroundColor: 'hsl(var(--chat-bot-bg))', color: 'hsl(var(--chat-bot-fg))' }}>
              <div className="text-base">
                {parsedContent ? renderContent(parsedContent) : message.response}
              </div>
              {message.intent_type && (
                <p className="mt-2 text-sm opacity-70">
                  Intent: {message.intent_type}
                </p>
              )}
            </div>
          </div>
        </>
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

