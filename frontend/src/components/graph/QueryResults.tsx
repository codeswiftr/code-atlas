import React, { useState } from 'react';
import { Download, Table, Network } from 'lucide-react';
import { GraphQueryResponse } from '@/types/api';

interface QueryResultsProps {
  results: GraphQueryResponse | null;
  isLoading?: boolean;
  error?: string | null;
}

const QueryResults: React.FC<QueryResultsProps> = ({ results, isLoading, error }) => {
  const [exportFormat, setExportFormat] = useState<'json' | 'csv'>('json');

  if (isLoading) {
    return (
      <div className="card">
        <div className="text-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-atlas-blue-600 mx-auto" />
          <p className="text-gray-600 mt-2">Executing query...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card">
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
          <div className="text-red-800 font-medium">Query Error</div>
          <div className="text-red-600 text-sm mt-1">{error}</div>
        </div>
      </div>
    );
  }

  if (!results || results.results.length === 0) {
    return (
      <div className="card">
        <div className="text-center py-8">
          <Table className="w-12 h-12 mx-auto text-gray-400" />
          <p className="text-gray-600 mt-2">No results returned</p>
        </div>
      </div>
    );
  }

  const handleExport = (format: 'json' | 'csv') => {
    if (!results) return;

    if (format === 'json') {
      const dataStr = JSON.stringify(results.results, null, 2);
      const blob = new Blob([dataStr], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `query-results-${Date.now()}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } else if (format === 'csv') {
      // Convert to CSV
      const headers = results.columns.join(',');
      const rows = results.results.map(row => {
        return results.columns.map(col => {
          const value = row[col];
          // Escape commas and quotes in CSV
          if (value === null || value === undefined) return '';
          const str = String(value);
          if (str.includes(',') || str.includes('"') || str.includes('\n')) {
            return `"${str.replace(/"/g, '""')}"`;
          }
          return str;
        }).join(',');
      });
      const csv = [headers, ...rows].join('\n');
      const blob = new Blob([csv], { type: 'text/csv' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `query-results-${Date.now()}.csv`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    }
  };

  // Check if results contain graph-like data (nodes/edges)
  const hasGraphData = results.results.some(row => {
    const keys = Object.keys(row);
    return keys.some(key => 
      key.toLowerCase().includes('path') || 
      key.toLowerCase().includes('node') ||
      key.toLowerCase().includes('edge')
    );
  });

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-semibold">Query Results</h3>
          <p className="text-sm text-gray-600">
            {results.row_count} row{results.row_count !== 1 ? 's' : ''} in {results.execution_time_ms.toFixed(2)}ms
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <select
            value={exportFormat}
            onChange={(e) => setExportFormat(e.target.value as 'json' | 'csv')}
            className="input-field text-sm"
            aria-label="Export format"
          >
            <option value="json">JSON</option>
            <option value="csv">CSV</option>
          </select>
          <button
            onClick={() => handleExport(exportFormat)}
            className="btn-secondary"
            aria-label="Export results"
          >
            <Download className="w-4 h-4 mr-2" />
            Export
          </button>
        </div>
      </div>

      {/* Table View */}
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              {results.columns.map((column) => (
                <th
                  key={column}
                  className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                >
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {results.results.map((row, rowIndex) => (
              <tr key={rowIndex} className="hover:bg-gray-50">
                {results.columns.map((column) => {
                  const value = row[column];
                  let displayValue: React.ReactNode = value;

                  // Handle complex objects
                  if (value && typeof value === 'object') {
                    if (Array.isArray(value)) {
                      displayValue = (
                        <span className="text-xs text-gray-500">
                          [{value.length} items]
                        </span>
                      );
                    } else {
                      displayValue = (
                        <span className="text-xs text-gray-500 font-mono">
                          {JSON.stringify(value).substring(0, 50)}
                          {JSON.stringify(value).length > 50 ? '...' : ''}
                        </span>
                      );
                    }
                  } else if (value === null || value === undefined) {
                    displayValue = <span className="text-gray-400 italic">null</span>;
                  }

                  return (
                    <td
                      key={column}
                      className="px-4 py-3 text-sm text-gray-900 max-w-xs truncate"
                      title={typeof value === 'string' ? value : JSON.stringify(value)}
                    >
                      {displayValue}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Graph Visualization Hint */}
      {hasGraphData && (
        <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="flex items-center">
            <Network className="w-5 h-5 text-blue-600 mr-2" />
            <div className="text-sm text-blue-800">
              This query contains graph data. Consider using the Graph Visualization view for better exploration.
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default QueryResults;

