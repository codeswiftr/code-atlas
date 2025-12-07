import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Download, RefreshCw } from 'lucide-react';

import { apiClient } from '@/api/client';
import TopEntitiesCard from '@/components/insights/TopEntitiesCard';
import RecurringProblemsCard from '@/components/insights/RecurringProblemsCard';
import PopularToolsCard from '@/components/insights/PopularToolsCard';
import TrendsChart from '@/components/insights/TrendsChart';

const InsightsPage: React.FC = () => {
  const [refreshKey, setRefreshKey] = useState(0);

  // Fetch insights data
  const { data: topEntities, isLoading: topEntitiesLoading, error: topEntitiesError } = useQuery({
    queryKey: ['top-entities', refreshKey],
    queryFn: () => apiClient.getTopEntities({ limit: 20 }),
  });

  const { data: recurringProblems, isLoading: problemsLoading, error: problemsError } = useQuery({
    queryKey: ['recurring-problems', refreshKey],
    queryFn: () => apiClient.getRecurringProblems({ min_sessions: 2, limit: 20 }),
  });

  const { data: popularTools, isLoading: toolsLoading, error: toolsError } = useQuery({
    queryKey: ['popular-tools', refreshKey],
    queryFn: () => apiClient.getPopularTools({ limit: 20 }),
  });

  const { data: trends, isLoading: trendsLoading, error: trendsError } = useQuery({
    queryKey: ['trends', refreshKey],
    queryFn: () => apiClient.getTrends({ days: 30 }),
  });

  const { data: report, isLoading: reportLoading } = useQuery({
    queryKey: ['insight-report', refreshKey],
    queryFn: () => apiClient.getInsightReport(),
  });

  const handleRefresh = () => {
    setRefreshKey(prev => prev + 1);
  };

  const handleExportReport = () => {
    if (!report) return;

    const dataStr = JSON.stringify(report, null, 2);
    const blob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `insight-report-${Date.now()}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Insights & Reports</h1>
          <p className="text-gray-600">Actionable intelligence from your knowledge graph</p>
        </div>
        <div className="flex space-x-3">
          <button
            onClick={handleRefresh}
            className="btn-secondary"
            aria-label="Refresh insights"
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </button>
          <button
            onClick={handleExportReport}
            className="btn-primary"
            disabled={!report || reportLoading}
            aria-label="Export insight report"
          >
            <Download className="w-4 h-4 mr-2" />
            Export Report
          </button>
        </div>
      </div>

      {/* Top Entities and Recurring Problems */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <TopEntitiesCard
          entities={topEntities?.entities || []}
          isLoading={topEntitiesLoading}
          error={topEntitiesError ? (topEntitiesError as Error).message || 'Failed to load top entities' : null}
        />
        <RecurringProblemsCard
          problems={recurringProblems?.problems || []}
          isLoading={problemsLoading}
          error={problemsError ? (problemsError as Error).message || 'Failed to load recurring problems' : null}
        />
      </div>

      {/* Popular Tools and Trends */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <PopularToolsCard
          tools={popularTools?.tools || []}
          isLoading={toolsLoading}
          error={toolsError ? (toolsError as Error).message || 'Failed to load popular tools' : null}
        />
        <TrendsChart
          trends={trends?.trends || []}
          isLoading={trendsLoading}
          error={trendsError ? (trendsError as Error).message || 'Failed to load trends' : null}
        />
      </div>

      {/* Concept Relationships */}
      {recurringProblems && recurringProblems.problems.length > 0 && (
        <div className="card">
          <h3 className="font-semibold mb-4">Key Insights</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <div className="text-2xl font-bold text-blue-600">
                {topEntities?.total || 0}
              </div>
              <div className="text-sm text-gray-600 mt-1">Top Entities Tracked</div>
            </div>
            <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
              <div className="text-2xl font-bold text-red-600">
                {recurringProblems?.total || 0}
              </div>
              <div className="text-sm text-gray-600 mt-1">Recurring Problems</div>
            </div>
            <div className="p-4 bg-orange-50 border border-orange-200 rounded-lg">
              <div className="text-2xl font-bold text-orange-600">
                {popularTools?.total || 0}
              </div>
              <div className="text-sm text-gray-600 mt-1">Popular Tools</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default InsightsPage;

