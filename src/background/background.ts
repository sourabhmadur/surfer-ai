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

// Message handling
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  console.log('=== Background Received Message ===', {
    message,
    sender,
    senderTabId: sender.tab?.id,
    hasTab: !!sender.tab
  });
  
  if (message.type === 'GET_PAGE_STATE') {
    console.log('=== Processing GET_PAGE_STATE ===', { tabId: message.tabId });
    getPageState(message.tabId)
      .then(response => {
        console.log('=== Sending Page State Response ===', response);
        sendResponse(response);
      })
      .catch(error => {
        console.error('=== Error in GET_PAGE_STATE ===', error);
        sendResponse({ 
          success: false, 
          error: error instanceof Error ? error.message : 'Failed to get page state' 
        });
      });
    return true;
  }
  
  if (message.type === 'EXECUTE_ACTION') {
    console.log('=== Processing EXECUTE_ACTION ===', {
      message,
      senderTabId: sender.tab?.id,
      action: message.action
    });

    // For scroll actions, we need the active tab
    chrome.tabs.query({ active: true, currentWindow: true }, async (tabs) => {
      console.log('=== Found Active Tab ===', {
        tabs,
        firstTabId: tabs[0]?.id
      });

      const tabId = tabs[0]?.id;
      if (!tabId) {
        const error = 'No active tab';
        console.error('=== Error ===', error);
        sendResponse({ success: false, error });
        return;
      }

      try {
        const response = await executeBrowserAction(tabId, message.action);
        console.log('=== Action Execution Response ===', response);
        sendResponse(response);
      } catch (error) {
        console.error('=== Error Executing Action ===', error);
        sendResponse({ 
          success: false, 
          error: error instanceof Error ? error.message : 'Failed to execute action' 
        });
      }
    });
    return true;
  }
  
  sendResponse({ received: true });
  return true;
});

// Extension icon click handler
chrome.action.onClicked.addListener((tab) => {
  console.log('=== Extension Icon Clicked ===', { tabId: tab.id });
  chrome.sidePanel.open({ windowId: tab.windowId });
});

console.log('=== Background Script Ready ==='); 