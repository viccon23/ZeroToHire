import React, { useState, useEffect } from 'react';
import './App.css';
import ChatPanel from './components/ChatPanel';
import CodeEditor from './components/CodeEditor';
import ProblemBrowser from './components/ProblemBrowser';
import api from './services/api';

function App() {
  const [conversation, setConversation] = useState([]);
  const [currentProblem, setCurrentProblem] = useState(null);
  const [code, setCode] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showProblemBrowser, setShowProblemBrowser] = useState(false);

  // Load initial status when app starts
  useEffect(() => {
    loadStatus();
  }, []);

  const loadStatus = async () => {
    try {
      const response = await api.get('/status');
      setConversation(response.data.conversation_history || []);
      setCurrentProblem(response.data.current_problem);
    } catch (error) {
      console.error('Failed to load status:', error);
    }
  };

  const sendMessage = async (message) => {
    if (!message.trim()) return;
    const userMessage = { 
      role: 'user', 
      content: message, 
      timestamp: new Date().toISOString() 
    };
    setConversation(prev => [...prev, userMessage]);

    setIsLoading(true);
    try {
      const response = await api.post('/chat', { message });
      setConversation(response.data.conversation_history || []);
      
      // Check if the problem changed during chat
      if (response.data.problem_changed) {
        setCurrentProblem(response.data.current_problem);
        setCode('# Write your solution here\ndef solution():\n    pass'); // Reset to default code
      } else {
        setCurrentProblem(response.data.current_problem);
      }
    } catch (error) {
      console.error('Failed to send message:', error);
      // Add error message to conversation (user message is already there)
      setConversation(prev => [...prev, 
        { role: 'error', content: 'Failed to get response from tutor. Please try again.', timestamp: new Date().toISOString() }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const selectProblem = async (problemId) => {
    setIsLoading(true);
    try {
      const response = await api.post(`/problems/${problemId}`, {});
      setConversation(response.data.conversation_history || []);
      setCurrentProblem(response.data.problem);
      setShowProblemBrowser(false);
      setCode('');
    } catch (error) {
      console.error('Failed to select problem:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const startNewProblem = async () => {
    setShowProblemBrowser(true);
  };

  const markCurrentProblemComplete = async () => {
    if (!currentProblem || currentProblem.id == null) return;
    setIsLoading(true);
    try {
      await api.post(`/problems/${currentProblem.id}/completion`, { completed: true });
      setConversation(prev => [...prev, { role: 'system', content: `Problem '${currentProblem.title}' marked as completed.`, timestamp: new Date().toISOString() }]);
      await loadStatus();
    } catch (error) {
      console.error('Failed to mark problem complete:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const evaluateCode = async () => {
    if (!code.trim()) return;

    setIsLoading(true);
    try {
      const response = await api.post('/evaluate-code', { 
        code, 
        language: 'python' 
      });
      setConversation(response.data.conversation_history || []);
    } catch (error) {
      console.error('Failed to evaluate code:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const clearChat = async () => {
    setIsLoading(true);
    try {
      await api.post('/clear-chat', {});
      setConversation([]);
      setCode('# Write your solution here\ndef solution():\n    pass');
    } catch (error) {
      console.error('Failed to clear Chat:', error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="App">
      <header className="app-header">
        <h1>ZeroToHire</h1>
        <div className="header-buttons">
          <button onClick={startNewProblem} disabled={isLoading}>
            Browse Problems
          </button>
          <button onClick={clearChat} disabled={isLoading}>
            Clear Chat
          </button>
        </div>
      </header>
      
      <main className="app-main">
        <div className="left-panel">
          <ChatPanel
            conversation={conversation}
            currentProblem={currentProblem}
            onSendMessage={sendMessage}
            isLoading={isLoading}
            onMarkComplete={markCurrentProblemComplete}
          />
        </div>
        
        <div className="right-panel">
          <CodeEditor
            code={code}
            onCodeChange={setCode}
            onEvaluate={evaluateCode}
            isLoading={isLoading}
            currentProblem={currentProblem}
          />
        </div>
      </main>
      
      {showProblemBrowser && (
        <ProblemBrowser
          onSelectProblem={selectProblem}
          onClose={() => setShowProblemBrowser(false)}
          isLoading={isLoading}
        />
      )}
    </div>
  );
}

export default App;
