import React, { useState, useRef, useEffect } from 'react';
import './ChatPanel.css';

const ChatPanel = ({ conversation, currentProblem, onSendMessage, isLoading }) => {
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

  const formatMessage = (content) => {
    // Convert newlines to <br> tags and preserve formatting
    return content.split('\n').map((line, index) => (
      <React.Fragment key={index}>
        {line}
        {index < content.split('\n').length - 1 && <br />}
      </React.Fragment>
    ));
  };

  const renderMessage = (msg, index) => {
    const isUser = msg.role === 'user';
    const isSystem = msg.role === 'system';
    const isError = msg.role === 'error';
    
    return (
      <div key={index} className={`message ${isUser ? 'user' : isSystem ? 'system' : isError ? 'error' : 'tutor'}`}>
        <div className="message-header">
          <span className="message-role">
            {isUser ? '👤 You' : isSystem ? '📋 System' : isError ? '❌ Error' : '🤖 Tutor'}
          </span>
          <span className="message-time">
            {new Date(msg.timestamp).toLocaleTimeString()}
          </span>
        </div>
        <div className="message-content">
          {formatMessage(msg.content)}
        </div>
      </div>
    );
  };

  return (
    <div className="chat-panel">
      <div className="chat-header">
        <h2>💬 Conversation</h2>
        {currentProblem && (
          <div className="current-problem">
            <strong>Current Problem:</strong> {currentProblem.title}
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
