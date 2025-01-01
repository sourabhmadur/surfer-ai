//@ sourceURL=chrome-extension://content-script.js
//# sourceURL=chrome-extension://content-script.js

// Immediately log to both console and DOM
(function() {
  // Force debugger to break on script load
  debugger;

  // Add console group for better visibility
  console.group('=== Content Script Initialization ===');
  console.log('Content Script Loading');
  console.log('URL:', window.location.href);
  console.log('Timestamp:', new Date().toISOString());
  console.groupEnd();

  // Create a global logger
  const logger = {
    log: (message: string, data?: any) => {
      const logMessage = data ? `${message}: ${JSON.stringify(data)}` : message;
      console.log(`%c[Content Script] ${logMessage}`, 'background: #333; color: #fff; padding: 2px 4px; border-radius: 2px;');
      showVisualLog(logMessage);
    },
    error: (message: string, error?: any) => {
      const errorMessage = error ? `${message}: ${error.message || JSON.stringify(error)}` : message;
      console.error(`%c[Content Script Error] ${errorMessage}`, 'background: #ff0000; color: #fff; padding: 2px 4px; border-radius: 2px;');
      showVisualLog(errorMessage, true);
    },
    warn: (message: string, data?: any) => {
      const warnMessage = data ? `${message}: ${JSON.stringify(data)}` : message;
      console.warn(`%c[Content Script Warning] ${warnMessage}`, 'background: #ff9900; color: #fff; padding: 2px 4px; border-radius: 2px;');
      showVisualLog(warnMessage);
    }
  };

  // Function to show visual logs
  function showVisualLog(message: string, isError = false) {
    try {
      const logElement = document.createElement('div');
      logElement.style.cssText = `
        position: fixed;
        ${isError ? 'top' : 'bottom'}: 10px;
        right: 10px;
        background: ${isError ? 'rgba(255, 0, 0, 0.8)' : 'rgba(0, 0, 0, 0.8)'};
        color: white;
        padding: 8px 12px;
        border-radius: 4px;
        z-index: 2147483647;
        font-family: sans-serif;
        font-size: 12px;
        max-width: 300px;
        word-wrap: break-word;
        pointer-events: none;
      `;
      logElement.textContent = message;
      (document.body || document.documentElement).appendChild(logElement);
      setTimeout(() => logElement.remove(), 3000);
    } catch (error) {
      console.error('Failed to show visual log:', error);
    }
  }

  // Function to handle scroll
  function handleScroll(direction: 'up' | 'down', pixels: number): Promise<ScrollResult> {
    return new Promise((resolve) => {
      // Get initial measurements
      const startPosition = window.scrollY;
      const documentHeight = Math.max(
        document.body.scrollHeight,
        document.documentElement.scrollHeight,
        document.body.offsetHeight,
        document.documentElement.offsetHeight,
        document.body.clientHeight,
        document.documentElement.clientHeight
      );
      const viewportHeight = window.innerHeight;
      const maxScroll = documentHeight - viewportHeight;

      // Log initial state
      logger.log('Scroll Initial State:', {
        startPosition,
        documentHeight,
        viewportHeight,
        maxScroll,
        direction,
        pixels
      });

      // Calculate target position
      const scrollAmount = direction === 'down' ? pixels : -pixels;
      const targetPosition = Math.max(0, Math.min(startPosition + scrollAmount, maxScroll));

      // Check if we're already at the limit
      if ((direction === 'up' && startPosition <= 0) || 
          (direction === 'down' && startPosition >= maxScroll)) {
        logger.log('Already at scroll limit', {
          direction,
          startPosition,
          maxScroll
        });
        resolve({
          success: true,
          details: {
            scrolled: false,
            startPosition,
            endPosition: startPosition,
            requestedChange: scrollAmount,
            actualChange: 0,
            isAtBottom: startPosition >= maxScroll,
            isAtTop: startPosition <= 0,
            maxScroll,
            viewportHeight,
            documentHeight
          }
        });
        return;
      }

      // Perform the scroll
      window.scrollTo({
        top: targetPosition,
        behavior: 'smooth'
      });

      // Wait for scroll to complete and check final position
      setTimeout(() => {
        const endPosition = window.scrollY;
        const actualChange = endPosition - startPosition;
        const isAtBottom = endPosition >= maxScroll - 1;
        const isAtTop = endPosition <= 0;

        // Log final state
        logger.log('Scroll Final State:', {
          startPosition,
          endPosition,
          actualChange,
          isAtBottom,
          isAtTop,
          maxScroll
        });

        resolve({
          success: true,
          details: {
            scrolled: actualChange !== 0,
            startPosition,
            endPosition,
            requestedChange: scrollAmount,
            actualChange,
            isAtBottom,
            isAtTop,
            maxScroll,
            viewportHeight,
            documentHeight
          }
        });
      }, 500);
    });
  }

  // Function to handle click actions
  function handleClick(element_data: any) {
    logger.log('Handling Click Action', { element_data });
    
    try {
      const { selector, element_type, text_content } = element_data;
      
      // Find the element using the selector
      const element = document.querySelector(selector);
      if (!element) {
        throw new Error(`Element not found with selector: ${selector}`);
      }

      // Create visual indicator
      const indicator = document.createElement('div');
      indicator.style.cssText = `
        position: fixed;
        top: 20px;
        left: 50%;
        transform: translateX(-50%);
        background: rgba(0, 0, 0, 0.7);
        color: white;
        padding: 5px 10px;
        border-radius: 4px;
        z-index: 999999;
        font-family: sans-serif;
        font-size: 12px;
      `;
      indicator.textContent = `Clicking element: ${text_content || selector}`;
      document.body.appendChild(indicator);

      // Highlight the element temporarily
      const originalOutline = element.style.outline;
      element.style.outline = '2px solid red';

      // Scroll element into view if needed
      element.scrollIntoView({ behavior: 'smooth', block: 'center' });

      // Click the element
      return new Promise<any>((resolve) => {
        setTimeout(() => {
          try {
            // Special handling for submit buttons
            if (element instanceof HTMLInputElement && element.type === 'submit') {
              // Find the parent form
              const form = element.closest('form');
              if (form) {
                // Submit the form
                form.submit();
              } else {
                // Fallback to regular click if no form found
                element.click();
              }
            } else {
              // Regular click for non-submit elements
              (element as HTMLElement).click();
            }
            
            element.style.outline = originalOutline;
            indicator.remove();
            resolve({
              success: true,
              details: {
                clicked: true,
                selector,
                element_type,
                text_content
              }
            });
          } catch (error) {
            element.style.outline = originalOutline;
            indicator.remove();
            resolve({
              success: false,
              details: {
                error: error instanceof Error ? error.message : 'Failed to click element'
              }
            });
          }
        }, 500); // Wait for scroll to complete
      });
    } catch (error) {
      logger.error('Error Handling Click', error);
      return Promise.reject(error);
    }
  }

  // First, let's add an interface for the scroll result
  interface ScrollResult {
    success: boolean;
    details?: {
      scrolled: boolean;
      startPosition: number;
      endPosition: number;
      requestedChange: number;
      actualChange: number;
      isAtBottom: boolean;
      isAtTop: boolean;
      maxScroll: number;
      viewportHeight: number;
      documentHeight: number;
    };
    error?: string;
  }

  // Add interface for action response
  interface ActionResponse {
    success: boolean;
    details: {
      error?: string;
      element?: string;
      text?: string;
      [key: string]: any;
    };
  }

  // Function to handle type action
  async function handleTypeAction(data: any): Promise<ActionResponse> {
    try {
        let targetElement: HTMLElement | null = null;
        
        logger.log('Type action data:', data);  // Add debug logging
        
        // If element_data is provided, find the element using the selector
        if (data.element_data?.selector) {
            targetElement = document.querySelector(data.element_data.selector);
            if (!targetElement) {
                return {
                    success: false,
                    details: {
                        error: `Element not found with selector: ${data.element_data.selector}`
                    }
                };
            }
        } else {
            // Fallback to currently focused element
            targetElement = document.activeElement as HTMLElement;
        }

        // Check if we have a valid input element
        if (!targetElement || !(targetElement instanceof HTMLInputElement || 
            targetElement instanceof HTMLTextAreaElement)) {
            return {
                success: false,
                details: {
                    error: 'Target element cannot accept text input'
                }
            };
        }

        // Create visual indicator
        const indicator = document.createElement('div');
        indicator.style.cssText = `
            position: fixed;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0, 0, 0, 0.7);
            color: white;
            padding: 5px 10px;
            border-radius: 4px;
            z-index: 999999;
            font-family: sans-serif;
            font-size: 12px;
        `;
        indicator.textContent = `Typing: ${data.text}`;
        document.body.appendChild(indicator);

        // Highlight the element temporarily
        const originalOutline = targetElement.style.outline;
        targetElement.style.outline = '2px solid blue';

        // Scroll element into view if needed
        targetElement.scrollIntoView({ behavior: 'smooth', block: 'center' });

        // Wait for scroll to complete
        await new Promise(resolve => setTimeout(resolve, 500));

        try {
            logger.log('Setting value:', data.text);  // Add debug logging
            
            // Focus the element
            targetElement.focus();
            
            // Set the value
            (targetElement as HTMLInputElement | HTMLTextAreaElement).value = data.text;

            // Dispatch events
            targetElement.dispatchEvent(new Event('input', { bubbles: true }));
            targetElement.dispatchEvent(new Event('change', { bubbles: true }));

            // Clean up
            targetElement.style.outline = originalOutline;
            setTimeout(() => indicator.remove(), 1000);

            return {
                success: true,
                details: {
                    element: targetElement.tagName.toLowerCase(),
                    selector: data.element_data?.selector,
                    text: data.text
                }
            };
        } catch (error) {
            targetElement.style.outline = originalOutline;
            indicator.remove();
            throw error;
        }
    } catch (error) {
        console.error('Error in handleTypeAction:', error);
        return {
            success: false,
            details: {
                error: error instanceof Error ? error.message : 'Failed to type text'
            }
        };
    }
  }

  // Function to initialize the content script
  function initializeContentScript() {
    logger.log('Initializing Content Script');
    
    // Show initialization indicator
    try {
      const indicator = document.createElement('div');
      indicator.style.cssText = `
        position: fixed;
        top: 10px;
        right: 10px;
        background: rgba(0, 128, 0, 0.8);
        color: white;
        padding: 8px 12px;
        border-radius: 4px;
        z-index: 2147483647;
        font-family: sans-serif;
        font-size: 12px;
      `;
      indicator.textContent = 'Content Script Active';
      (document.body || document.documentElement).appendChild(indicator);
      setTimeout(() => indicator.remove(), 3000);
    } catch (error) {
      console.error('Failed to show indicator:', error);
    }

    // Set up message listener
    chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
      console.log('Content script received message:', message);

      if (message.type === 'PING') {
        sendResponse({ status: 'ready' });
        return true;
      }

      if (message.type === 'EXECUTE_ACTION') {
        const action = message.action;
        
        if (action.action === 'scroll') {
          // Handle scroll action asynchronously
          handleScroll(action.direction, action.pixels)
            .then((scrollResult: ScrollResult) => {
              logger.log('Scroll Result:', scrollResult);
              sendResponse(scrollResult);
            })
            .catch((error: Error) => {
              logger.error('Scroll Error:', error);
              sendResponse({
                success: false,
                error: error.message || 'Scroll action failed'
              });
            });
          return true; // Keep the message channel open for async response
        }
        else if (action.action === 'click') {
          // Handle click action asynchronously
          handleClick(action.element_data)
            .then((clickResult: any) => {
              logger.log('Click Result:', clickResult);
              sendResponse(clickResult);
            })
            .catch((error: Error) => {
              logger.error('Click Error:', error);
              sendResponse({
                success: false,
                error: error.message || 'Click action failed'
              });
            });
          return true; // Keep the message channel open for async response
        }
        else if (action.action === 'type') {
          logger.log('Handling type action:', action);  // Add debug logging
          handleTypeAction(action)
            .then(response => {
              logger.log('Type action response:', response);
              sendResponse(response);
            })
            .catch(error => {
              logger.error('Error in type action:', error);
              sendResponse({
                success: false,
                details: {
                  error: error instanceof Error ? error.message : 'Failed to type text'
                }
              });
            });
          return true;  // Will respond asynchronously
        }
        else {
          sendResponse({
            success: false,
            details: {
              error: `Unknown action type: ${action.action}`
            }
          });
        }
        return true;  // Will respond asynchronously
      }

      logger.warn('Unhandled Message Type:', message.type);
      return false;
    });
  }

  // Initialize immediately and also on DOMContentLoaded
  try {
    initializeContentScript();
  } catch (error) {
    console.error('Failed to initialize content script immediately:', error);
  }

  // Also try on DOMContentLoaded as backup
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      try {
        initializeContentScript();
      } catch (error) {
        console.error('Failed to initialize content script on DOMContentLoaded:', error);
      }
    });
  }
})();

// Add another sourceURL at the end for redundancy
//@ sourceURL=chrome-extension://content-script.js
//# sourceURL=chrome-extension://content-script.js 