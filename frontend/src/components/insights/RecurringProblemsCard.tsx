import React from 'react';
import { AlertTriangle } from 'lucide-react';
import { EntityResponse } from '@/types/api';

interface RecurringProblem {
  entity: EntityResponse;
  session_count: number;
}

interface RecurringProblemsCardProps {
  problems: RecurringProblem[];
  isLoading?: boolean;
  error?: string | null;
}

const RecurringProblemsCard: React.FC<RecurringProblemsCardProps> = ({ problems, isLoading, error }) => {
  if (isLoading) {
    return (
      <div className="card">
        <div className="text-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-atlas-blue-600 mx-auto" />
          <p className="text-gray-600 mt-2">Loading recurring problems...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card">
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
          <div className="text-red-800 font-medium">Error</div>
          <div className="text-red-600 text-sm mt-1">{error}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center">
          <AlertTriangle className="w-5 h-5 text-red-600 mr-2" />
          <h3 className="font-semibold">Recurring Problems</h3>
        </div>
        <span className="text-sm text-gray-600">{problems.length} problems</span>
      </div>

      {problems.length === 0 ? (
        <div className="text-center py-8 text-gray-500">No recurring problems found</div>
      ) : (
        <div className="space-y-3 max-h-96 overflow-y-auto">
          {problems.map((problem, index) => (
            <div
              key={problem.entity.id}
              className="p-3 border border-red-200 rounded-lg bg-red-50"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center space-x-2">
                    <span className="text-sm font-medium text-gray-500">#{index + 1}</span>
                    <div className="font-medium text-gray-900">{problem.entity.name}</div>
                  </div>
                  {problem.entity.properties?.description && (
                    <div className="text-sm text-gray-600 mt-1">
                      {problem.entity.properties.description}
                    </div>
                  )}
                </div>
                <div className="ml-4 text-right">
                  <div className="text-lg font-bold text-red-600">{problem.session_count}</div>
                  <div className="text-xs text-gray-500">sessions</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default RecurringProblemsCard;

