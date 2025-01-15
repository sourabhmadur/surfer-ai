import React, { useState, useEffect, useRef } from 'react';
import { Action } from '../content/actions';

// Keep only the interfaces we're using
interface ChatMessage {
  type: 'user' | 'agent' | 'action' | 'error' | 'plan' | 'progress';
  content: string;
  subtasks?: string[];
  progress?: number;
  total?: number;
  isReplanning?: boolean;
}

// Add logger utility at the top of the file
const logger = {
  group: (label: string) => {
    console.group(`=== ${label} ===`);
  },
  groupEnd: () => {
    console.groupEnd();
  },
  log: (message: string, data?: any) => {
    console.log(`[${new Date().toISOString()}] ${message}`, data || '');
  },
  error: (message: string, error?: any) => {
    console.error(`[${new Date().toISOString()}] ERROR: ${message}`, error || '');
  }
};

export default function Sidepanel() {
  const [task, setTask] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isExecuting, setIsExecuting] = useState(false);
  const [currentSubtask, setCurrentSubtask] = useState(0);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const [wsStatus, setWsStatus] = useState<'connecting' | 'connected' | 'disconnected'>('connecting');

  // Add test scroll function
  const testScroll = () => {
    logger.group('Test Scroll');
    const scrollAction: Action = {
      action: 'scroll',
      direction: 'down',
      pixels: 100
    };
    
    logger.log('Sending test scroll action', scrollAction);
    const messageToBackground = {
      type: 'EXECUTE_ACTION',
      action: scrollAction
    };
    
    chrome.runtime.sendMessage(messageToBackground, (response) => {
      logger.log('Background response (test scroll)', response);
      handleActionResult(response);
    });
    logger.groupEnd();
  };

  // Add test button to the UI
  const renderTestControls = () => (
    <div style={{ padding: '10px', borderTop: '1px solid #ccc', marginTop: '10px' }}>
      <button 
        onClick={testScroll}
        style={{
          padding: '8px 16px',
          backgroundColor: '#4CAF50',
          color: 'white',
          border: 'none',
          borderRadius: '4px',
          cursor: 'pointer'
        }}
      >
        Test Scroll Down
      </button>
    </div>
  );

  // Initialize WebSocket connection
  useEffect(() => {
    const connectWebSocket = () => {
      logger.group('WebSocket Connection');
      logger.log('Attempting connection');
      setWsStatus('connecting');
      
      const ws = new WebSocket('ws://localhost:8000/ws/agent');
      wsRef.current = ws;

      ws.onopen = () => {
        logger.log('Connected successfully');
        setIsConnected(true);
        setWsStatus('connected');
        // Send a test message when connected
        ws.send(JSON.stringify({ type: 'test', message: 'Testing WebSocket connection' }));
      };

      ws.onclose = (event) => {
        logger.log('Disconnected', {
          code: event.code,
          reason: event.reason,
          wasClean: event.wasClean
        });
        setIsConnected(false);
        setWsStatus('disconnected');
        // Try to reconnect after 2 seconds
        setTimeout(connectWebSocket, 2000);
      };

      ws.onerror = (error) => {
        logger.error('Connection error', {
          error,
          readyState: ws.readyState,
          url: ws.url
        });
        setWsStatus('disconnected');
        setMessages(prev => [...prev, {
          type: 'error',
          content: 'Connection error. Please try again.'
        }]);
      };

      ws.onmessage = (event) => {
        logger.group('WebSocket Message');
        console.log('=== Raw WebSocket Message ===', {
          data: event.data,
          type: typeof event.data,
          length: event.data.length
        });

        try {
          const message = JSON.parse(event.data);
          console.log('=== Parsed WebSocket Message ===', {
            messageType: message.type,
            messageData: message.data,
            fullMessage: message,
            isAction: message.type === 'action',
            dataType: typeof message.data
          });

          // Add debug logging for action messages
          if (message.type === 'action') {
            console.log('=== Action Message Details ===', {
              actionType: typeof message.data === 'string' ? 'string' : message.data.action || message.data.type,
              actionData: message.data,
              isString: typeof message.data === 'string',
              hasAction: message.data?.action,
              hasType: message.data?.type
            });
          }

          handleWebSocketMessage(event);
        } catch (error) {
          console.error('=== WebSocket Parse Error ===', {
            error,
            rawData: event.data
          });
          logger.error('Failed to parse message', {
            error,
            rawData: event.data
          });
        }
        logger.groupEnd();
      };
      logger.groupEnd();
    };

    connectWebSocket();
    return () => {
      if (wsRef.current) {
        logger.log('Cleaning up WebSocket connection');
        wsRef.current.close();
      }
    };
  }, []);

  // Handle WebSocket messages
  const handleWebSocketMessage = async (event: MessageEvent) => {
    logger.group('WebSocket Message');
    logger.log('Raw message:', event.data);
    
    try {
        // Parse the message if it's a string
        const message = typeof event.data === 'string' ? JSON.parse(event.data) : event.data;
        logger.log('Processed message:', message);
        
        // Handle completion messages
        if (message.type === 'complete') {
            setMessages(prev => [...prev, {
                type: 'agent',
                content: message.data
            }]);
            setIsExecuting(false);  // Stop execution when task is complete
            return;
        }
        
        // Handle error messages
        if (message.type === 'error') {
            setMessages(prev => [...prev, {
                type: 'error',
                content: message.data
            }]);
            setIsExecuting(false);  // Stop execution on error
            return;
        }
        
        // Handle simple text messages
        if (message.type === 'message') {
            // Skip displaying message if it's a description of an action that was just executed
            if (!message.data.startsWith('Scrolling') && 
                !message.data.startsWith('Clicking') && 
                !message.data.startsWith('Typing')) {
                setMessages(prev => [...prev, {
                    type: 'agent',
                    content: message.data
                }]);
            }
            return;
        }

        // Handle action messages
        if (message.type === 'action') {
            let actionData = message.data;
            let actionMessage = '';

            // Handle backend executor format
            if (actionData.tool === 'executor' && actionData.input) {
                actionData = actionData.input;
            }

            // Handle complete action
            if (actionData.action === 'complete') {
                logger.log('Task completed:', actionData);
                setMessages(prev => [...prev, {
                    type: 'agent',
                    content: actionData.reason || 'Task completed successfully'
                }]);
                setIsExecuting(false);  // Stop execution
                return;
            }

            // Handle scroll actions
            if (actionData.action === 'scroll') {
                logger.log('Processing scroll action', actionData);
                actionMessage = `Scrolling ${actionData.direction} by ${actionData.pixels} pixels`;
                
                try {
                    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
                    if (!tab?.id) {
                        throw new Error('No active tab found');
                    }

                    // Send scroll action to background script
                    const messageToBackground = {
                        type: 'EXECUTE_ACTION',
                        action: {
                            action: 'scroll',
                            direction: actionData.direction,
                            pixels: actionData.pixels
                        },
                        tabId: tab.id
                    };
                    
                    logger.log('Sending scroll action to background', messageToBackground);
                    chrome.runtime.sendMessage(messageToBackground, (response) => {
                        logger.log('Background response (scroll)', response);
                        handleActionResult(response);
                    });
                } catch (error) {
                    logger.error('Failed to execute scroll action', error);
                    handleActionResult({
                        success: false,
                        error: error instanceof Error ? error.message : 'Failed to execute scroll action'
                    });
                }
            }
            // Handle click actions
            else if (actionData.action === 'click') {
                logger.log('Processing click action', actionData);
                actionMessage = `Click on element: ${actionData.element}`;
                
                // Get the current active tab first
                try {
                    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
                    if (!tab?.id) {
                        throw new Error('No active tab found');
                    }

                    // Send click action to background script
                    const messageToBackground = {
                        type: 'EXECUTE_ACTION',
                        action: {
                            action: 'click',
                            element: actionData.element,
                            element_data: actionData.element_data
                        },
                        tabId: tab.id  // Include the tab ID in the message
                    };
                    
                    logger.log('Sending click action to background', messageToBackground);
                    chrome.runtime.sendMessage(messageToBackground, (response) => {
                        logger.log('Background response (click)', response);
                        handleActionResult(response);
                    });
                } catch (error) {
                    logger.error('Failed to execute click action', error);
                    handleActionResult({
                        success: false,
                        error: error instanceof Error ? error.message : 'Failed to execute click action'
                    });
                }
            }
            // Handle type actions
            else if (actionData.action === 'type') {
                logger.log('Processing type action', actionData);
                actionMessage = `Typing text: ${actionData.text}`;
                
                try {
                    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
                    if (!tab?.id) {
                        throw new Error('No active tab found');
                    }

                    // Send type action to background script with the correct structure
                    const messageToBackground = {
                        type: 'EXECUTE_ACTION',
                        action: {
                            action: 'type',
                            element_data: actionData.element_data,
                            text: actionData.text  // Make sure text is passed correctly
                        },
                        tabId: tab.id
                    };
                    
                    logger.log('Sending type action to background', messageToBackground);
                    chrome.runtime.sendMessage(messageToBackground, (response) => {
                        logger.log('Background response (type)', response);
                        handleActionResult(response);
                    });
                } catch (error) {
                    logger.error('Failed to execute type action', error);
                    handleActionResult({
                        success: false,
                        error: error instanceof Error ? error.message : 'Failed to execute type action'
                    });
                }
            }
            // Handle keypress actions
            else if (actionData.action === 'keypress') {
                logger.log('Processing keypress action', actionData);
                actionMessage = `Pressing key: ${actionData.key}`;
                
                try {
                    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
                    if (!tab?.id) {
                        throw new Error('No active tab found');
                    }

                    // Send keypress action to background script
                    const messageToBackground = {
                        type: 'EXECUTE_ACTION',
                        action: {
                            action: 'keypress',
                            key: actionData.key
                        },
                        tabId: tab.id
                    };
                    
                    logger.log('Sending keypress action to background', messageToBackground);
                    chrome.runtime.sendMessage(messageToBackground, (response) => {
                        logger.log('Background response (keypress)', response);
                        handleActionResult(response);
                    });
                } catch (error) {
                    logger.error('Failed to execute keypress action', error);
                    handleActionResult({
                        success: false,
                        error: error instanceof Error ? error.message : 'Failed to execute keypress action'
                    });
                }
            }
            // Handle wait actions
            else if (actionData.action === 'wait') {
                logger.log('Processing wait action', actionData);
                actionMessage = `Waiting for ${actionData.duration} seconds`;
                
                try {
                    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
                    if (!tab?.id) {
                        throw new Error('No active tab found');
                    }

                    // Send wait action to background script
                    const messageToBackground = {
                        type: 'EXECUTE_ACTION',
                        action: {
                            action: 'wait',
                            duration: actionData.duration
                        },
                        tabId: tab.id
                    };
                    
                    logger.log('Sending wait action to background', messageToBackground);
                    chrome.runtime.sendMessage(messageToBackground, (response) => {
                        logger.log('Background response (wait)', response);
                        handleActionResult(response);
                    });
                } catch (error) {
                    logger.error('Failed to execute wait action', error);
                    handleActionResult({
                        success: false,
                        error: error instanceof Error ? error.message : 'Failed to execute wait action'
                    });
                }
            }
            else {
                logger.error('Unknown action:', actionData);
                handleActionResult({
                    success: false,
                    error: `Unknown action type: ${actionData.action}`
                });
            }

            // Add action to messages
            if (actionMessage) {
                setMessages(prev => [...prev, {
                    type: 'action',
                    content: actionMessage
                }]);
            }
            return;
        }

        logger.error('Unknown message type:', message.type);
    } catch (error) {
        logger.error('Error processing WebSocket message:', error);
        // If it's a string message that failed JSON parsing, just display it
        if (typeof event.data === 'string') {
            try {
                const message = JSON.parse(event.data);
                if (message.type === 'error') {
                    setMessages(prev => [...prev, {
                        type: 'error',
                        content: message.data
                    }]);
                    setIsExecuting(false);  // Stop execution on error
                } else if (message.type === 'complete') {
                    setMessages(prev => [...prev, {
                        type: 'agent',
                        content: message.data
                    }]);
                    setIsExecuting(false);  // Stop execution on completion
                } else if (message.type === 'message' && 
                    !message.data.startsWith('Scrolling') && 
                    !message.data.startsWith('Clicking') && 
                    !message.data.startsWith('Typing')) {
                    setMessages(prev => [...prev, {
                        type: 'agent',
                        content: message.data
                    }]);
                }
            } catch (innerError) {
                setMessages(prev => [...prev, {
                    type: 'agent',
                    content: event.data
                }]);
            }
        }
    }
    logger.groupEnd();
  };

  // Add action result handler
  const handleActionResult = async (response: any) => {
    logger.group('Action Result');
    logger.log('Processing result', {
        success: response?.success,
        error: response?.error,
        hasScreenshot: !!response?.screenshot,
        hasHtml: !!response?.html
    });
    
    if (response && response.success) {
        try {
            // Wait for scroll animations to complete
            await new Promise(resolve => setTimeout(resolve, 750));  // Wait longer than the content script's 500ms

            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
            if (!tab.id) throw new Error('No active tab');

            // Get updated page state
            const pageState = await chrome.runtime.sendMessage({ 
                type: 'GET_PAGE_STATE',
                tabId: tab.id
            });

            if (!pageState.success) {
                throw new Error(pageState.error || 'Failed to get page state');
            }

            logger.log('Sending success response to WebSocket');
            const resultMessage = JSON.stringify({
                success: true,
                data: {
                    screenshot: pageState.screenshot,
                    html: pageState.html
                }
            });
            wsRef.current?.send(resultMessage);
        } catch (error) {
            logger.error('Failed to get page state after action', error);
            const errorMessage = JSON.stringify({
                success: false,
                error: error instanceof Error ? error.message : 'Failed to get page state after action'
            });
            wsRef.current?.send(errorMessage);
        }
    } else {
        logger.error('Sending error response to WebSocket', response?.error);
        const errorMessage = JSON.stringify({
            success: false,
            error: response?.error || 'Action failed'
        });
        wsRef.current?.send(errorMessage);

        setMessages(prev => [...prev, {
            type: 'error',
            content: response?.error || 'Action failed'
        }]);
    }
    logger.groupEnd();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!task.trim() || isExecuting || !isConnected) return;

    logger.group('Task Submission');
    logger.log('Submitting task', {
      task,
      isConnected,
      wsReadyState: wsRef.current?.readyState
    });

    setIsExecuting(true);
    setMessages(prev => [...prev, { type: 'user', content: task }]);
    setCurrentSubtask(0);

    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab.id) throw new Error('No active tab');

      // Get current page screenshot and HTML
      const response = await chrome.runtime.sendMessage({ 
        type: 'GET_PAGE_STATE',
        tabId: tab.id
      });

      if (!response.success) {
        throw new Error(response.error || 'Failed to get page state');
      }

      // Send task to WebSocket server
      const taskMessage = JSON.stringify({
        goal: task,
        screenshot: response.screenshot,
        html: response.html,
        session_id: Date.now()
      });
      logger.log('Sending task to WebSocket', {
        messageLength: taskMessage.length,
        goal: task,
        session_id: Date.now()
      });
      
      wsRef.current?.send(taskMessage);
      logger.log('Task sent successfully');

      setTask('');
    } catch (error) {
      logger.error('Failed to submit task', error);
      setMessages(prev => [...prev, { 
        type: 'error', 
        content: error instanceof Error ? error.message : 'Unknown error'
      }]);
      setIsExecuting(false);
    }
    logger.groupEnd();
  };

  const handleStop = async () => {
    if (wsRef.current) {
      wsRef.current.close();
    }
    await chrome.runtime.sendMessage({ type: 'STOP_TASK' });
    setIsExecuting(false);
    setMessages(prev => [...prev, { 
      type: 'agent', 
      content: 'Task execution stopped.'
    }]);
  };

  return (
    <div className="flex flex-col h-screen bg-white">
      {renderTestControls()}
      <div className="flex-1 overflow-y-auto p-3 flex flex-col gap-2">
        <div className={`p-2 text-sm rounded-md border-l-2 ${
          wsStatus === 'connected' ? 'bg-green-50 text-green-800 border-green-500' :
          wsStatus === 'connecting' ? 'bg-yellow-50 text-yellow-800 border-yellow-500 animate-pulse' :
          'bg-red-50 text-red-800 border-red-500 animate-pulse'
        }`}>
          <strong>WebSocket Status: </strong>
          {wsStatus === 'connected' ? 'Connected' :
           wsStatus === 'connecting' ? 'Connecting...' :
           'Disconnected. Trying to reconnect...'}
        </div>
        {!isConnected && (
          <div className="p-2 bg-red-50 text-red-800 text-sm rounded-md border-l-2 border-red-500 animate-pulse">
            <strong>Connection Status: </strong>
            Disconnected. Trying to reconnect...
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`p-2 rounded-lg text-sm shadow-sm ${
            msg.type === 'user' ? 'bg-blue-600 text-white ml-auto' :
            msg.type === 'agent' ? 'bg-gray-100 mr-auto' :
            msg.type === 'action' ? 'bg-green-50 text-green-800 mr-auto' :
            msg.type === 'error' ? 'bg-red-50 text-red-800 mr-auto' :
            msg.type === 'progress' ? 'bg-gray-50 text-gray-600 mx-auto inline-flex items-center gap-2' :
            msg.type === 'plan' ? 'bg-gray-50 mr-auto w-[85%]' : ''
          } ${
            msg.isReplanning ? 'bg-orange-50 border-l-2 border-orange-500' : ''
          }`}>
            {msg.type === 'user' && <strong>You: </strong>}
            {msg.type === 'agent' && <strong>Agent: </strong>}
            {msg.type === 'action' && <strong>Action: </strong>}
            {msg.type === 'error' && <strong>Error: </strong>}
            {msg.type === 'plan' && (
              <>
                <strong className={msg.isReplanning ? 'text-orange-600' : ''}>
                  {msg.isReplanning ? 'Replanning: ' : 'Plan: '}
                </strong>
                {msg.content}
                <ul className="mt-1.5 ml-5 text-sm list-disc">
                  {msg.subtasks?.map((subtask, j) => (
                    <li key={j} className={`text-gray-600 my-0.5 ${
                      j < currentSubtask ? 'text-green-600 line-through' : ''
                    }`}>
                      {subtask}
                    </li>
                  ))}
                </ul>
              </>
            )}
            {msg.type === 'progress' && (
              <>
                <strong>Progress: </strong>
                {msg.content}
                {msg.progress !== undefined && msg.total && (
                  <div className="w-16 h-1 bg-gray-200 rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-blue-500 transition-all duration-300"
                      style={{ width: `${(msg.progress / msg.total) * 100}%` }}
                    />
                  </div>
                )}
              </>
            )}
            {msg.type !== 'plan' && msg.type !== 'progress' && msg.content}
          </div>
        ))}
      </div>
      <form onSubmit={handleSubmit} className="p-3 flex gap-2 border-t border-gray-200">
        <input
          type="text"
          value={task}
          onChange={(e) => setTask(e.target.value)}
          placeholder="Enter your task..."
          disabled={isExecuting || !isConnected}
          className="flex-1 px-3 py-2 text-sm border border-gray-200 rounded-md
            focus:outline-none focus:ring-2 focus:ring-blue-500/10 focus:border-blue-500
            disabled:bg-gray-50"
        />
        {isExecuting ? (
          <button 
            type="button" 
            onClick={handleStop}
            className="px-4 py-2 text-sm font-medium text-white bg-red-500 rounded-md
              hover:bg-red-600 hover:-translate-y-0.5 transition-all"
          >
            Stop
          </button>
        ) : (
          <button 
            type="submit" 
            disabled={!task.trim() || !isConnected}
            className="px-4 py-2 text-sm font-medium text-white bg-blue-500 rounded-md
              hover:bg-blue-600 hover:-translate-y-0.5 transition-all
              disabled:bg-gray-200 disabled:text-gray-400 disabled:hover:translate-y-0"
          >
            Start
          </button>
        )}
      </form>
    </div>
  );
} 