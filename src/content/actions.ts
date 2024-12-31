export interface Action {
  action: 'click' | 'type' | 'scroll' | 'press_key';
  selector?: string;
  text?: string;
  direction?: 'up' | 'down';
  pixels?: number;
  key?: string;
}

// Add type definitions
interface ClickResult {
  clicked: boolean;
  element: string;
}

interface TypeResult {
  typed: boolean;
  element: string;
}

interface ScrollResult {
  scrolled: boolean;
  amount: number;
}

interface KeyPressResult {
  pressed: boolean;
  key: string;
}

export async function executeAction(tabId: number, action: Action): Promise<any> {
  switch (action.action) {
    case 'click':
      if (!action.selector) {
        throw new Error('Click action requires selector');
      }
      return await clickElement(tabId, action.selector);
    case 'type':
      if (!action.selector || !action.text) {
        throw new Error('Type action requires selector and text');
      }
      return await typeText(tabId, action.selector, action.text);
    case 'scroll':
      if (!action.direction || !action.pixels) {
        throw new Error('Scroll action requires direction and pixels');
      }
      const amount = action.direction === 'up' ? -action.pixels : action.pixels;
      return await scrollPage(tabId, amount);
    case 'press_key':
      if (!action.key) {
        throw new Error('Press key action requires key');
      }
      return await pressKey(tabId, action.key);
    default:
      throw new Error(`Unknown action type: ${action.action}`);
  }
}

export async function clickElement(tabId: number, selector: string): Promise<ClickResult> {
  const result = await chrome.scripting.executeScript({
    target: { tabId },
    func: (selector: string) => {
      let element: Element | null = null;
      element = document.querySelector(selector);
      if (!element) {
        throw new Error('Element not found');
      }
      (element as HTMLElement).click();
      return { clicked: true, element: element.outerHTML };
    },
    args: [selector]
  });

  if (!result[0].result) {
    throw new Error('Failed to execute click action');
  }
  return result[0].result as ClickResult;
}

export async function typeText(tabId: number, selector: string, text: string): Promise<TypeResult> {
  const result = await chrome.scripting.executeScript({
    target: { tabId },
    func: (_selector: string, text: string) => {
      const activeElement = document.activeElement as HTMLElement;
      if (activeElement && 'value' in activeElement) {
        (activeElement as HTMLInputElement).value = text;
        activeElement.dispatchEvent(new Event('input', { bubbles: true }));
        activeElement.dispatchEvent(new Event('change', { bubbles: true }));
        return { typed: true, element: activeElement.outerHTML };
      }
      throw new Error('No active input element');
    },
    args: [selector, text]
  });

  if (!result[0].result) {
    throw new Error('Failed to execute type action');
  }
  return result[0].result as TypeResult;
}

export async function scrollPage(tabId: number, amount: number): Promise<ScrollResult> {
  const result = await chrome.scripting.executeScript({
    target: { tabId },
    func: (amount: number) => {
      window.scrollBy(0, amount);
      return { scrolled: true, amount };
    },
    args: [amount]
  });

  if (!result[0].result) {
    throw new Error('Failed to execute scroll action');
  }
  return result[0].result as ScrollResult;
}

export async function pressKey(tabId: number, key: string): Promise<KeyPressResult> {
  const result = await chrome.scripting.executeScript({
    target: { tabId },
    func: (key: string) => {
      const activeElement = document.activeElement as HTMLElement;
      if (activeElement) {
        activeElement.dispatchEvent(new KeyboardEvent('keydown', { key }));
        activeElement.dispatchEvent(new KeyboardEvent('keyup', { key }));
        return { pressed: true, key };
      }
      throw new Error('No active element');
    },
    args: [key]
  });

  if (!result[0].result) {
    throw new Error('Failed to execute key press action');
  }
  return result[0].result as KeyPressResult;
} 