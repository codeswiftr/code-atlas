import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import QueryResults from '@/components/graph/QueryResults';
import { GraphQueryResponse } from '@/types/api';

// Mock URL.createObjectURL and document methods
global.URL.createObjectURL = vi.fn(() => 'blob:mock-url');
global.URL.revokeObjectURL = vi.fn();

describe('QueryResults', () => {
  const mockResults: GraphQueryResponse = {
    results: [
      { name: 'Entity 1', type: 'Concept', id: '1' },
      { name: 'Entity 2', type: 'Tool', id: '2' },
    ],
    columns: ['name', 'type', 'id'],
    row_count: 2,
    execution_time_ms: 12.5,
    message: 'Query executed successfully',
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('loading state', () => {
    it('should show loading indicator when isLoading is true', () => {
      render(<QueryResults results={null} isLoading={true} />);
      
      expect(screen.getByText('Executing query...')).toBeInTheDocument();
    });
  });

  describe('error state', () => {
    it('should display error message when error is provided', () => {
      render(<QueryResults results={null} error="Query syntax error" />);
      
      expect(screen.getByText('Query Error')).toBeInTheDocument();
      expect(screen.getByText('Query syntax error')).toBeInTheDocument();
    });

    it('should not show error when error is null', () => {
      render(<QueryResults results={mockResults} error={null} />);
      
      expect(screen.queryByText('Query Error')).not.toBeInTheDocument();
    });
  });

  describe('empty results', () => {
    it('should show empty message when results are null', () => {
      render(<QueryResults results={null} />);
      
      expect(screen.getByText('No results returned')).toBeInTheDocument();
    });

    it('should show empty message when results array is empty', () => {
      const emptyResults: GraphQueryResponse = {
        results: [],
        columns: [],
        row_count: 0,
        execution_time_ms: 5.0,
        message: 'Query executed successfully',
      };
      
      render(<QueryResults results={emptyResults} />);
      
      expect(screen.getByText('No results returned')).toBeInTheDocument();
    });
  });

  describe('results display', () => {
    it('should display query results in a table', () => {
      render(<QueryResults results={mockResults} />);
      
      expect(screen.getByText('Query Results')).toBeInTheDocument();
      expect(screen.getByText('2 rows in 12.50ms')).toBeInTheDocument();
    });

    it('should display table headers from columns', () => {
      render(<QueryResults results={mockResults} />);
      
      expect(screen.getByText('name')).toBeInTheDocument();
      expect(screen.getByText('type')).toBeInTheDocument();
      expect(screen.getByText('id')).toBeInTheDocument();
    });

    it('should display table rows with data', () => {
      render(<QueryResults results={mockResults} />);
      
      expect(screen.getByText('Entity 1')).toBeInTheDocument();
      expect(screen.getByText('Concept')).toBeInTheDocument();
      expect(screen.getByText('1')).toBeInTheDocument();
      expect(screen.getByText('Entity 2')).toBeInTheDocument();
      expect(screen.getByText('Tool')).toBeInTheDocument();
      expect(screen.getByText('2')).toBeInTheDocument();
    });

    it('should handle singular row count', () => {
      const singleResult: GraphQueryResponse = {
        results: [{ name: 'Entity 1' }],
        columns: ['name'],
        row_count: 1,
        execution_time_ms: 5.0,
        message: 'Query executed successfully',
      };
      
      render(<QueryResults results={singleResult} />);
      
      expect(screen.getByText('1 row in 5.00ms')).toBeInTheDocument();
    });

    it('should display null values as italic "null"', () => {
      const resultsWithNull: GraphQueryResponse = {
        results: [{ name: 'Entity 1', value: null }],
        columns: ['name', 'value'],
        row_count: 1,
        execution_time_ms: 5.0,
        message: 'Query executed successfully',
      };
      
      render(<QueryResults results={resultsWithNull} />);
      
      // Find the null cell - it's rendered as a span with italic class
      const nullCells = screen.getAllByText('null');
      const nullCell = nullCells.find(cell => cell.classList.contains('italic'));
      expect(nullCell).toBeInTheDocument();
      if (nullCell) {
        expect(nullCell).toHaveClass('italic');
      }
    });

    it('should display arrays as item count', () => {
      const resultsWithArray: GraphQueryResponse = {
        results: [{ name: 'Entity 1', tags: ['tag1', 'tag2', 'tag3'] }],
        columns: ['name', 'tags'],
        row_count: 1,
        execution_time_ms: 5.0,
        message: 'Query executed successfully',
      };
      
      render(<QueryResults results={resultsWithArray} />);
      
      expect(screen.getByText('[3 items]')).toBeInTheDocument();
    });

    it('should display objects as JSON string preview', () => {
      const resultsWithObject: GraphQueryResponse = {
        results: [{ name: 'Entity 1', metadata: { key: 'value' } }],
        columns: ['name', 'metadata'],
        row_count: 1,
        execution_time_ms: 5.0,
        message: 'Query executed successfully',
      };
      
      render(<QueryResults results={resultsWithObject} />);
      
      // The JSON is truncated to 50 chars, so check for partial match
      const jsonPreview = screen.getByText(/"key":"value"/);
      expect(jsonPreview).toBeInTheDocument();
      expect(jsonPreview).toHaveClass('font-mono');
    });
  });

  describe('export functionality', () => {
    it('should render export format selector', () => {
      render(<QueryResults results={mockResults} />);
      
      const formatSelect = screen.getByLabelText('Export format');
      expect(formatSelect).toBeInTheDocument();
      expect(formatSelect).toHaveValue('json');
    });

    it('should allow changing export format', () => {
      render(<QueryResults results={mockResults} />);
      
      const formatSelect = screen.getByLabelText('Export format');
      fireEvent.change(formatSelect, { target: { value: 'csv' } });
      
      expect(formatSelect).toHaveValue('csv');
    });

    it('should export JSON when export button is clicked with JSON format', () => {
      const createObjectURLSpy = vi.spyOn(global.URL, 'createObjectURL');
      
      render(<QueryResults results={mockResults} />);
      
      const exportButton = screen.getByLabelText('Export results');
      fireEvent.click(exportButton);
      
      // Verify that export was triggered by checking if createObjectURL was called
      expect(createObjectURLSpy).toHaveBeenCalled();
      
      createObjectURLSpy.mockRestore();
    });

    it('should export CSV when export button is clicked with CSV format', () => {
      const createObjectURLSpy = vi.spyOn(global.URL, 'createObjectURL');
      
      render(<QueryResults results={mockResults} />);
      
      const formatSelect = screen.getByLabelText('Export format');
      fireEvent.change(formatSelect, { target: { value: 'csv' } });
      
      const exportButton = screen.getByLabelText('Export results');
      fireEvent.click(exportButton);
      
      // Verify that export was triggered by checking if createObjectURL was called
      expect(createObjectURLSpy).toHaveBeenCalled();
      
      createObjectURLSpy.mockRestore();
    });

    it('should handle CSV export with special characters', () => {
      const resultsWithSpecialChars: GraphQueryResponse = {
        results: [
          { name: 'Entity, with comma', description: 'Has "quotes" and\nnewlines' },
        ],
        columns: ['name', 'description'],
        row_count: 1,
        execution_time_ms: 5.0,
        message: 'Query executed successfully',
      };
      
      const createObjectURLSpy = vi.spyOn(global.URL, 'createObjectURL');
      
      render(<QueryResults results={resultsWithSpecialChars} />);
      
      const formatSelect = screen.getByLabelText('Export format');
      fireEvent.change(formatSelect, { target: { value: 'csv' } });
      
      const exportButton = screen.getByLabelText('Export results');
      fireEvent.click(exportButton);
      
      // Verify that export was triggered
      expect(createObjectURLSpy).toHaveBeenCalled();
      
      createObjectURLSpy.mockRestore();
    });
  });

  describe('graph data detection', () => {
    it('should show graph visualization hint when results contain path data', () => {
      const resultsWithPath: GraphQueryResponse = {
        results: [{ path: 'some-path-data', name: 'Entity 1' }],
        columns: ['path', 'name'],
        row_count: 1,
        execution_time_ms: 5.0,
        message: 'Query executed successfully',
      };
      
      render(<QueryResults results={resultsWithPath} />);
      
      expect(screen.getByText(/This query contains graph data/)).toBeInTheDocument();
    });

    it('should show graph visualization hint when results contain node data', () => {
      const resultsWithNode: GraphQueryResponse = {
        results: [{ node: 'some-node-data', name: 'Entity 1' }],
        columns: ['node', 'name'],
        row_count: 1,
        execution_time_ms: 5.0,
        message: 'Query executed successfully',
      };
      
      render(<QueryResults results={resultsWithNode} />);
      
      expect(screen.getByText(/This query contains graph data/)).toBeInTheDocument();
    });

    it('should show graph visualization hint when results contain edge data', () => {
      const resultsWithEdge: GraphQueryResponse = {
        results: [{ edge: 'some-edge-data', name: 'Entity 1' }],
        columns: ['edge', 'name'],
        row_count: 1,
        execution_time_ms: 5.0,
        message: 'Query executed successfully',
      };
      
      render(<QueryResults results={resultsWithEdge} />);
      
      expect(screen.getByText(/This query contains graph data/)).toBeInTheDocument();
    });

    it('should not show graph visualization hint for regular data', () => {
      render(<QueryResults results={mockResults} />);
      
      expect(screen.queryByText(/This query contains graph data/)).not.toBeInTheDocument();
    });
  });
});

