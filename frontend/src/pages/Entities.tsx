import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Search, Filter, Database, FileText, Wrench, Lightbulb, CheckCircle } from 'lucide-react';

import { apiClient } from '@/api/client';
import { EntityType } from '@/types/api';

const EntitiesPage: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedType, setSelectedType] = useState<EntityType | ''>('');
  const [minConfidence, setMinConfidence] = useState(0);
  const [page, setPage] = useState(1);

  // List entities
  const { data: entitiesData, isLoading, refetch } = useQuery({
    queryKey: ['entities', selectedType, searchQuery, minConfidence, page],
    queryFn: () => apiClient.listEntities({
      entity_type: selectedType || undefined,
      search: searchQuery || undefined,
      min_confidence: minConfidence,
      page,
      page_size: 20,
    }),
  });

  const getEntityIcon = (type: EntityType) => {
    switch (type) {
      case EntityType.SESSION:
        return FileText;
      case EntityType.CONCEPT:
        return Lightbulb;
      case EntityType.FILE:
        return Database;
      case EntityType.TOOL:
        return Wrench;
      case EntityType.PROBLEM:
        return CheckCircle;
      case EntityType.SOLUTION:
        return CheckCircle;
      default:
        return Database;
    }
  };

  const getEntityColor = (type: EntityType) => {
    switch (type) {
      case EntityType.SESSION:
        return 'text-atlas-blue-electric';
      case EntityType.CONCEPT:
        return 'text-atlas-purple';
      case EntityType.FILE:
        return 'text-atlas-green-emerald';
      case EntityType.TOOL:
        return 'text-atlas-orange';
      case EntityType.PROBLEM:
        return 'text-atlas-red';
      case EntityType.SOLUTION:
        return 'text-atlas-green-emerald';
      default:
        return 'text-gray-600';
    }
  };

  const handleSearch = () => {
    setPage(1);
    refetch();
  };

  const handlePageChange = (newPage: number) => {
    setPage(newPage);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Entities</h1>
          <p className="text-gray-600">Browse and search extracted entities</p>
        </div>
        <button
          onClick={() => refetch()}
          className="btn-secondary"
          disabled={isLoading}
          aria-label="Refresh entities list"
        >
          <Filter className="w-4 h-4 mr-2" />
          Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="card">
        <h3 className="font-semibold mb-4">Filters</h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Search
            </label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="Search entities..."
                className="input-field pl-10"
                aria-label="Search entities input"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Entity Type
            </label>
            <select
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value as EntityType | '')}
              className="input-field"
              aria-label="Entity type filter"
            >
              <option value="">All Types</option>
              {Object.values(EntityType).map(type => (
                <option key={type} value={type}>{type}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Min Confidence
            </label>
            <input
              type="number"
              min="0"
              max="1"
              step="0.1"
              value={minConfidence}
              onChange={(e) => setMinConfidence(parseFloat(e.target.value))}
              className="input-field"
              aria-label="Minimum confidence filter"
            />
          </div>

          <div className="flex items-end">
            <button 
              onClick={handleSearch} 
              className="btn-primary w-full"
              aria-label="Apply filters"
            >
              Apply Filters
            </button>
          </div>
        </div>
      </div>

      {/* Results */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold">
            Entities {entitiesData && `(${entitiesData.total} total)`}
          </h3>
          {isLoading && (
            <div className="flex items-center space-x-2 text-sm text-gray-600">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-atlas-blue-600" />
              <span>Loading entities...</span>
            </div>
          )}
        </div>

        {!entitiesData || entitiesData.entities.length === 0 ? (
          <div className="text-center py-8">
            <Database className="w-12 h-12 mx-auto text-gray-400" />
            <p className="text-gray-600 mt-2">No entities found</p>
          </div>
        ) : (
          <div className="space-y-3">
            {entitiesData.entities.map((entity) => {
              const Icon = getEntityIcon(entity.type);
              return (
                <div
                  key={entity.id}
                  className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-start space-x-3">
                      <div className={`p-2 rounded-lg bg-gray-100 ${getEntityColor(entity.type)}`}>
                        <Icon className="w-5 h-5" />
                      </div>
                      <div className="flex-1">
                        <h4 className="font-semibold text-gray-900">
                          {entity.name}
                        </h4>
                        <div className="flex items-center space-x-4 mt-1 text-sm text-gray-600">
                          <span className="capitalize">{entity.type}</span>
                          {entity.confidence && (
                            <span>Confidence: {(entity.confidence * 100).toFixed(1)}%</span>
                          )}
                          {entity.mention_count && (
                            <span>Mentions: {entity.mention_count}</span>
                          )}
                        </div>
                        {entity.source_session && (
                          <div className="text-xs text-gray-500 mt-1">
                            Source: {entity.source_session}
                          </div>
                        )}
                      </div>
                    </div>
                    
                    <div className="text-right">
                      <div className="text-xs text-gray-500">
                        ID: {entity.id.substring(0, 8)}...
                      </div>
                      {entity.created_at && (
                        <div className="text-xs text-gray-500">
                          {new Date(entity.created_at).toLocaleDateString()}
                        </div>
                      )}
                    </div>
                  </div>

                  {entity.properties && Object.keys(entity.properties).length > 0 && (
                    <div className="mt-3 pt-3 border-t border-gray-200">
                      <div className="text-sm font-medium text-gray-700 mb-2">Properties</div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
                        {Object.entries(entity.properties).map(([key, value]) => (
                          <div key={key} className="flex">
                            <span className="font-medium text-gray-600 mr-2">{key}:</span>
                            <span className="text-gray-900 truncate">
                              {typeof value === 'string' ? value : JSON.stringify(value)}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* Pagination */}
        {entitiesData && entitiesData.total > entitiesData.page_size && (
          <div className="flex items-center justify-between mt-6 pt-4 border-t border-gray-200">
            <div className="text-sm text-gray-600">
              Showing {((page - 1) * entitiesData.page_size) + 1} to{' '}
              {Math.min(page * entitiesData.page_size, entitiesData.total)} of{' '}
              {entitiesData.total} entities
            </div>
            
            <div className="flex space-x-2">
              <button
                onClick={() => handlePageChange(page - 1)}
                disabled={page === 1}
                className="btn-secondary disabled:opacity-50 disabled:cursor-not-allowed"
                aria-label="Previous page"
              >
                Previous
              </button>
              
              <span className="px-3 py-1 text-sm text-gray-600" aria-label={`Page ${page} of ${Math.ceil(entitiesData.total / entitiesData.page_size)}`}>
                Page {page} of {Math.ceil(entitiesData.total / entitiesData.page_size)}
              </span>
              
              <button
                onClick={() => handlePageChange(page + 1)}
                disabled={page >= Math.ceil(entitiesData.total / entitiesData.page_size)}
                className="btn-secondary disabled:opacity-50 disabled:cursor-not-allowed"
                aria-label="Next page"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default EntitiesPage;