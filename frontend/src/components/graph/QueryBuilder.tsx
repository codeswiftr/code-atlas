import React, { useState } from 'react';
import { FileText, ChevronDown, ChevronUp } from 'lucide-react';

export interface SavedQuery {
  id: string;
  name: string;
  query: string;
  parameters?: Record<string, any>;
  createdAt: string;
}

interface QueryBuilderProps {
  queryText: string;
  onQueryChange: (query: string) => void;
  onLoadQuery: (query: string, parameters?: Record<string, any>) => void;
  queryHistory: SavedQuery[];
  onSaveQuery: (name: string, query: string) => void;
}

const QUERY_TEMPLATES = [
  {
    name: 'Find All Entities',
    query: 'MATCH (e)\nRETURN e.name as name, labels(e) as type, e.id as id\nLIMIT 100',
    description: 'Get all entities in the graph'
  },
  {
    name: 'Find Entities by Type',
    query: 'MATCH (e:Concept)\nRETURN e.name as name, e.id as id\nLIMIT 50',
    description: 'Find all Concept entities'
  },
  {
    name: 'Find Relationships',
    query: 'MATCH (a)-[r]->(b)\nRETURN a.name as source, type(r) as relationship, b.name as target\nLIMIT 100',
    description: 'Get all relationships between entities'
  },
  {
    name: 'Find Path Between Entities',
    query: 'MATCH path = (a {name: $entity1})-[*1..3]-(b {name: $entity2})\nRETURN path\nLIMIT 10',
    description: 'Find paths between two entities (up to 3 hops)',
    parameters: { entity1: '', entity2: '' }
  },
  {
    name: 'Find Most Connected Entities',
    query: 'MATCH (e)-[r]-()\nWITH e, count(r) as connections\nORDER BY connections DESC\nRETURN e.name as name, connections\nLIMIT 20',
    description: 'Find entities with the most relationships'
  },
  {
    name: 'Find Problems and Solutions',
    query: 'MATCH (p:Problem)-[r:SOLVES]->(s:Solution)\nRETURN p.name as problem, s.name as solution\nLIMIT 50',
    description: 'Find problems and their solutions'
  },
  {
    name: 'Find Entities by Confidence',
    query: 'MATCH (e)\nWHERE e.confidence >= $minConfidence\nRETURN e.name as name, e.confidence as confidence\nORDER BY confidence DESC\nLIMIT 50',
    description: 'Find entities above a confidence threshold',
    parameters: { minConfidence: 0.8 }
  }
];

const QueryBuilder: React.FC<QueryBuilderProps> = ({
  queryText,
  onQueryChange,
  onLoadQuery,
  queryHistory,
  onSaveQuery,
}) => {
  const [showTemplates, setShowTemplates] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [saveQueryName, setSaveQueryName] = useState('');
  const [showSaveDialog, setShowSaveDialog] = useState(false);

  const handleTemplateSelect = (template: typeof QUERY_TEMPLATES[0]) => {
    onLoadQuery(template.query, template.parameters);
    setShowTemplates(false);
  };

  const handleHistorySelect = (savedQuery: SavedQuery) => {
    onLoadQuery(savedQuery.query, savedQuery.parameters);
    setShowHistory(false);
  };

  const handleSave = () => {
    if (saveQueryName.trim() && queryText.trim()) {
      onSaveQuery(saveQueryName.trim(), queryText);
      setSaveQueryName('');
      setShowSaveDialog(false);
    }
  };

  return (
    <div className="space-y-3">
      {/* Query Input */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Cypher Query
        </label>
        <textarea
          value={queryText}
          onChange={(e) => onQueryChange(e.target.value)}
          placeholder="Enter a Cypher query (read-only queries only)..."
          className="input-field font-mono text-sm"
          rows={8}
          aria-label="Cypher query input"
        />
        <p className="text-xs text-gray-500 mt-1">
          Only read queries are allowed (MATCH, RETURN, etc.). CREATE, DELETE, SET, REMOVE, MERGE, DROP are not permitted.
        </p>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between">
        <div className="flex space-x-2">
          {/* Templates Dropdown */}
          <div className="relative">
            <button
              onClick={() => {
                setShowTemplates(!showTemplates);
                setShowHistory(false);
              }}
              className="btn-secondary text-sm"
              aria-label="Show query templates"
            >
              <FileText className="w-4 h-4 mr-1" />
              Templates
              {showTemplates ? <ChevronUp className="w-4 h-4 ml-1" /> : <ChevronDown className="w-4 h-4 ml-1" />}
            </button>
            
            {showTemplates && (
              <div className="absolute z-10 mt-1 w-80 bg-white border border-gray-200 rounded-lg shadow-lg max-h-96 overflow-y-auto">
                <div className="p-2">
                  {QUERY_TEMPLATES.map((template, index) => (
                    <button
                      key={index}
                      onClick={() => handleTemplateSelect(template)}
                      className="w-full text-left p-2 hover:bg-gray-50 rounded text-sm"
                    >
                      <div className="font-medium text-gray-900">{template.name}</div>
                      <div className="text-xs text-gray-500 mt-1">{template.description}</div>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* History Dropdown */}
          {queryHistory.length > 0 && (
            <div className="relative">
              <button
                onClick={() => {
                  setShowHistory(!showHistory);
                  setShowTemplates(false);
                }}
                className="btn-secondary text-sm"
                aria-label="Show query history"
              >
                History ({queryHistory.length})
                {showHistory ? <ChevronUp className="w-4 h-4 ml-1" /> : <ChevronDown className="w-4 h-4 ml-1" />}
              </button>
              
              {showHistory && (
                <div className="absolute z-10 mt-1 w-80 bg-white border border-gray-200 rounded-lg shadow-lg max-h-96 overflow-y-auto">
                  <div className="p-2">
                    {queryHistory.map((savedQuery) => (
                      <button
                        key={savedQuery.id}
                        onClick={() => handleHistorySelect(savedQuery)}
                        className="w-full text-left p-2 hover:bg-gray-50 rounded text-sm"
                      >
                        <div className="font-medium text-gray-900">{savedQuery.name}</div>
                        <div className="text-xs text-gray-500 mt-1 font-mono truncate">
                          {savedQuery.query.substring(0, 60)}...
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Save Query */}
          <button
            onClick={() => setShowSaveDialog(true)}
            className="btn-secondary text-sm"
            disabled={!queryText.trim()}
            aria-label="Save query"
          >
            Save Query
          </button>
        </div>
      </div>

      {/* Save Dialog */}
      {showSaveDialog && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold mb-4">Save Query</h3>
            <input
              type="text"
              value={saveQueryName}
              onChange={(e) => setSaveQueryName(e.target.value)}
              placeholder="Query name..."
              className="input-field w-full mb-4"
              onKeyPress={(e) => {
                if (e.key === 'Enter') {
                  handleSave();
                }
              }}
              aria-label="Query name input"
            />
            <div className="flex justify-end space-x-2">
              <button
                onClick={() => {
                  setShowSaveDialog(false);
                  setSaveQueryName('');
                }}
                className="btn-secondary"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                className="btn-primary"
                disabled={!saveQueryName.trim()}
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default QueryBuilder;

