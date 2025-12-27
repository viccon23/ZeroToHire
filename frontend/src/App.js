import React, { useState, useEffect, useRef, useCallback } from 'react';
import './App.css';
import ChatPanel from './components/ChatPanel';
import CodeEditor from './components/CodeEditor';
import ProblemBrowser from './components/ProblemBrowser';
import api, { API_BASE_URL } from './services/api';

const DEFAULT_TEMPLATE = 'def solution():\n    pass';
const CODE_STORAGE_PREFIX = 'zerotohire_code_';

const getCodeStorageKey = (problemId) => `${CODE_STORAGE_PREFIX}${problemId ?? 'global'}`;

const buildDefaultWsUrl = (apiBaseUrl) => {
  const normalized = (apiBaseUrl || 'http://127.0.0.1:5000/api').replace(/\/+$/, '');
  let protocolAdjusted = normalized;
  if (normalized.startsWith('https://')) {
    protocolAdjusted = `wss://${normalized.slice('https://'.length)}`;
  } else if (normalized.startsWith('http://')) {
    protocolAdjusted = `ws://${normalized.slice('http://'.length)}`;
  }

  if (protocolAdjusted.endsWith('/api')) {
    return `${protocolAdjusted.slice(0, -4)}/ws/chat`;
  }
  return `${protocolAdjusted}/ws/chat`;
};

const WS_URL = process.env.REACT_APP_WS_URL || buildDefaultWsUrl(API_BASE_URL);

function App() {
  const [conversation, setConversation] = useState([]);
  const [currentProblem, setCurrentProblem] = useState(null);
  const [code, setCode] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showProblemBrowser, setShowProblemBrowser] = useState(false);
  const [includeCodeInContext, setIncludeCodeInContext] = useState(true); // Toggle for auto code context
  const [error, setError] = useState(null);
  const [isStreamingResponse, setIsStreamingResponse] = useState(false);
  const [isWebSocketReady, setIsWebSocketReady] = useState(false);
  const wsRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const isUnmountedRef = useRef(false);
  const messageHandlerRef = useRef(null);

  

  // Load code for current problem
  const loadCodeForProblem = useCallback(async (problemId) => {
    try {
      const response = await api.get(`/code/load/${problemId}`);
      return response.data.code;
    } catch (err) {
      console.error('Failed to load code:', err);
      return null;
    }
  }, []);

  const hydrateCodeForProblem = useCallback(async (problem) => {
    if (!problem || problem.id == null) {
      const fallback = localStorage.getItem(getCodeStorageKey('global')) || DEFAULT_TEMPLATE;
      setCode(fallback);
      return;
    }

    const storageKey = getCodeStorageKey(problem.id);
    const persisted = localStorage.getItem(storageKey);
    if (persisted !== null) {
      setCode(persisted);
      return;
    }

    const savedCode = await loadCodeForProblem(problem.id);
    if (savedCode) {
      setCode(savedCode);
      localStorage.setItem(storageKey, savedCode);
      return;
    }

    const templateCode = problem.template_code || DEFAULT_TEMPLATE;
    setCode(templateCode);
    localStorage.setItem(storageKey, templateCode);
  }, [loadCodeForProblem]);

  useEffect(() => {
    hydrateCodeForProblem(currentProblem);
  }, [currentProblem?.id, hydrateCodeForProblem]);

  // Load user settings
  const loadSettings = useCallback(async () => {
    try {
      const response = await api.get('/settings');
      if (response.data.includeCodeInContext !== undefined) {
        setIncludeCodeInContext(response.data.includeCodeInContext);
      }
    } catch (error) {
      console.error('Failed to load settings:', error);
    }
  }, []);

  // Save setting
  const saveSetting = async (key, value) => {
    try {
      await api.post(`/settings/${key}`, { value });
    } catch (error) {
      console.error('Failed to save setting:', error);
    }
  };

  // Update includeCodeInContext and persist to backend
  const handleToggleCodeContext = () => {
    const newValue = !includeCodeInContext;
    setIncludeCodeInContext(newValue);
    saveSetting('includeCodeInContext', newValue);
  };

  const loadStatus = useCallback(async () => {
    try {
      setError(null);
      const response = await api.get('/status');
      setConversation(response.data.conversation_history || []);
      setCurrentProblem(response.data.current_problem);
    } catch (error) {
      console.error('Failed to load status:', error);
      setError('Failed to connect to the backend. Make sure the server is running.');
    }
  }, []);

  // Load initial status when app starts
  useEffect(() => {
    loadStatus();
    loadSettings();
  }, [loadStatus, loadSettings]);

  const sendMessageViaHttp = useCallback(async (payload) => {
    try {
      const response = await api.post('/chat', payload);
      setConversation(response.data.conversation_history || []);

      if (response.data.problem_changed) {
        setCurrentProblem(response.data.current_problem);
        const templateCode = response.data.current_problem?.template_code || DEFAULT_TEMPLATE;
        setCode(templateCode);
      } else {
        setCurrentProblem(response.data.current_problem);
      }
    } catch (err) {
      console.error('Failed to send message via HTTP:', err);
      const errorMessage = err.response?.data?.error || 'Failed to get response from tutor. Please try again.';
      setError(errorMessage);
      setConversation((prev) => [
        ...prev,
        { role: 'error', content: errorMessage, timestamp: new Date().toISOString() }
      ]);
    } finally {
      setIsLoading(false);
      setIsStreamingResponse(false);
    }
  }, []);

  const handleWebSocketMessage = useCallback((event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === 'token') {
        setIsStreamingResponse(true);
        setConversation((prev) => {
          if (!prev.length || prev[prev.length - 1]?.role !== 'alex' || !prev[prev.length - 1]?.isStreaming) {
            return [
              ...prev,
              {
                role: 'alex',
                content: data.token,
                timestamp: new Date().toISOString(),
                isStreaming: true
              }
            ];
          }
          const updated = [...prev];
          const lastMessage = { ...updated[updated.length - 1] };
          lastMessage.content = `${lastMessage.content || ''}${data.token}`;
          updated[updated.length - 1] = lastMessage;
          return updated;
        });
      } else if (data.type === 'final') {
        setIsStreamingResponse(false);
        setIsLoading(false);
        if (Array.isArray(data.conversation_history)) {
          setConversation(data.conversation_history);
        }
        if (data.current_problem !== undefined) {
          setCurrentProblem(data.current_problem);
        }
      } else if (data.type === 'error') {
        setIsStreamingResponse(false);
        setIsLoading(false);
        const errorMessage = data.error || 'Streaming error occurred. Please try again.';
        setError(errorMessage);
        setConversation((prev) => [
          ...prev,
          { role: 'error', content: errorMessage, timestamp: new Date().toISOString() }
        ]);
      }
    } catch (err) {
      console.error('Failed to parse WebSocket message:', err);
    }
  }, []);

  // Update the ref whenever the handler changes
  useEffect(() => {
    messageHandlerRef.current = handleWebSocketMessage;
  }, [handleWebSocketMessage]);

  const connectWebSocket = useCallback(() => {
    if (typeof window === 'undefined' || !('WebSocket' in window)) {
      return;
    }

    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      return;
    }

    try {
      const socket = new WebSocket(WS_URL);
      wsRef.current = socket;

      socket.onopen = () => {
        setIsWebSocketReady(true);
      };

      socket.onmessage = (event) => {
        if (messageHandlerRef.current) {
          messageHandlerRef.current(event);
        }
      };

      socket.onerror = (event) => {
        console.error('WebSocket error:', event);
      };

      socket.onclose = () => {
        setIsWebSocketReady(false);
        wsRef.current = null;
        if (!isUnmountedRef.current) {
          reconnectTimerRef.current = window.setTimeout(() => {
            connectWebSocket();
          }, 2000);
        }
      };
    } catch (err) {
      console.error('Failed to establish WebSocket connection:', err);
    }
  }, []);

  useEffect(() => {
    connectWebSocket();

    return () => {
      isUnmountedRef.current = true;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connectWebSocket]);

  // Auto-save code snapshot every 30 seconds
  useEffect(() => {
    if (!currentProblem || currentProblem.id == null || !code.trim()) {
      return undefined;
    }

    const problemId = currentProblem.id;
    const codeSnapshot = code;

    const handleAutoSave = async () => {
      try {
        await api.post('/code/save', {
          problem_id: problemId,
          code: codeSnapshot,
          language: 'python'
        });
        console.log('Code auto-saved');
      } catch (autoSaveError) {
        console.error('Failed to auto-save code:', autoSaveError);
      }
    };

    const autoSaveTimer = setTimeout(handleAutoSave, 30000);
    return () => clearTimeout(autoSaveTimer);
  }, [code, currentProblem]);

  // Persist code locally for reload resilience
  useEffect(() => {
    const storageKey = currentProblem && currentProblem.id != null
      ? getCodeStorageKey(currentProblem.id)
      : getCodeStorageKey('global');
    localStorage.setItem(storageKey, code || '');
  }, [code, currentProblem]);

  const sendMessage = async (message) => {
    if (!message.trim()) return;

    setError(null);
    const userMessage = {
      role: 'user',
      content: message,
      timestamp: new Date().toISOString()
    };
    setConversation((prev) => [...prev, userMessage]);

    setIsLoading(true);
    setIsStreamingResponse(false);

    const payload = {
      message,
      ...(includeCodeInContext && code.trim() && {
        codeContext: {
          code: code,
          includeInContext: true
        }
      })
    };

    const socket = wsRef.current;
    if (isWebSocketReady && socket && socket.readyState === WebSocket.OPEN) {
      try {
        socket.send(JSON.stringify(payload));
        return;
      } catch (err) {
        console.error('WebSocket send failed, falling back to HTTP:', err);
      }
    }

    if (socket && socket.readyState === WebSocket.CONNECTING) {
      console.warn('WebSocket still connecting. Falling back to HTTP for this message.');
    } else {
      connectWebSocket();
      if (!isWebSocketReady) {
        console.warn('WebSocket not ready yet. Using HTTP fallback temporarily.');
      }
    }

    await sendMessageViaHttp(payload);
  };

   const selectProblem = async (problemId) => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await api.post(`/problems/${problemId}`, {});
      setConversation(response.data.conversation_history || []);
      setCurrentProblem(response.data.problem);
      setShowProblemBrowser(false);
    } catch (error) {
      console.error('Failed to select problem:', error);
      const errorMessage = error.response?.data?.error || 'Failed to load problem. Please try again.';
      setError(errorMessage);
      setCode(DEFAULT_TEMPLATE); // Fallback
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
    setError(null);
    try {
      await api.post(`/problems/${currentProblem.id}/completion`, { completed: true });
      setConversation(prev => [...prev, { role: 'system', content: `Problem '${currentProblem.title}' marked as completed.`, timestamp: new Date().toISOString() }]);
      await loadStatus();
    } catch (error) {
      console.error('Failed to mark problem complete:', error);
      const errorMessage = error.response?.data?.error || 'Failed to mark problem as complete.';
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const evaluateCode = async () => {
    if (!code.trim()) return;

    setIsLoading(true);
    setError(null);
    try {
      const response = await api.post('/evaluate-code', { 
        code, 
        language: 'python' 
      });
      setConversation(response.data.conversation_history || []);
    } catch (error) {
      console.error('Failed to evaluate code:', error);
      const errorMessage = error.response?.data?.error || 'Failed to evaluate code. Please try again.';
      setError(errorMessage);
      setConversation(prev => [...prev, 
        { role: 'error', content: errorMessage, timestamp: new Date().toISOString() }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const clearChat = async () => {
    setIsLoading(true);
    setError(null);
    try {
      await api.post('/clear-chat', {});
      setConversation([]);
      
      const templateCode = currentProblem?.template_code || DEFAULT_TEMPLATE;
      setCode(templateCode);
      const storageKey = currentProblem ? getCodeStorageKey(currentProblem.id) : getCodeStorageKey('global');
      localStorage.setItem(storageKey, templateCode);
    } catch (error) {
      console.error('Failed to clear Chat:', error);
      const errorMessage = error.response?.data?.error || 'Failed to clear chat.';
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  const resetProblem = async () => {
    if (!currentProblem) {
      alert('No problem is currently selected');
      return;
    }

    const confirmReset = window.confirm(
      `Are you sure you want to reset "${currentProblem.title}"?\n\nThis will:\n- Clear all chat messages for this problem\n- Delete your saved code\n- Mark as incomplete\n\nThis action cannot be undone.`
    );

    if (!confirmReset) return;

    try {
      await api.post('/problem/reset', { 
        problem_id: currentProblem.id 
      });
      
      // Clear local state
      setConversation([]);
      setCode(DEFAULT_TEMPLATE);
      localStorage.removeItem(getCodeStorageKey(currentProblem.id));
      setError(null);
      
      alert('Problem reset successfully! Starting fresh.');
    } catch (err) {
      console.error('Failed to reset problem:', err);
      setError('Failed to reset problem. Please try again.');
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
          <button onClick={resetProblem} disabled={isLoading || !currentProblem}>
            Reset Problem
          </button>
        </div>
      </header>
      
      {error && (
        <div className="error-banner">
          <span>⚠️ {error}</span>
          <button onClick={() => setError(null)}>✕</button>
        </div>
      )}
      
      <main className="app-main">
        <div className="left-panel">
          <ChatPanel
            conversation={conversation}
            currentProblem={currentProblem}
            onSendMessage={sendMessage}
            isLoading={isLoading}
            onMarkComplete={markCurrentProblemComplete}
            includeCodeInContext={includeCodeInContext}
            onToggleCodeContext={handleToggleCodeContext}
            isStreamingResponse={isStreamingResponse}
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
