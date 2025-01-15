console.log('=== Background Script Starting ===');

// Function to check if URL is accessible
function isAccessibleUrl(url: string): boolean {
  return !url.startsWith('chrome://') && !url.startsWith('chrome-extension://');
}

// Rate limiting for screenshot capture
let lastScreenshotTime = 0;
const MIN_SCREENSHOT_INTERVAL = 1000; // Minimum 1 second between screenshots

// Function to get page state
async function getPageState(tabId: number) {
  try {
    console.log('=== Getting Page State ===', { tabId });
    
    // Get current window ID
    const tab = await chrome.tabs.get(tabId);
    console.log('=== Tab Info ===', { 
      url: tab.url,
      status: tab.status,
      active: tab.active
    });

    if (!tab.url || !isAccessibleUrl(tab.url)) {
      throw new Error('Cannot access this type of page. Please try on a regular webpage.');
    }

    const windowId = tab.windowId;
    
    // Rate limit screenshot capture
    const currentTime = Date.now();
    if (currentTime - lastScreenshotTime < MIN_SCREENSHOT_INTERVAL) {
      console.log('=== Screenshot rate limit hit, skipping screenshot ===');
      return {
        success: true,
        html: await getPageHtml(tabId),
        screenshot: null  // Skip screenshot if we're rate limited
      };
    }
    
    // Get screenshot with proper window ID
    const screenshot = await chrome.tabs.captureVisibleTab(windowId, {
      format: 'png'
    });
    lastScreenshotTime = Date.now();

    // Get HTML content
    const html = await getPageHtml(tabId);

    console.log('=== Got Page State Successfully ===');
    return {
      success: true,
      screenshot,
      html
    };
  } catch (error) {
    console.error('=== Error Getting Page State ===', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Failed to get page state'
    };
  }
}

// Separate function to get HTML content
async function getPageHtml(tabId: number): Promise<string> {
  const [{ result }] = await chrome.scripting.executeScript({
    target: { tabId },
    func: () => document.documentElement.outerHTML
  });
  return result || '';
}

// Function to execute browser action
async function executeBrowserAction(tabId: number, action: any) {
  try {
    console.log('=== Executing Browser Action ===', { tabId, action });
    
    // Check if we can access this tab
    const tab = await chrome.tabs.get(tabId);
    if (!tab.url || !isAccessibleUrl(tab.url)) {
      throw new Error('Cannot execute actions on this type of page. Please try on a regular webpage.');
    }

    // Forward action to content script
    return new Promise((resolve) => {
      console.log('=== Forwarding action to content script ===', {
        tabId,
        action,
        url: tab.url
      });

      // First try to ping the content script
      chrome.tabs.sendMessage(tabId, { type: 'PING' }, (pingResponse) => {
        console.log('=== Content Script Ping Response ===', pingResponse);
        
        if (chrome.runtime.lastError) {
          console.error('=== Content Script Not Ready ===', chrome.runtime.lastError);
          // If content script is not ready, inject it
          chrome.scripting.executeScript({
            target: { tabId },
            files: ['content.js']
          }).then(() => {
            console.log('=== Content Script Injected ===');
            // Now send the action
            chrome.tabs.sendMessage(tabId, { type: 'EXECUTE_ACTION', action }, (response) => {
              console.log('=== Content Script Response (after injection) ===', response);
              resolve(response || { success: false, error: 'No response from content script' });
            });
          }).catch((error) => {
            console.error('=== Failed to inject content script ===', error);
            resolve({ success: false, error: 'Failed to inject content script' });
          });
        } else {
          // Content script is ready, send the action
          chrome.tabs.sendMessage(tabId, { type: 'EXECUTE_ACTION', action }, (response) => {
            console.log('=== Content Script Response ===', response);
            resolve(response || { success: false, error: 'No response from content script' });
          });
        }
      });
    });
  } catch (error) {
    console.error('=== Error in executeBrowserAction ===', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Failed to execute action'
    };
  }
}

// Listen for messages from the popup/sidepanel
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  console.log('=== Received Message ===', message);

  if (message.type === 'GET_PAGE_STATE') {
    handleGetPageState(message.tabId).then(sendResponse);
    return true;
  }

  if (message.type === 'EXECUTE_ACTION') {
    handleExecuteAction(message.action, message.tabId).then(sendResponse);
    return true;
  }

  if (message.type === 'STOP_TASK') {
    // Handle task stopping logic here
    sendResponse({ success: true });
    return true;
  }
});

async function handleGetPageState(tabId: number) {
  try {
    // Get the active tab
    const tab = await chrome.tabs.get(tabId);
    console.log('=== Found Active Tab ===', { tabId, tab });

    // Get the window ID from the tab
    const windowId = tab.windowId;

    // Take screenshot
    const screenshot = await chrome.tabs.captureVisibleTab(windowId, {
      format: 'jpeg',
      quality: 70
    });

    // Get page HTML
    const [{ result: html }] = await chrome.scripting.executeScript({
      target: { tabId },
      func: () => document.documentElement.outerHTML
    });

    return {
      success: true,
      screenshot,
      html
    };
  } catch (error) {
    console.error('=== Error Getting Page State ===', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Failed to get page state'
    };
  }
}

async function handleExecuteAction(action: any, tabId?: number) {
  if (!tabId) {
    console.error('=== No Tab ID Provided ===');
    return { success: false, error: 'No tab ID provided' };
  }

  console.log('=== Executing Browser Action ===', { tabId, action });

  // Add debug logging for search interactions
  if (action.action === 'click' && action.element_data?.element_type === 'input') {
    console.log('=== Search Interaction: Clicking Input ===', action.element_data);
  } else if (action.action === 'type') {
    console.log('=== Search Interaction: Typing Text ===', { text: action.text });
  } else if (action.action === 'keypress' && action.key === 'Enter') {
    console.log('=== Search Interaction: Pressing Enter ===');
  }

  try {
    // Get the tab URL
    const tab = await chrome.tabs.get(tabId);
    console.log('=== Forwarding action to content script ===', { tabId, action, url: tab.url });

    // First ping the content script to see if it's ready
    try {
      await chrome.tabs.sendMessage(tabId, { type: 'PING' });
      console.log('=== Content Script Ready ===');
    } catch (error) {
      // Content script not ready, inject it
      console.log('=== Content Script Not Ready, Injecting ===');
      await chrome.scripting.executeScript({
        target: { tabId },
        files: ['content.js']
      });
      console.log('=== Content Script Injected ===');

      // Wait a bit for the content script to initialize
      await new Promise(resolve => setTimeout(resolve, 100));
    }

    // Now send the action
    return new Promise((resolve) => {
      chrome.tabs.sendMessage(tabId, {
        type: 'EXECUTE_ACTION',
        action: action
      }, (response) => {
        console.log('=== Content Script Response ===', response);
        
        if (chrome.runtime.lastError) {
          console.error('=== Content Script Error ===', chrome.runtime.lastError);
          resolve({ success: false, error: chrome.runtime.lastError.message });
          return;
        }

        if (!response) {
          console.error('=== No Response from Content Script ===');
          resolve({ success: false, error: 'No response from content script' });
          return;
        }

        // For scroll actions, check the response details
        if (action.action === 'scroll') {
          console.log('=== Processing Scroll Response ===', response);
          if (response && typeof response === 'object') {
            if (response.success && response.details) {
              const { isAtTop, isAtBottom, scrolled, actualChange } = response.details;
              
              // Handle different scroll scenarios
              if (action.direction === 'up' && isAtTop) {
                resolve({
                  success: true,
                  result: action,
                  details: response.details,
                  message: 'Already at the top of the page'
                });
              } else if (action.direction === 'down' && isAtBottom) {
                resolve({
                  success: true,
                  result: action,
                  details: response.details,
                  message: 'Already at the bottom of the page'
                });
              } else if (!scrolled || actualChange === 0) {
                resolve({
                  success: true,
                  result: action,
                  details: response.details,
                  message: 'No scroll needed or possible'
                });
              } else {
                resolve({
                  success: true,
                  result: action,
                  details: response.details,
                  message: `Scrolled ${action.direction} by ${Math.abs(actualChange)} pixels`
                });
              }
            } else if (response.error) {
              resolve({
                success: false,
                error: response.error
              });
            } else {
              resolve({
                success: false,
                error: 'Invalid scroll response format: missing details'
              });
            }
          } else {
            resolve({
              success: false,
              error: 'Invalid scroll response format: not an object'
            });
          }
          return;
        }

        // For click actions, get updated page state
        if (action.action === 'click') {
          if (response.success) {
            handleGetPageState(tabId).then(pageState => {
              resolve({
                ...pageState,
                details: {
                  ...response.details,
                  screenshot: pageState.screenshot,
                  html: pageState.html
                }
              });
            }).catch(error => {
              resolve({
                success: false,
                error: `Click succeeded but failed to get page state: ${error.message}`
              });
            });
          } else {
            resolve({
              success: false,
              error: response.details?.error || 'Click action failed'
            });
          }
          return;
        }

        // For type actions
        if (action.action === 'type') {
          if (response.success) {
            handleGetPageState(tabId).then(pageState => {
              resolve({
                ...pageState,
                details: {
                  ...response.details,
                  screenshot: pageState.screenshot,
                  html: pageState.html
                }
              });
            }).catch(error => {
              resolve({
                success: false,
                error: `Type action succeeded but failed to get page state: ${error.message}`
              });
            });
          } else {
            resolve({
              success: false,
              error: response.details?.error || 'Type action failed'
            });
          }
        }

        // For wait actions
        if (action.action === 'wait') {
          if (response.success) {
            handleGetPageState(tabId).then(pageState => {
              resolve({
                ...pageState,
                details: {
                  ...response.details,
                  screenshot: pageState.screenshot,
                  html: pageState.html
                }
              });
            }).catch(error => {
              resolve({
                success: false,
                error: `Wait action succeeded but failed to get page state: ${error.message}`
              });
            });
          } else {
            resolve({
              success: false,
              error: response.details?.error || 'Wait action failed'
            });
          }
          return;
        }

        // Default response
        resolve(response);
      });
    });
  } catch (error) {
    console.error('=== Action Execution Error ===', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error occurred'
    };
  }
}

// Extension icon click handler
chrome.action.onClicked.addListener((tab) => {
  console.log('=== Extension Icon Clicked ===', { tabId: tab.id });
  chrome.sidePanel.open({ windowId: tab.windowId });
});

console.log('=== Background Script Ready ==='); 