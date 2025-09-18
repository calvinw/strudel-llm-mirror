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
    // Only connect if we detect we're on the MCP server port (8080)
    const isMCPServer = window.location.port === '8080' || window.location.host.includes('8080');
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
    if (!editorRef.current) {
      console.error('Editor not ready for code retrieval');
      return;
    }

    const currentCode = editorRef.current.getCode() || '// No code in editor';

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      const message = {
        type: 'current-code-response',
        request_id: requestId,
        code: currentCode,
        timestamp: Date.now()
      };

      wsRef.current.send(JSON.stringify(message));
      console.log(`📤 Sent current code to MCP server (${currentCode.length} chars)`);
    } else {
      console.error('WebSocket not connected - cannot send code');
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
        getCode: () => editorRef.current.getCode(),
        sessionId,
        connectionStatus
      };
    }
  }, [sessionId, connectionStatus, editorRef.current]);

  return {
    sessionId,
    connectionStatus,
    isMCPEnabled: window.location.port === '8080' || window.location.host.includes('8080')
  };
}