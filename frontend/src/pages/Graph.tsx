import React, { useState, useEffect, useRef } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Search, Download, ZoomIn, ZoomOut, RotateCcw, Play, X } from 'lucide-react';

import { apiClient } from '@/api/client';
import { EntityType, EntityResponse, GraphQueryRequest } from '@/types/api';
import QueryBuilder, { SavedQuery } from '@/components/graph/QueryBuilder';
import QueryResults from '@/components/graph/QueryResults';

const GraphPage: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedEntityType, setSelectedEntityType] = useState<EntityType | ''>('');
  const [selectedEntity, setSelectedEntity] = useState<EntityResponse | null>(null);
  const [zoomLevel, setZoomLevel] = useState(1);
  const svgRef = useRef<SVGSVGElement>(null);
  
  // Query interface state
  const [showQueryInterface, setShowQueryInterface] = useState(false);
  const [queryText, setQueryText] = useState('');
  const [queryHistory, setQueryHistory] = useState<SavedQuery[]>([]);
  const [queryError, setQueryError] = useState<string | null>(null);

  // Get graph visualization data
  const { data: graphData, isLoading, refetch } = useQuery({
    queryKey: ['graph-visualization', selectedEntityType],
    queryFn: () => apiClient.getVisualization({
      entity_type: selectedEntityType || undefined,
      max_nodes: 100,
    }),
  });

  // Search entities
  const { data: searchResults } = useQuery({
    queryKey: ['entity-search', searchQuery],
    queryFn: () => searchQuery 
      ? apiClient.searchEntities(searchQuery, { limit: 20 })
      : { results: [], total: 0, query: searchQuery, took_ms: 0, message: '' },
    enabled: searchQuery.length > 0,
  });

  // Load query history from localStorage
  useEffect(() => {
    const saved = localStorage.getItem('code-atlas-query-history');
    if (saved) {
      try {
        setQueryHistory(JSON.parse(saved));
      } catch (e) {
        console.error('Failed to load query history:', e);
      }
    }
  }, []);

  // Query execution
  const queryMutation = useMutation({
    mutationFn: (request: GraphQueryRequest) => apiClient.executeQuery(request),
    onSuccess: () => {
      setQueryError(null);
    },
    onError: (error: any) => {
      setQueryError(error.message || 'Query execution failed');
    },
  });

  const executeQuery = () => {
    if (!queryText.trim()) return;
    
    setQueryError(null);
    queryMutation.mutate({
      query: queryText,
      limit: 100,
      parameters: {},
    });
  };

  const handleLoadQuery = (query: string) => {
    setQueryText(query);
    setQueryError(null);
  };

  const handleSaveQuery = (name: string, query: string) => {
    const newQuery: SavedQuery = {
      id: Date.now().toString(),
      name,
      query,
      createdAt: new Date().toISOString(),
    };
    const updated = [newQuery, ...queryHistory].slice(0, 20); // Keep last 20
    setQueryHistory(updated);
    localStorage.setItem('code-atlas-query-history', JSON.stringify(updated));
  };

  const handleExport = (format: 'json' | 'csv') => {
    if (!graphData) return;
    
    if (format === 'json') {
      const dataStr = JSON.stringify(graphData, null, 2);
      const blob = new Blob([dataStr], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `graph-export-${Date.now()}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } else if (format === 'csv') {
      // Export nodes as CSV
      const headers = ['id', 'label', 'type', 'size', 'color'];
      const rows = graphData.nodes.map(node => [
        node.id,
        node.label,
        node.type,
        node.size,
        node.color,
      ]);
      const csv = [headers.join(','), ...rows.map(row => row.join(','))].join('\n');
      const blob = new Blob([csv], { type: 'text/csv' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `graph-export-${Date.now()}.csv`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    }
  };

  // Simple D3-style force simulation (basic implementation)
  useEffect(() => {
    if (!graphData || !svgRef.current) return;

    const svg = svgRef.current;
    const width = svg.clientWidth;
    const height = svg.clientHeight;

    // Clear existing content
    svg.innerHTML = '';

    // Create force simulation (simplified)
    const nodes = graphData.nodes.map(node => ({
      ...node,
      x: Math.random() * width,
      y: Math.random() * height,
      vx: 0,
      vy: 0,
    }));

    const edges = graphData.edges;

    // Simple force simulation
    const simulate = () => {
      for (let i = 0; i < 50; i++) {
        // Apply forces
        nodes.forEach((node, i) => {
          // Repulsion between nodes
          nodes.forEach((other, j) => {
            if (i !== j) {
              const dx = node.x - other.x;
              const dy = node.y - other.y;
              const distance = Math.sqrt(dx * dx + dy * dy);
              if (distance < 100) {
                const force = (100 - distance) / distance * 0.1;
                node.vx += dx * force;
                node.vy += dy * force;
              }
            }
          });

          // Attraction along edges
          edges.forEach(edge => {
            let other = null;
            if (edge.source === node.id) {
              other = nodes.find(n => n.id === edge.target);
            } else if (edge.target === node.id) {
              other = nodes.find(n => n.id === edge.source);
            }

            if (other) {
              const dx = other.x - node.x;
              const dy = other.y - node.y;
              node.vx += dx * 0.01;
              node.vy += dy * 0.01;
            }
          });

          // Apply velocity with damping
          node.x += node.vx * 0.8;
          node.y += node.vy * 0.8;
          node.vx *= 0.9;
          node.vy *= 0.9;

          // Keep within bounds
          node.x = Math.max(20, Math.min(width - 20, node.x));
          node.y = Math.max(20, Math.min(height - 20, node.y));
        });
      }
    };

    // Render function
    const render = () => {
      svg.innerHTML = '';

      // Create edge elements
      edges.forEach(edge => {
        const sourceNode = nodes.find(n => n.id === edge.source);
        const targetNode = nodes.find(n => n.id === edge.target);
        
        if (sourceNode && targetNode) {
          const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
          line.setAttribute('x1', sourceNode.x.toString());
          line.setAttribute('y1', sourceNode.y.toString());
          line.setAttribute('x2', targetNode.x.toString());
          line.setAttribute('y2', targetNode.y.toString());
          line.setAttribute('stroke', edge.color);
          line.setAttribute('stroke-width', '2');
          line.setAttribute('opacity', '0.6');
          svg.appendChild(line);
        }
      });

      // Create node elements
      nodes.forEach(node => {
        const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        g.setAttribute('transform', `translate(${node.x}, ${node.y})`);
        g.style.cursor = 'pointer';

        const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        circle.setAttribute('r', (node.size * zoomLevel).toString());
        circle.setAttribute('fill', node.color);
        circle.setAttribute('stroke', '#fff');
        circle.setAttribute('stroke-width', '2');
        
        const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        text.setAttribute('text-anchor', 'middle');
        text.setAttribute('dy', '0.3em');
        text.setAttribute('font-size', (12 * zoomLevel).toString());
        text.setAttribute('fill', '#333');
        text.textContent = node.label.length > 15 ? node.label.substring(0, 15) + '...' : node.label;

        g.appendChild(circle);
        g.appendChild(text);
        
        g.addEventListener('click', () => {
          // Find full entity data
          apiClient.getEntity(node.id).then(setSelectedEntity);
        });

        svg.appendChild(g);
      });
    };

    // Run simulation and render
    simulate();
    render();

    // Handle zoom
    const handleWheel = (e: WheelEvent) => {
      e.preventDefault();
      const delta = e.deltaY > 0 ? 0.9 : 1.1;
      setZoomLevel(prev => Math.max(0.1, Math.min(3, prev * delta)));
    };

    svg.addEventListener('wheel', handleWheel);

    return () => {
      svg.removeEventListener('wheel', handleWheel);
    };
  }, [graphData, zoomLevel]);

  const handleZoomIn = () => setZoomLevel(prev => Math.min(3, prev * 1.2));
  const handleZoomOut = () => setZoomLevel(prev => Math.max(0.1, prev / 1.2));
  const handleReset = () => setZoomLevel(1);

  const handleSearch = (entity: EntityResponse) => {
    setSelectedEntity(entity);
    // Center graph on this entity
    refetch();
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Knowledge Graph</h1>
          <p className="text-gray-600">Explore entities and relationships</p>
        </div>
        <div className="flex space-x-3">
          <button
            onClick={() => setShowQueryInterface(!showQueryInterface)}
            className={showQueryInterface ? 'btn-primary' : 'btn-secondary'}
            aria-label={showQueryInterface ? 'Hide query interface' : 'Show query interface'}
          >
            <Play className="w-4 h-4 mr-2" />
            {showQueryInterface ? 'Hide Query' : 'Query Graph'}
          </button>
          <button
            onClick={() => refetch()}
            className="btn-secondary"
            aria-label="Refresh graph"
          >
            <RotateCcw className="w-4 h-4 mr-2" />
            Refresh
          </button>
          <div className="relative">
            <button
              onClick={() => handleExport('json')}
              className="btn-secondary"
              disabled={!graphData}
              aria-label="Export graph data"
            >
              <Download className="w-4 h-4 mr-2" />
              Export
            </button>
          </div>
        </div>
      </div>

      {/* Query Interface */}
      {showQueryInterface && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold">Cypher Query Interface</h3>
            <button
              onClick={() => {
                setShowQueryInterface(false);
                setQueryError(null);
              }}
              className="text-gray-400 hover:text-gray-600"
              aria-label="Close query interface"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
          
          <QueryBuilder
            queryText={queryText}
            onQueryChange={setQueryText}
            onLoadQuery={handleLoadQuery}
            queryHistory={queryHistory}
            onSaveQuery={handleSaveQuery}
          />
          
          <div className="mt-4 flex justify-end">
            <button
              onClick={executeQuery}
              disabled={!queryText.trim() || queryMutation.isPending}
              className="btn-primary"
              aria-label="Execute query"
            >
              <Play className="w-4 h-4 mr-2" />
              {queryMutation.isPending ? 'Executing...' : 'Execute Query'}
            </button>
          </div>
        </div>
      )}

      {/* Query Results */}
      {showQueryInterface && (queryMutation.data || queryError) && (
        <QueryResults
          results={queryMutation.data || null}
          isLoading={queryMutation.isPending}
          error={queryError}
        />
      )}

      {/* Controls */}
      <div className="card">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Search Entities
            </label>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search for entities..."
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
              value={selectedEntityType}
              onChange={(e) => setSelectedEntityType(e.target.value as EntityType | '')}
              className="input-field"
              aria-label="Entity type filter"
            >
              <option value="">All Types</option>
              {Object.values(EntityType).map(type => (
                <option key={type} value={type}>{type}</option>
              ))}
            </select>
          </div>

          <div className="flex items-end space-x-2">
            <button
              onClick={handleZoomOut}
              className="btn-secondary"
              title="Zoom out"
            >
              <ZoomOut className="w-4 h-4" />
            </button>
            <button
              onClick={handleZoomIn}
              className="btn-secondary"
              title="Zoom in"
            >
              <ZoomIn className="w-4 h-4" />
            </button>
            <button
              onClick={handleReset}
              className="btn-secondary"
              title="Reset view"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
          </div>

          <div className="flex items-end text-sm text-gray-600">
            Zoom: {Math.round(zoomLevel * 100)}%
          </div>
        </div>
      </div>

      {/* Search Results */}
      {searchQuery && searchResults && (
        <div className="card">
          <h3 className="font-semibold mb-3">Search Results ({searchResults.total})</h3>
          <div className="space-y-2 max-h-40 overflow-y-auto">
            {searchResults.results.map((result, index) => (
              <div
                key={index}
                onClick={() => handleSearch(result.entity)}
                className="p-2 border border-gray-200 rounded cursor-pointer hover:bg-gray-50"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <span className="font-medium">{result.entity.name}</span>
                    <span className="ml-2 text-xs text-gray-500">({result.entity.type})</span>
                  </div>
                  <span className="text-xs text-gray-500">
                    Score: {result.score.toFixed(2)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Graph Visualization */}
      <div className="card" style={{ height: '600px' }}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold">
            Graph Visualization 
            {graphData && ` (${graphData.node_count} nodes, ${graphData.edge_count} edges)`}
          </h3>
          {isLoading && (
            <div className="flex items-center space-x-2 text-sm text-gray-600">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-atlas-blue-600" />
              <span>Loading graph data...</span>
            </div>
          )}
        </div>
        
        <div className="relative w-full h-full border border-gray-200 rounded-lg bg-gray-50">
          <svg
            ref={svgRef}
            className="w-full h-full"
            style={{ minHeight: '500px' }}
          />
        </div>
      </div>

      {/* Entity Details Modal */}
      {selectedEntity && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Entity Details</h3>
              <button
                onClick={() => setSelectedEntity(null)}
                className="text-gray-400 hover:text-gray-600"
              >
                ×
              </button>
            </div>
            
            <div className="space-y-3">
              <div>
                <label className="text-sm font-medium text-gray-700">Name</label>
                <div className="text-gray-900">{selectedEntity.name}</div>
              </div>
              
              <div>
                <label className="text-sm font-medium text-gray-700">Type</label>
                <div className="text-gray-900">{selectedEntity.type}</div>
              </div>
              
              <div>
                <label className="text-sm font-medium text-gray-700">ID</label>
                <div className="text-sm text-gray-600 font-mono">{selectedEntity.id}</div>
              </div>
              
              {selectedEntity.confidence && (
                <div>
                  <label className="text-sm font-medium text-gray-700">Confidence</label>
                  <div className="text-gray-900">{(selectedEntity.confidence * 100).toFixed(1)}%</div>
                </div>
              )}
              
              {selectedEntity.mention_count && (
                <div>
                  <label className="text-sm font-medium text-gray-700">Mentions</label>
                  <div className="text-gray-900">{selectedEntity.mention_count}</div>
                </div>
              )}
              
              {selectedEntity.source_session && (
                <div>
                  <label className="text-sm font-medium text-gray-700">Source Session</label>
                  <div className="text-sm text-gray-600">{selectedEntity.source_session}</div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default GraphPage;