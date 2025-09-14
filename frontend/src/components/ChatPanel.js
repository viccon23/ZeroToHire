import React, { useState, useRef, useEffect } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './ChatPanel.css';

const ChatPanel = ({ conversation, currentProblem, onSendMessage, isLoading, onMarkComplete }) => {
  const [message, setMessage] = useState('');
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [conversation]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (message.trim() && !isLoading) {
      onSendMessage(message);
      setMessage('');
    }
  };


  const renderMarkdown = (content) => (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        code({ node, inline, className, children, ...props }) {
          const match = /language-(\w+)/.exec(className || '');
          const language = match ? match[1] : 'text';
          const text = String(children).replace(/\n$/, '');
          if (inline) {
            return (
              <code className={className} {...props}>
                {text}
              </code>
            );
          }
          // If it's a single short line fenced/indented block, render as inline pill
          const isShortSingleLine = !text.includes('\n') && text.trim().length > 0 && text.length <= 80;
          if (isShortSingleLine) {
            return (
              <code className={`inline-code-block ${className || ''}`} {...props}>
                {text}
              </code>
            );
          }
          return (
            <SyntaxHighlighter
              style={vscDarkPlus}
              language={language}
              PreTag="div"
              customStyle={{
                margin: '1rem 0',
                borderRadius: '6px',
                fontSize: '0.9rem',
                overflowX: 'auto'
              }}
            >
              {text}
            </SyntaxHighlighter>
          );
        }
      }}
    >
      {content}
    </ReactMarkdown>
  );

  const renderMessage = (msg, index) => {
    const isUser = msg.role === 'user';
    const isSystem = msg.role === 'system';
    const isError = msg.role === 'error';
    
    return (
      <div key={index} className={`message ${isUser ? 'user' : isSystem ? 'system' : isError ? 'error' : 'tutor'}`}>
        <div className="message-header">
          <span className="message-role">
            {isUser ? '👤 You' : isSystem ? '📋 SYSTEM' : isError ? '❌ Error' : '🤖 Alex'}
          </span>
          <span className="message-time">
            {new Date(msg.timestamp).toLocaleTimeString()}
          </span>
        </div>
        <div className="message-content">
          {renderMarkdown(msg.content)}
        </div>
      </div>
    );
  };

  return (
    <div className="chat-panel">
      <div className="chat-header">
        {currentProblem && (
          <div className="current-problem" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', justifyContent: 'space-between' }}>
            <div>
              <strong>Current Problem:</strong> {currentProblem.title} <strong> Difficulty:</strong> {currentProblem.difficulty}
              {currentProblem.completed ? (
                <span style={{ marginLeft: '0.5rem', color: '#2e7d32' }}>✓ Completed</span>
              ) : null}
            </div>
            <div>
              <button
                onClick={onMarkComplete}
                disabled={isLoading || !currentProblem || currentProblem.completed}
                className="send-button"
                title={currentProblem.completed ? 'Already completed' : 'Mark as Complete'}
                style={{ width: 'auto', height: '32px', padding: '0 12px', borderRadius: '16px' }}
              >
                {currentProblem?.completed ? 'Completed' : 'Mark as Complete'}
              </button>
            </div>
          </div>
        )}
      </div>
      
      <div className="messages-container">
        {conversation.length === 0 ? (
          <div className="empty-state">
            <p>👋 Welcome! Start a conversation with your AI tutor.</p>
            <p>Try saying "hello" or ask for a new problem!</p>
          </div>
        ) : (
          conversation.map((msg, index) => renderMessage(msg, index))
        )}
        {isLoading && (
          <div className="message tutor loading">
            <div className="message-header">
              <span className="message-role">🤖 Tutor</span>
            </div>
            <div className="message-content">
              <div className="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <form onSubmit={handleSubmit} className="message-input-form">
        <div className="input-container">
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Type your message here..."
            disabled={isLoading}
            className="message-input"
          />
          <button 
            type="submit" 
            disabled={!message.trim() || isLoading}
            className="send-button"
          >
            {isLoading ? '⏳' : '📤'}
          </button>
        </div>
      </form>
    </div>
  );
};

export default ChatPanel;
