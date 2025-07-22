import React, { useState, useEffect } from 'react';
import Editor from '@monaco-editor/react';
import ReactMarkdown from 'react-markdown';
import './CodeEditor.css';

const CodeEditor = ({ code, onCodeChange, onEvaluate, isLoading, currentProblem, functionSignature }) => {
  const [problemHeight, setProblemHeight] = useState(200); // Default height in pixels
  const [isResizing, setIsResizing] = useState(false);

  const handleEditorChange = (value) => {
    onCodeChange(value || '');
  };

  const handleEvaluate = () => {
    if (code.trim() && !isLoading) {
      onEvaluate();
    }
  };

  const handleMouseDown = (e) => {
    setIsResizing(true);
    e.preventDefault();
  };

  const handleMouseMove = (e) => {
    if (!isResizing) return;
    
    const codeEditorElement = document.querySelector('.code-editor');
    if (!codeEditorElement) return;
    
    const rect = codeEditorElement.getBoundingClientRect();
    const headerElement = document.querySelector('.editor-header');
    const headerHeight = headerElement ? headerElement.offsetHeight : 60;
    
    const relativeY = e.clientY - rect.top - headerHeight;
    const newHeight = Math.max(150, Math.min(500, relativeY));
    
    setProblemHeight(newHeight);
  };

  const handleMouseUp = () => {
    setIsResizing(false);
  };

  // Add event listeners when resizing starts
  React.useEffect(() => {
    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      
      return () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
      };
    }
  }, [isResizing]);

  // If we have a function signature and the code is empty, use it as default
  const editorValue = code || (functionSignature ? `${functionSignature}\n        # Your solution here\n        pass` : '');

  return (
    <div className="code-editor">
      <div className="editor-header">
        <h2>💻 Code Editor</h2>
        <div className="editor-controls">
          <button 
            onClick={handleEvaluate}
            disabled={!code.trim() || isLoading}
            className="evaluate-button"
          >
            {isLoading ? '⏳ Evaluating...' : '🚀 Submit Code'}
          </button>
        </div>
      </div>
      
      <div className="problem-display" style={{ height: `${problemHeight}px` }}>
        {currentProblem ? (
          <div className="problem-info">
            <h3>{currentProblem.title}</h3>
            {currentProblem.description && (
              <div className="problem-description">
                <div className="description-content expanded">
                  <ReactMarkdown>{currentProblem.description}</ReactMarkdown>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="no-problem">
            <p>🤔 No problem loaded yet. Start a conversation with your tutor!</p>
          </div>
        )}
      </div>

      <div 
        className={`resize-handle ${isResizing ? 'resizing' : ''}`}
        onMouseDown={handleMouseDown}
      >
        <div className="resize-indicator">⋯</div>
      </div>

      <div className="editor-container" style={{ height: `calc(100% - ${problemHeight + 70}px)` }}>
        <Editor
          height="100%"
          defaultLanguage="python"
          value={editorValue}
          onChange={handleEditorChange}
          theme="vs-dark"
          options={{
            fontSize: 14,
            minimap: { enabled: false },
            scrollBeyondLastLine: false,
            automaticLayout: true,
            tabSize: 4,
            insertSpaces: true,
            wordWrap: 'on',
            lineNumbers: 'on',
            glyphMargin: false,
            folding: false,
            lineDecorationsWidth: 0,
            lineNumbersMinChars: 3,
            renderLineHighlight: 'line',
            bracketPairColorization: { enabled: true },
          }}
        />
      </div>

      <div className="editor-footer">
        <div className="editor-tips">
          <span>💡 Tips:</span>
          <ul>
            <li>Write your solution and click "Submit Code" to get feedback</li>
            <li>The AI tutor can see your code and provide specific guidance</li>
            <li>Don't worry about getting it perfect - learning is iterative!</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default CodeEditor;
