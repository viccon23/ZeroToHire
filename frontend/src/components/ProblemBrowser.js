import React, { useState, useEffect } from 'react';
import './ProblemBrowser.css';
import api from '../services/api';

const ProblemBrowser = ({ onSelectProblem, onClose, isLoading }) => {
  const [problems, setProblems] = useState([]);
  const [filters, setFilters] = useState({ difficulties: [], problem_types: [] });
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedDifficulties, setSelectedDifficulties] = useState([]);
  const [selectedTypes, setSelectedTypes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);

  const ITEMS_PER_PAGE = 20;

  useEffect(() => {
    loadFilters();
    loadProblems();
  }, []);

  useEffect(() => {
    setCurrentPage(1);
    loadProblems(true);
  }, [searchTerm, selectedDifficulties, selectedTypes]);

  const loadFilters = async () => {
    try {
      const response = await api.get('/filters');
      setFilters(response.data);
    } catch (error) {
      console.error('Failed to load filters:', error);
    }
  };

  const loadProblems = async (reset = false) => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      
      if (searchTerm) params.append('search', searchTerm);
      if (selectedDifficulties.length > 0) {
        selectedDifficulties.forEach(diff => params.append('difficulty', diff));
      }
      if (selectedTypes.length > 0) {
        selectedTypes.forEach(type => params.append('type', type));
      }
      
      params.append('page', reset ? 1 : currentPage);
      params.append('per_page', ITEMS_PER_PAGE);

      const response = await api.get(`/problems?${params.toString()}`);
      
      if (reset) {
        setProblems(response.data.problems);
        setCurrentPage(1);
      } else {
        setProblems(prev => [...prev, ...response.data.problems]);
      }
      
      setHasMore(response.data.has_more);
    } catch (error) {
      console.error('Failed to load problems:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadMoreProblems = () => {
    if (hasMore && !loading) {
      setCurrentPage(prev => {
        const newPage = prev + 1;
        // Load problems for the new page
        setTimeout(() => loadProblems(false), 0);
        return newPage;
      });
    }
  };

  const handleDifficultyChange = (difficulty) => {
    setSelectedDifficulties(prev => 
      prev.includes(difficulty) 
        ? prev.filter(d => d !== difficulty)
        : [...prev, difficulty]
    );
  };

  const handleTypeChange = (type) => {
    setSelectedTypes(prev => 
      prev.includes(type) 
        ? prev.filter(t => t !== type)
        : [...prev, type]
    );
  };

  const clearFilters = () => {
    setSearchTerm('');
    setSelectedDifficulties([]);
    setSelectedTypes([]);
  };

  const getDifficultyColor = (difficulty) => {
    switch (difficulty?.toLowerCase()) {
      case 'easy': return '#28a745';
      case 'medium': return '#ffc107';
      case 'hard': return '#dc3545';
      default: return '#6c757d';
    }
  };

  return (
    <div className="problem-browser-overlay">
      <div className="problem-browser-modal">
        <div className="problem-browser-header">
          <h2>Browse LeetCode Problems</h2>
          <button className="close-button" onClick={onClose}>×</button>
        </div>

        <div className="problem-browser-filters">
          <div className="search-section">
            <input
              type="text"
              placeholder="Search problems by title..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="search-input"
            />
          </div>

          <div className="filters-section">
            <div className="filter-group">
              <label>Difficulty:</label>
              <div className="filter-options">
                {(filters.difficulties || []).map(difficulty => (
                  <label key={difficulty} className="filter-checkbox">
                    <input
                      type="checkbox"
                      checked={selectedDifficulties.includes(difficulty)}
                      onChange={() => handleDifficultyChange(difficulty)}
                    />
                    <span style={{ color: getDifficultyColor(difficulty) }}>
                      {difficulty}
                    </span>
                  </label>
                ))}
              </div>
            </div>

            <div className="filter-group">
              <label>Type:</label>
              <div className="filter-options">
                {(filters.problem_types || []).slice(0, 8).map(type => (
                  <label key={type} className="filter-checkbox">
                    <input
                      type="checkbox"
                      checked={selectedTypes.includes(type)}
                      onChange={() => handleTypeChange(type)}
                    />
                    <span>{type}</span>
                  </label>
                ))}
              </div>
            </div>

            <button className="clear-filters-button" onClick={clearFilters}>
              Clear All Filters
            </button>
          </div>
        </div>

        <div className="problems-list">
          {problems.map(problem => (
            <div key={problem.id} className="problem-item">
              <div className="problem-info">
                <div className="problem-title">{problem.title}</div>
                <div className="problem-meta">
                  <span 
                    className="problem-difficulty"
                    style={{ color: getDifficultyColor(problem.difficulty) }}
                  >
                    {problem.difficulty}
                  </span>
                  {(problem.problem_types && Array.isArray(problem.problem_types) && problem.problem_types.length > 0) && (
                    <span className="problem-types">
                      {problem.problem_types
                        .filter(type => type && typeof type === 'string')
                        .slice(0, 3)
                        .join(', ')}
                      {problem.problem_types.length > 3 && '...'}
                    </span>
                  )}
                </div>
              </div>
              <button
                className="select-problem-button"
                onClick={() => onSelectProblem(problem.id)}
                disabled={isLoading}
              >
                Select
              </button>
            </div>
          ))}

          {loading && (
            <div className="loading-indicator">
              <div className="spinner"></div>
              <span>Loading problems...</span>
            </div>
          )}

          {!loading && problems.length === 0 && (
            <div className="no-problems">
              <p>No problems found matching your criteria.</p>
              <p>Try adjusting your search terms or filters.</p>
            </div>
          )}

          {!loading && hasMore && problems.length > 0 && (
            <button className="load-more-button" onClick={loadMoreProblems}>
              Load More Problems
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default ProblemBrowser;
