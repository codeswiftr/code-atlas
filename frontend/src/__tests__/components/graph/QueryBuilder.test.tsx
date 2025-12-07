import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import QueryBuilder, { SavedQuery } from '@/components/graph/QueryBuilder';

describe('QueryBuilder', () => {
  const mockOnQueryChange = vi.fn();
  const mockOnLoadQuery = vi.fn();
  const mockOnSaveQuery = vi.fn();

  const defaultProps = {
    queryText: '',
    onQueryChange: mockOnQueryChange,
    onLoadQuery: mockOnLoadQuery,
    queryHistory: [],
    onSaveQuery: mockOnSaveQuery,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('should render query input field', () => {
      render(<QueryBuilder {...defaultProps} />);
      
      expect(screen.getByLabelText('Cypher query input')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('Enter a Cypher query (read-only queries only)...')).toBeInTheDocument();
    });

    it('should display initial query text', () => {
      render(<QueryBuilder {...defaultProps} queryText="MATCH (e) RETURN e" />);
      
      const textarea = screen.getByLabelText('Cypher query input');
      expect(textarea).toHaveValue('MATCH (e) RETURN e');
    });

    it('should render templates button', () => {
      render(<QueryBuilder {...defaultProps} />);
      
      expect(screen.getByLabelText('Show query templates')).toBeInTheDocument();
      expect(screen.getByText('Templates')).toBeInTheDocument();
    });

    it('should render save query button', () => {
      render(<QueryBuilder {...defaultProps} />);
      
      expect(screen.getByLabelText('Save query')).toBeInTheDocument();
      expect(screen.getByText('Save Query')).toBeInTheDocument();
    });

    it('should not render history button when history is empty', () => {
      render(<QueryBuilder {...defaultProps} queryHistory={[]} />);
      
      expect(screen.queryByText(/History/)).not.toBeInTheDocument();
    });

    it('should render history button when history exists', () => {
      const history: SavedQuery[] = [
        {
          id: '1',
          name: 'Test Query',
          query: 'MATCH (e) RETURN e',
          createdAt: '2025-01-01T00:00:00Z',
        },
      ];
      
      render(<QueryBuilder {...defaultProps} queryHistory={history} />);
      
      expect(screen.getByLabelText('Show query history')).toBeInTheDocument();
      expect(screen.getByText('History (1)')).toBeInTheDocument();
    });
  });

  describe('query input', () => {
    it('should call onQueryChange when text changes', () => {
      render(<QueryBuilder {...defaultProps} />);
      
      const textarea = screen.getByLabelText('Cypher query input');
      fireEvent.change(textarea, { target: { value: 'MATCH (e) RETURN e' } });
      
      expect(mockOnQueryChange).toHaveBeenCalledWith('MATCH (e) RETURN e');
    });

    it('should disable save button when query is empty', () => {
      render(<QueryBuilder {...defaultProps} queryText="" />);
      
      const saveButton = screen.getByLabelText('Save query');
      expect(saveButton).toBeDisabled();
    });

    it('should enable save button when query has text', () => {
      render(<QueryBuilder {...defaultProps} queryText="MATCH (e) RETURN e" />);
      
      const saveButton = screen.getByLabelText('Save query');
      expect(saveButton).not.toBeDisabled();
    });
  });

  describe('templates', () => {
    it('should show templates dropdown when clicked', () => {
      render(<QueryBuilder {...defaultProps} />);
      
      const templatesButton = screen.getByLabelText('Show query templates');
      fireEvent.click(templatesButton);
      
      expect(screen.getByText('Find All Entities')).toBeInTheDocument();
      expect(screen.getByText('Get all entities in the graph')).toBeInTheDocument();
    });

    it('should hide templates dropdown when clicked again', () => {
      render(<QueryBuilder {...defaultProps} />);
      
      const templatesButton = screen.getByLabelText('Show query templates');
      fireEvent.click(templatesButton);
      expect(screen.getByText('Find All Entities')).toBeInTheDocument();
      
      fireEvent.click(templatesButton);
      expect(screen.queryByText('Find All Entities')).not.toBeInTheDocument();
    });

    it('should call onLoadQuery when template is selected', () => {
      render(<QueryBuilder {...defaultProps} />);
      
      const templatesButton = screen.getByLabelText('Show query templates');
      fireEvent.click(templatesButton);
      
      const templateButton = screen.getByText('Find All Entities');
      fireEvent.click(templateButton);
      
      expect(mockOnLoadQuery).toHaveBeenCalledWith(
        expect.stringContaining('MATCH (e)'),
        undefined
      );
    });

    it('should pass parameters when template has parameters', () => {
      render(<QueryBuilder {...defaultProps} />);
      
      const templatesButton = screen.getByLabelText('Show query templates');
      fireEvent.click(templatesButton);
      
      const templateButton = screen.getByText('Find Entities by Confidence');
      fireEvent.click(templateButton);
      
      expect(mockOnLoadQuery).toHaveBeenCalledWith(
        expect.stringContaining('WHERE e.confidence'),
        { minConfidence: 0.8 }
      );
    });

    it('should hide templates when history is opened', () => {
      const history: SavedQuery[] = [
        {
          id: '1',
          name: 'Test Query',
          query: 'MATCH (e) RETURN e',
          createdAt: '2025-01-01T00:00:00Z',
        },
      ];
      
      render(<QueryBuilder {...defaultProps} queryHistory={history} />);
      
      const templatesButton = screen.getByLabelText('Show query templates');
      fireEvent.click(templatesButton);
      expect(screen.getByText('Find All Entities')).toBeInTheDocument();
      
      const historyButton = screen.getByLabelText('Show query history');
      fireEvent.click(historyButton);
      
      expect(screen.queryByText('Find All Entities')).not.toBeInTheDocument();
      expect(screen.getByText('Test Query')).toBeInTheDocument();
    });
  });

  describe('query history', () => {
    it('should show history dropdown when clicked', () => {
      const history: SavedQuery[] = [
        {
          id: '1',
          name: 'Test Query',
          query: 'MATCH (e) RETURN e LIMIT 10',
          createdAt: '2025-01-01T00:00:00Z',
        },
        {
          id: '2',
          name: 'Another Query',
          query: 'MATCH (n:Concept) RETURN n',
          createdAt: '2025-01-02T00:00:00Z',
        },
      ];
      
      render(<QueryBuilder {...defaultProps} queryHistory={history} />);
      
      const historyButton = screen.getByLabelText('Show query history');
      fireEvent.click(historyButton);
      
      expect(screen.getByText('Test Query')).toBeInTheDocument();
      expect(screen.getByText('Another Query')).toBeInTheDocument();
    });

    it('should call onLoadQuery when history item is selected', () => {
      const history: SavedQuery[] = [
        {
          id: '1',
          name: 'Test Query',
          query: 'MATCH (e) RETURN e',
          parameters: { limit: 10 },
          createdAt: '2025-01-01T00:00:00Z',
        },
      ];
      
      render(<QueryBuilder {...defaultProps} queryHistory={history} />);
      
      const historyButton = screen.getByLabelText('Show query history');
      fireEvent.click(historyButton);
      
      const historyItem = screen.getByText('Test Query');
      fireEvent.click(historyItem);
      
      expect(mockOnLoadQuery).toHaveBeenCalledWith(
        'MATCH (e) RETURN e',
        { limit: 10 }
      );
    });

    it('should hide history when templates is opened', () => {
      const history: SavedQuery[] = [
        {
          id: '1',
          name: 'Test Query',
          query: 'MATCH (e) RETURN e',
          createdAt: '2025-01-01T00:00:00Z',
        },
      ];
      
      render(<QueryBuilder {...defaultProps} queryHistory={history} />);
      
      const historyButton = screen.getByLabelText('Show query history');
      fireEvent.click(historyButton);
      expect(screen.getByText('Test Query')).toBeInTheDocument();
      
      const templatesButton = screen.getByLabelText('Show query templates');
      fireEvent.click(templatesButton);
      
      expect(screen.queryByText('Test Query')).not.toBeInTheDocument();
      expect(screen.getByText('Find All Entities')).toBeInTheDocument();
    });
  });

  describe('save query', () => {
    it('should show save dialog when save button is clicked', () => {
      render(<QueryBuilder {...defaultProps} queryText="MATCH (e) RETURN e" />);
      
      const saveButton = screen.getByLabelText('Save query');
      fireEvent.click(saveButton);
      
      // Check for dialog heading (h3) instead of button text
      expect(screen.getByRole('heading', { name: 'Save Query' })).toBeInTheDocument();
      expect(screen.getByLabelText('Query name input')).toBeInTheDocument();
    });

    it('should call onSaveQuery when save is confirmed', () => {
      render(<QueryBuilder {...defaultProps} queryText="MATCH (e) RETURN e" />);
      
      const saveButton = screen.getByLabelText('Save query');
      fireEvent.click(saveButton);
      
      const nameInput = screen.getByLabelText('Query name input');
      fireEvent.change(nameInput, { target: { value: 'My Query' } });
      
      const confirmButton = screen.getByText('Save');
      fireEvent.click(confirmButton);
      
      expect(mockOnSaveQuery).toHaveBeenCalledWith('My Query', 'MATCH (e) RETURN e');
    });

    it('should not call onSaveQuery when name is empty', () => {
      render(<QueryBuilder {...defaultProps} queryText="MATCH (e) RETURN e" />);
      
      const saveButton = screen.getByLabelText('Save query');
      fireEvent.click(saveButton);
      
      const confirmButton = screen.getByText('Save');
      expect(confirmButton).toBeDisabled();
      
      fireEvent.click(confirmButton);
      expect(mockOnSaveQuery).not.toHaveBeenCalled();
    });

    it('should close dialog when cancel is clicked', () => {
      render(<QueryBuilder {...defaultProps} queryText="MATCH (e) RETURN e" />);
      
      const saveButton = screen.getByLabelText('Save query');
      fireEvent.click(saveButton);
      
      expect(screen.getByRole('heading', { name: 'Save Query' })).toBeInTheDocument();
      
      const cancelButton = screen.getByText('Cancel');
      fireEvent.click(cancelButton);
      
      expect(screen.queryByRole('heading', { name: 'Save Query' })).not.toBeInTheDocument();
    });

    it('should save when Enter key is pressed in name input', () => {
      render(<QueryBuilder {...defaultProps} queryText="MATCH (e) RETURN e" />);
      
      const saveButton = screen.getByLabelText('Save query');
      fireEvent.click(saveButton);
      
      const nameInput = screen.getByLabelText('Query name input') as HTMLInputElement;
      fireEvent.change(nameInput, { target: { value: 'My Query' } });
      // Focus the input first, then trigger keyPress
      nameInput.focus();
      fireEvent.keyPress(nameInput, { key: 'Enter', code: 'Enter', charCode: 13 });
      
      expect(mockOnSaveQuery).toHaveBeenCalledWith('My Query', 'MATCH (e) RETURN e');
    });

    it('should trim whitespace from query name', () => {
      render(<QueryBuilder {...defaultProps} queryText="MATCH (e) RETURN e" />);
      
      const saveButton = screen.getByLabelText('Save query');
      fireEvent.click(saveButton);
      
      const nameInput = screen.getByLabelText('Query name input');
      fireEvent.change(nameInput, { target: { value: '  My Query  ' } });
      
      const confirmButton = screen.getByText('Save');
      fireEvent.click(confirmButton);
      
      expect(mockOnSaveQuery).toHaveBeenCalledWith('My Query', 'MATCH (e) RETURN e');
    });
  });
});

