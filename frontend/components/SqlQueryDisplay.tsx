'use client';

import { useState } from 'react';
import { ToolCall } from '@/lib/api';

interface SqlQueryDisplayProps {
  toolCall: ToolCall;
}

export default function SqlQueryDisplay({ toolCall }: SqlQueryDisplayProps) {
  const [copied, setCopied] = useState(false);
  
  const sqlQuery = toolCall.inputs?.sql_query || '';
  const queryResult = toolCall.outputs;
  const hasError = toolCall.error || (queryResult && !queryResult.success);
  const errorMessage = toolCall.error || queryResult?.error;

  const handleCopy = async () => {
    if (sqlQuery) {
      await navigator.clipboard.writeText(sqlQuery);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="mt-2 space-y-2">
      {/* SQL Query */}
      <div className="relative">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs font-medium text-gray-600 dark:text-gray-400">SQL Query</span>
          <button
            onClick={handleCopy}
            className="text-xs px-2 py-1 rounded bg-gray-200 dark:bg-gray-600 hover:bg-gray-300 dark:hover:bg-gray-500 transition-colors"
          >
            {copied ? 'Copied!' : 'Copy'}
          </button>
        </div>
        <pre className="bg-gray-900 text-gray-100 p-3 rounded-lg text-xs overflow-x-auto">
          <code>{sqlQuery}</code>
        </pre>
      </div>

      {/* Query Result or Error */}
      {hasError ? (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3">
          <p className="text-xs font-medium text-red-800 dark:text-red-200 mb-1">Query Error</p>
          <p className="text-xs text-red-700 dark:text-red-300">{errorMessage}</p>
        </div>
      ) : queryResult && queryResult.success ? (
        <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-3">
          <p className="text-xs font-medium text-green-800 dark:text-green-200 mb-1">
            Query Result
          </p>
          <p className="text-xs text-green-700 dark:text-green-300">
            {queryResult.row_count !== undefined
              ? `Returned ${queryResult.row_count} row(s)`
              : 'Query executed successfully'}
          </p>
          {queryResult.data && Array.isArray(queryResult.data) && queryResult.data.length > 0 && (
            <div className="mt-2 max-h-32 overflow-y-auto">
              <table className="w-full text-xs border-collapse">
                <thead>
                  <tr className="bg-gray-100 dark:bg-gray-800">
                    {Object.keys(queryResult.data[0]).map((key) => (
                      <th key={key} className="border border-gray-300 dark:border-gray-600 px-2 py-1 text-left">
                        {key}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {queryResult.data.slice(0, 3).map((row: any, idx: number) => (
                    <tr key={idx} className="bg-white dark:bg-gray-700">
                      {Object.values(row).map((val: any, colIdx: number) => (
                        <td key={colIdx} className="border border-gray-300 dark:border-gray-600 px-2 py-1">
                          {String(val)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              {queryResult.data.length > 3 && (
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  ... and {queryResult.data.length - 3} more rows
                </p>
              )}
            </div>
          )}
        </div>
      ) : null}

      {/* Duration */}
      {toolCall.duration_ms !== undefined && (
        <p className="text-xs text-gray-500 dark:text-gray-400">
          Duration: {toolCall.duration_ms.toFixed(2)}ms
        </p>
      )}
    </div>
  );
}

