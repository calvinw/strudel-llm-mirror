/*
useWebSocketMCP.jsx - WebSocket hook for MCP integration with Strudel REPL
*/

import { useEffect, useState, useRef } from 'react';

export function useWebSocketMCP(editorRef) {
  const [sessionId, setSessionId] = useState('');
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const wsRef = useRef(null);

  // Generate session ID
  const generateSessionId = () => {
    const letters = Math.random().toString(36).substring(2, 5);
    const digit = Math.floor(Math.random() * 10);
    return letters + digit;
  };

  // WebSocket connection
  const connectWebSocket = () => {
    // Only connect if we detect we're on the MCP server port (8080) or Docker port (8000)
    const isMCPServer = window.location.port === '8080' || window.location.port === '8000' ||
                        window.location.host.includes('8080') || window.location.host.includes('8000');
    if (!isMCPServer) {
      console.log('🔍 Not on MCP server, skipping WebSocket connection');
      return;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/strudel/ws?session_id=${sessionId}`;

    console.log('🔍 Connecting WebSocket with sessionId:', sessionId);
    console.log('🔍 WebSocket URL:', wsUrl);

    wsRef.current = new WebSocket(wsUrl);

    wsRef.current.onopen = () => {
      setConnectionStatus('connected');
      console.log('🔍 WebSocket connected with URL:', wsUrl);
    };

    wsRef.current.onmessage = async (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('🔍 WebSocket received message:', data);

        if (data.type === 'strudel-code') {
          const description = data.metadata?.description || '';
          console.log('🎵 Processing strudel-code message:', data);

          // Set the code and play it using the editor
          if (editorRef.current) {
            editorRef.current.setCode(data.code);
            editorRef.current.evaluate();
            console.log('✅ Pattern playing');
          }

        } else if (data.type === 'strudel-stop' || data.type === 'stop') {
          console.log('⏹️ Stop command received');
          if (editorRef.current) {
            editorRef.current.stop();
            console.log('⏹️ Stopped all patterns');
          }

        } else if (data.type === 'get-current-code') {
          console.log('📝 Sending current editor code to MCP server');
          sendCurrentCodeToServer(data.request_id);

        } else if (data.type === 'ping') {
          wsRef.current.send(JSON.stringify({type: 'pong'}));
        }

      } catch (error) {
        console.error('WebSocket message error:', error);
      }
    };

    wsRef.current.onclose = () => {
      setConnectionStatus('disconnected');
      console.log('WebSocket disconnected, attempting to reconnect...');
      setTimeout(connectWebSocket, 3000);
    };

    wsRef.current.onerror = (error) => {
      console.error('WebSocket error:', error);
      setConnectionStatus('error');
    };
  };

  const sendCurrentCodeToServer = (requestId) => {
    console.log('🔍 sendCurrentCodeToServer called with requestId:', requestId);
    console.log('🔍 editorRef.current:', editorRef.current);

    if (!editorRef.current) {
      console.error('❌ Editor not ready for code retrieval');
      // Send error response instead of just returning
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        const errorMessage = {
          type: 'current-code-response',
          request_id: requestId,
          code: '// Error: Editor not ready',
          timestamp: Date.now()
        };
        wsRef.current.send(JSON.stringify(errorMessage));
        console.log('📤 Sent error response to MCP server');
      }
      return;
    }

    console.log('🔍 editorRef.current.getCode:', typeof editorRef.current.getCode);

    let currentCode;
    try {
      currentCode = editorRef.current.code || '// No code in editor';
      console.log('🔍 Retrieved code length:', currentCode.length);
    } catch (error) {
      console.error('❌ Error getting code from editor:', error);
      currentCode = '// Error: Could not retrieve code';
    }

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      const message = {
        type: 'current-code-response',
        request_id: requestId,
        code: currentCode,
        timestamp: Date.now()
      };

      console.log('🔍 About to send message:', message);
      wsRef.current.send(JSON.stringify(message));
      console.log(`📤 Sent current code to MCP server (${currentCode.length} chars)`);
    } else {
      console.error('❌ WebSocket not connected - cannot send code');
      console.log('🔍 WebSocket state:', wsRef.current?.readyState);
    }
  };

  // Initialize session and connect WebSocket
  useEffect(() => {
    const newSessionId = generateSessionId();
    setSessionId(newSessionId);
  }, []);

  useEffect(() => {
    if (sessionId) {
      connectWebSocket();
    }

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [sessionId]);

  // Add global API for external access
  useEffect(() => {
    const isMCPServer = window.location.port === '8080' || window.location.host.includes('8080');
    if (isMCPServer && editorRef.current) {
      window.strudelMCP = {
        setCode: (code) => {
          editorRef.current.setCode(code);
          editorRef.current.evaluate();
        },
        play: () => editorRef.current.evaluate(),
        stop: () => editorRef.current.stop(),
        getCode: () => editorRef.current.code,
        sessionId,
        connectionStatus
      };
    }
  }, [sessionId, connectionStatus, editorRef.current]);

  return {
    sessionId,
    connectionStatus,
    isMCPEnabled: window.location.port === '8080' || window.location.port === '8000' ||
                 window.location.host.includes('8080') || window.location.host.includes('8000')
  };
}