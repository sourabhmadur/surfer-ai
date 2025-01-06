export interface Action {
  action: 'click' | 'type' | 'scroll' | 'keypress';
  selector?: string;
  text?: string;
  direction?: 'up' | 'down';
  pixels?: number;
  key?: string;
  element_data?: {
    selector: string;
    element_type?: string;
    text_content?: string;
  };
} 