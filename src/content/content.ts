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

  interface ScrollAction {
    action: 'scroll';
    direction: 'up' | 'down';
    pixels: number;
  }

  // Function to handle scroll
  function handleScroll(action: ScrollAction | string) {
    logger.log('Handling Scroll Action', { action, type: typeof action });
    
    try {
      let scrollAmount: number;
      
      if (typeof action === 'string') {
        // Parse string-formatted scroll action
        const match = action.match(/\[(.*?)\]/);
        if (!match) {
          throw new Error('Invalid scroll action format');
        }
        
        const actionStr = match[1];
        logger.log('Parsed String Action', actionStr);
        
        // Extract direction and pixels
        const parts = actionStr.split(' ');
        if (parts[0] !== 'scroll' || !['up', 'down'].includes(parts[1]) || parts[2] !== 'by' || isNaN(parseInt(parts[3]))) {
          throw new Error('Invalid scroll action format');
        }
        
        scrollAmount = parts[1] === 'up' ? -parseInt(parts[3]) : parseInt(parts[3]);
      } else {
        // Handle structured scroll action
        logger.log('Handling Structured Action', action);
        
        // Ensure we have a valid scroll action
        if (!action || typeof action !== 'object') {
          throw new Error('Invalid scroll action: not an object');
        }
        
        // Handle potentially nested action structure
        const scrollAction = 'type' in action ? action.action : action;
        logger.log('Extracted Scroll Action', scrollAction);
        
        if (!scrollAction || typeof scrollAction !== 'object') {
          throw new Error('Invalid scroll action: missing action object');
        }
        
        if (!scrollAction.direction || !scrollAction.pixels || !['up', 'down'].includes(scrollAction.direction)) {
          throw new Error(`Invalid scroll action format: ${JSON.stringify(scrollAction)}`);
        }
        
        scrollAmount = scrollAction.direction === 'up' ? -scrollAction.pixels : scrollAction.pixels;
      }
      
      // Log current scroll position and document dimensions
      const startPosition = window.scrollY;
      const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
      
      logger.log('Scroll Details', {
        startPosition,
        scrollAmount,
        maxScroll,
        documentHeight: document.documentElement.scrollHeight,
        viewportHeight: window.innerHeight,
        canScroll: maxScroll > 0
      });

      // Create visual indicator
      const indicator = document.createElement('div');
      indicator.style.cssText = `
        position: fixed;
        ${scrollAmount > 0 ? 'bottom' : 'top'}: 20px;
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
      indicator.textContent = `Scrolling ${scrollAmount > 0 ? 'down' : 'up'} by ${Math.abs(scrollAmount)}px`;
      document.body.appendChild(indicator);

      // Try different scroll methods
      const scrollMethods = [
        // Method 1: window.scrollBy with smooth behavior
        () => {
          logger.log('Trying window.scrollBy with smooth behavior');
          window.scrollBy({
            top: scrollAmount,
            behavior: 'smooth'
          });
        },
        // Method 2: window.scrollTo with smooth behavior
        () => {
          logger.log('Trying window.scrollTo with smooth behavior');
          window.scrollTo({
            top: Math.max(0, Math.min(startPosition + scrollAmount, maxScroll)),
            behavior: 'smooth'
          });
        },
        // Method 3: Direct scroll with requestAnimationFrame
        () => {
          logger.log('Trying requestAnimationFrame scroll');
          const startTime = performance.now();
          const duration = 500; // 500ms animation
          
          function animate(currentTime: number) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);
            
            // Ease-out function
            const easeProgress = 1 - Math.pow(1 - progress, 3);
            
            const currentScroll = startPosition + (scrollAmount * easeProgress);
            window.scrollTo(0, currentScroll);
            
            if (progress < 1) {
              requestAnimationFrame(animate);
            }
          }
          
          requestAnimationFrame(animate);
        },
        // Method 4: Element.scrollIntoView
        () => {
          logger.log('Trying scrollIntoView');
          const targetY = startPosition + scrollAmount;
          const elements = document.elementsFromPoint(window.innerWidth / 2, targetY);
          if (elements.length > 0) {
            elements[0].scrollIntoView({
              behavior: 'smooth',
              block: scrollAmount > 0 ? 'end' : 'start'
            });
          }
        }
      ];

      // Try each method in sequence
      let methodIndex = 0;
      const tryNextMethod = () => {
        if (methodIndex < scrollMethods.length) {
          try {
            logger.log(`Attempting scroll method ${methodIndex + 1}`);
            scrollMethods[methodIndex]();
            methodIndex++;
          } catch (error) {
            logger.log(`Method ${methodIndex + 1} failed, trying next method`, error);
            methodIndex++;
            tryNextMethod();
          }
        }
      };

      tryNextMethod();

      // Return a promise that resolves after the scroll completes
      return new Promise<any>((resolve) => {
        setTimeout(() => {
          const endPosition = window.scrollY;
          const actualChange = endPosition - startPosition;
          const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
          
          logger.log('Scroll Complete', {
            startPosition,
            endPosition,
            requestedChange: scrollAmount,
            actualChange,
            success: Math.abs(actualChange) > 0,
            isAtBottom: Math.abs(maxScroll - endPosition) < 10,
            isAtTop: endPosition <= 0
          });
          
          indicator.remove();
          
          resolve({
            success: Math.abs(actualChange) > 0,
            details: {
              scrolled: Math.abs(actualChange) > 0,
              startPosition,
              endPosition,
              requestedChange: scrollAmount,
              actualChange,
              isAtBottom: Math.abs(maxScroll - endPosition) < 10,
              isAtTop: endPosition <= 0,
              maxScroll: maxScroll
            }
          });
        }, 1000); // Increased wait time for smooth scroll
      });
    } catch (error) {
      logger.error('Error Handling Scroll', error);
      return Promise.resolve({
        success: false,
        details: { error: error instanceof Error ? error.message : 'Unknown error' }
      });
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
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
      logger.log('Message Received', {
        type: message.type,
        action: message.action,
        sender
      });

      // Handle PING message
      if (message.type === 'PING') {
        logger.log('Received PING');
        sendResponse({ status: 'ready' });
        return true;
      }

      // Handle action execution
      if (message.type === 'EXECUTE_ACTION') {
        logger.log('Executing Action', message.action);
        
        // Handle scroll actions
        if ((typeof message.action === 'string' && message.action.includes('scroll')) || 
            (typeof message.action === 'object' && 
             ((message.action.action === 'scroll') || 
              (message.action.type === 'EXECUTE_ACTION' && message.action.action?.action === 'scroll')))) {
          
          logger.log('Detected Scroll Action', message.action);
          
          // Extract the actual scroll action
          const scrollAction = typeof message.action === 'object' 
            ? (message.action.type === 'EXECUTE_ACTION' ? message.action.action : message.action)
            : message.action;
          
          logger.log('Extracted Scroll Action', scrollAction);
          
          // Execute scroll
          handleScroll(scrollAction)
            .then(result => {
              logger.log('Scroll Action Result', result);
              sendResponse(result);
            })
            .catch(error => {
              logger.error('Scroll Action Error', error);
              sendResponse({
                success: false,
                details: { error: error instanceof Error ? error.message : String(error) }
              });
            });
          
          return true; // Keep the message channel open
        }
      }

      // Acknowledge unhandled messages
      logger.log('Unhandled Message Type', message.type);
      sendResponse({ received: true });
      return true;
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