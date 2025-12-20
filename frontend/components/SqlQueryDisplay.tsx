'use client';

import { useState } from 'react';
import { ToolCall } from '@/lib/api';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

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
      <Card>
        <CardContent className="pt-4">
          <div className="flex items-center justify-between mb-2">
            <Badge variant="outline" className="text-xs">SQL Query</Badge>
            <Button
              onClick={handleCopy}
              variant="ghost"
              size="sm"
              className="h-7 text-xs"
            >
              {copied ? 'Copied!' : 'Copy'}
            </Button>
          </div>
          <pre className="bg-muted p-3 rounded-md text-xs overflow-x-auto border border-border">
            <code className="text-foreground">{sqlQuery}</code>
          </pre>
        </CardContent>
      </Card>

      {/* Query Result or Error */}
      {hasError ? (
        <Card className="border-destructive">
          <CardContent className="pt-4">
            <p className="text-xs font-medium text-destructive mb-1">Query Error</p>
            <p className="text-xs text-destructive/80">{errorMessage}</p>
          </CardContent>
        </Card>
      ) : queryResult && queryResult.success ? (
        <Card className="border-green-500/50">
          <CardContent className="pt-4">
            <p className="text-xs font-medium text-green-700 dark:text-green-400 mb-1">
              Query Result
            </p>
            <p className="text-xs text-green-600 dark:text-green-500">
              {queryResult.row_count !== undefined
                ? `Returned ${queryResult.row_count} row(s)`
                : 'Query executed successfully'}
            </p>
            {queryResult.data && Array.isArray(queryResult.data) && queryResult.data.length > 0 && (
              <div className="mt-2 max-h-32 overflow-y-auto">
                <table className="w-full text-xs border-collapse">
                  <thead>
                    <tr className="bg-muted">
                      {Object.keys(queryResult.data[0]).map((key) => (
                        <th key={key} className="border border-border px-2 py-1 text-left">
                          {key}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {queryResult.data.slice(0, 3).map((row: any, idx: number) => (
                      <tr key={idx} className="bg-card">
                        {Object.values(row).map((val: any, colIdx: number) => (
                          <td key={colIdx} className="border border-border px-2 py-1">
                            {String(val)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
                {queryResult.data.length > 3 && (
                  <p className="text-xs text-muted-foreground mt-1">
                    ... and {queryResult.data.length - 3} more rows
                  </p>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      ) : null}

      {/* Duration */}
      {toolCall.duration_ms !== undefined && (
        <p className="text-xs text-muted-foreground">
          Duration: {toolCall.duration_ms.toFixed(2)}ms
        </p>
      )}
    </div>
  );
}

