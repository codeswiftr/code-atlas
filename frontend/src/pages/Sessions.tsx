import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  FileText,
  Play,
  RefreshCw,
  CheckCircle,
  XCircle,
  Clock,
  Search,
  ChevronDown,
  X
} from 'lucide-react';

import { apiClient } from '@/api/client';
import {
  JobStatus,
  SessionProcessRequest
} from '@/types/api';

const SessionsPage: React.FC = () => {
  const [selectedSessions, setSelectedSessions] = useState<string[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [projectFilter, setProjectFilter] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [cancelJobId, setCancelJobId] = useState<string | null>(null);

  const queryClient = useQueryClient();

  // Discover sessions
  const { data: sessionsData, isLoading: sessionsLoading, refetch: refetchSessions } = useQuery({
    queryKey: ['sessions', searchTerm, projectFilter],
    queryFn: () => apiClient.discoverSessions({
      limit: 100,
      project_filter: projectFilter || undefined,
    }),
  });

  // List jobs
  const { data: jobs } = useQuery({
    queryKey: ['jobs'],
    queryFn: () => apiClient.listJobs(),
    refetchInterval: 5000, // Poll every 5 seconds
  });

  // Process sessions mutation
  const processMutation = useMutation({
    mutationFn: (request: SessionProcessRequest) => apiClient.processSessions(request),
    onSuccess: () => {
      setSelectedSessions([]);
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
    },
  });

  // Cancel job mutation
  const cancelJobMutation = useMutation({
    mutationFn: (jobId: string) => apiClient.cancelJob(jobId),
    onSuccess: () => {
      setCancelJobId(null);
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
    },
  });

  const filteredSessions = sessionsData?.sessions.filter(session => 
    session.filename.toLowerCase().includes(searchTerm.toLowerCase()) &&
    session.project_name.toLowerCase().includes(projectFilter.toLowerCase())
  ) || [];

  const handleSessionSelect = (sessionPath: string) => {
    setSelectedSessions(prev => 
      prev.includes(sessionPath)
        ? prev.filter(s => s !== sessionPath)
        : [...prev, sessionPath]
    );
  };

  const handleProcessSessions = () => {
    if (selectedSessions.length === 0) return;

    processMutation.mutate({
      session_paths: selectedSessions,
      use_llm: true,
      dry_run: false,
      max_cost_per_session: 0.02,
    });
  };

  const getStatusIcon = (status: JobStatus) => {
    switch (status) {
      case JobStatus.PENDING:
        return <Clock className="w-4 h-4 text-yellow-500" />;
      case JobStatus.RUNNING:
        return <RefreshCw className="w-4 h-4 text-blue-500 animate-spin" />;
      case JobStatus.COMPLETED:
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case JobStatus.FAILED:
        return <XCircle className="w-4 h-4 text-red-500" />;
      default:
        return <Clock className="w-4 h-4 text-gray-500" />;
    }
  };

  const getStatusBadge = (status: JobStatus) => {
    const baseClasses = "status-badge";
    switch (status) {
      case JobStatus.PENDING:
        return `${baseClasses} status-pending`;
      case JobStatus.RUNNING:
        return `${baseClasses} status-running`;
      case JobStatus.COMPLETED:
        return `${baseClasses} status-completed`;
      case JobStatus.FAILED:
        return `${baseClasses} status-failed`;
      default:
        return baseClasses;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Sessions</h1>
          <p className="text-gray-600">Discover and process Claude Code session files</p>
        </div>
        <div className="flex space-x-3">
          <button
            onClick={() => refetchSessions()}
            className="btn-secondary"
            disabled={sessionsLoading}
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${sessionsLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <button
            onClick={handleProcessSessions}
            className="btn-primary"
            disabled={selectedSessions.length === 0 || processMutation.isPending}
          >
            <Play className="w-4 h-4 mr-2" />
            Process {selectedSessions.length} Sessions
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold">Filters</h3>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="text-gray-500 hover:text-gray-700"
          >
            <ChevronDown className={`w-4 h-4 transform transition-transform ${showFilters ? 'rotate-180' : ''}`} />
          </button>
        </div>
        
        {showFilters && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Search Sessions
              </label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  placeholder="Search filenames..."
                  className="input-field pl-10"
                />
              </div>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Project Filter
              </label>
              <input
                type="text"
                value={projectFilter}
                onChange={(e) => setProjectFilter(e.target.value)}
                placeholder="Filter by project..."
                className="input-field"
              />
            </div>

            <div className="flex items-end">
              <div className="text-sm text-gray-600">
                {filteredSessions.length} sessions found
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Processing Jobs */}
      {jobs && jobs.length > 0 && (
        <div className="card">
          <h3 className="font-semibold mb-4">Processing Jobs</h3>
          <div className="space-y-3">
            {jobs.map((job) => (
              <div key={job.job_id} className="border border-gray-200 rounded-lg p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    {getStatusIcon(job.status)}
                    <div>
                      <div className="font-medium">{job.job_id}</div>
                      <div className="text-sm text-gray-600">
                        {job.processed_sessions} / {job.total_sessions} sessions processed
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center space-x-3">
                    <div className="text-right">
                      <span className={getStatusBadge(job.status)}>
                        {job.status}
                      </span>
                      {job.current_session && (
                        <div className="text-sm text-gray-600 mt-1">
                          Current: {job.current_session}
                        </div>
                      )}
                    </div>
                    {(job.status === JobStatus.PENDING || job.status === JobStatus.RUNNING) && (
                      <button
                        onClick={() => setCancelJobId(job.job_id)}
                        className="btn-secondary text-sm text-red-600 hover:bg-red-50"
                        aria-label={`Cancel job ${job.job_id}`}
                      >
                        <X className="w-4 h-4 mr-1" />
                        Cancel
                      </button>
                    )}
                  </div>
                </div>
                
                {job.error_message && (
                  <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
                    {job.error_message}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Sessions List */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold">
            Sessions ({filteredSessions.length})
          </h3>
          <div className="flex items-center space-x-2">
            <input
              type="checkbox"
              id="select-all"
              checked={selectedSessions.length === filteredSessions.length && filteredSessions.length > 0}
              onChange={(e) => {
                if (e.target.checked) {
                  setSelectedSessions(filteredSessions.map(s => s.path));
                } else {
                  setSelectedSessions([]);
                }
              }}
              className="rounded"
            />
            <label htmlFor="select-all" className="text-sm text-gray-600">
              Select All
            </label>
          </div>
        </div>

        {sessionsLoading ? (
          <div className="text-center py-8">
            <RefreshCw className="w-8 h-8 animate-spin mx-auto text-gray-400" />
            <p className="text-gray-600 mt-2">Discovering sessions...</p>
          </div>
        ) : filteredSessions.length === 0 ? (
          <div className="text-center py-8">
            <FileText className="w-12 h-12 mx-auto text-gray-400" />
            <p className="text-gray-600 mt-2">No sessions found</p>
          </div>
        ) : (
          <div className="space-y-2">
            {filteredSessions.map((session) => (
              <div
                key={session.path}
                className={`border rounded-lg p-4 cursor-pointer transition-colors ${
                  selectedSessions.includes(session.path)
                    ? 'border-atlas-blue-500 bg-atlas-blue-50'
                    : 'border-gray-200 hover:border-gray-300'
                }`}
                onClick={() => handleSessionSelect(session.path)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <input
                      type="checkbox"
                      checked={selectedSessions.includes(session.path)}
                      onChange={() => handleSessionSelect(session.path)}
                      className="rounded"
                    />
                    <FileText className="w-5 h-5 text-gray-400" />
                    <div>
                      <div className="font-medium">{session.filename}</div>
                      <div className="text-sm text-gray-600">
                        {session.project_name} • {(session.size_bytes / 1024).toFixed(1)} KB
                      </div>
                    </div>
                  </div>
                  <div className="text-sm text-gray-500">
                    {new Date(session.modified_at).toLocaleDateString()}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Cancel Job Confirmation Dialog */}
      {cancelJobId && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold mb-4">Cancel Job</h3>
            <p className="text-gray-600 mb-6">
              Are you sure you want to cancel job <span className="font-mono font-medium">{cancelJobId}</span>?
              This action cannot be undone.
            </p>
            <div className="flex justify-end space-x-3">
              <button
                onClick={() => setCancelJobId(null)}
                className="btn-secondary"
                disabled={cancelJobMutation.isPending}
              >
                Keep Running
              </button>
              <button
                onClick={() => {
                  cancelJobMutation.mutate(cancelJobId);
                }}
                className="btn-primary bg-red-600 hover:bg-red-700"
                disabled={cancelJobMutation.isPending}
                aria-label="Confirm cancel job"
              >
                {cancelJobMutation.isPending ? 'Cancelling...' : 'Cancel Job'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SessionsPage;