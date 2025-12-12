import React, { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Send, Loader2, MessageSquare } from 'lucide-react';
import { apiClient } from '@/api/client';
import { RAGQueryRequest, RAGQueryResponse, EntityType } from '@/types/api';

const RAG: React.FC = () => {
  const [question, setQuestion] = useState('');
  const [entityType, setEntityType] = useState<EntityType | ''>('');

  const ragMutation = useMutation({
    mutationFn: (request: RAGQueryRequest) => apiClient.ragQuery(request),
    onError: (error: Error) => {
      console.error('RAG query failed:', error);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;

    const request: RAGQueryRequest = {
      question: question.trim(),
      entity_type: entityType || undefined,
      context_limit: 5,
      include_sources: true,
    };

    ragMutation.mutate(request);
  };

  const result: RAGQueryResponse | undefined = ragMutation.data;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">RAG Query</h1>
        <p className="mt-2 text-gray-600">
          Ask natural language questions about your codebase knowledge graph
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label htmlFor="question" className="block text-sm font-medium text-gray-700 mb-2">
            Question
          </label>
          <textarea
            id="question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g., What problems keep recurring in my sessions?"
            rows={4}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-atlas-blue-500 focus:border-transparent"
          />
        </div>

        <div>
          <label htmlFor="entity_type" className="block text-sm font-medium text-gray-700 mb-2">
            Filter by Entity Type (Optional)
          </label>
          <select
            id="entity_type"
            value={entityType}
            onChange={(e) => setEntityType(e.target.value as EntityType | '')}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-atlas-blue-500"
          >
            <option value="">All Types</option>
            <option value={EntityType.CONCEPT}>Concept</option>
            <option value={EntityType.FILE}>File</option>
            <option value={EntityType.TOOL}>Tool</option>
            <option value={EntityType.PROBLEM}>Problem</option>
            <option value={EntityType.SOLUTION}>Solution</option>
          </select>
        </div>

        <button
          type="submit"
          disabled={!question.trim() || ragMutation.isPending}
          className="inline-flex items-center px-6 py-3 bg-atlas-blue-600 text-white rounded-lg hover:bg-atlas-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {ragMutation.isPending ? (
            <>
              <Loader2 className="w-5 h-5 mr-2 animate-spin" />
              Processing...
            </>
          ) : (
            <>
              <Send className="w-5 h-5 mr-2" />
              Ask Question
            </>
          )}
        </button>
      </form>

      {ragMutation.isError && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-red-800">
            Error: {ragMutation.error instanceof Error ? ragMutation.error.message : 'Unknown error'}
          </p>
        </div>
      )}

      {result && (
        <div className="space-y-6">
          <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
            <div className="flex items-center mb-4">
              <MessageSquare className="w-6 h-6 text-atlas-blue-600 mr-2" />
              <h2 className="text-xl font-semibold text-gray-900">Answer</h2>
              <span className="ml-auto text-sm text-gray-500">
                Confidence: {(result.confidence * 100).toFixed(0)}%
              </span>
            </div>
            <p className="text-gray-700 whitespace-pre-wrap">{result.answer}</p>
            <p className="mt-4 text-sm text-gray-500">
              Query took {result.execution_time_ms.toFixed(0)}ms
            </p>
          </div>

          {result.sources.length > 0 && (
            <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Sources</h3>
              <ul className="space-y-2">
                {result.sources.map((sourceId) => (
                  <li key={sourceId} className="text-sm text-gray-600">
                    {sourceId}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {result.context_entities.length > 0 && (
            <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">
                Context Entities ({result.context_entities.length})
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {result.context_entities.map((entity) => (
                  <div
                    key={entity.entity_id}
                    className="p-3 bg-gray-50 rounded-lg border border-gray-200"
                  >
                    <p className="font-medium text-gray-900">{entity.entity_name}</p>
                    <p className="text-sm text-gray-500">{entity.entity_type}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default RAG;
