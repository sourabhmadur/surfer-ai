"""Element identification using LLM."""
import logging
import json
import re
from typing import Dict, Any, List
from bs4 import BeautifulSoup
from langchain_core.language_models.base import BaseLanguageModel

logger = logging.getLogger(__name__)

class ElementIdentifier:
    """Handles element identification using LLM."""
    def __init__(self, model: BaseLanguageModel):
        self.model = model

    def identify_element(self, element_desc: str, html: str, screenshot: str = None) -> Dict[str, Any]:
        """Identify DOM element based on description and screenshot."""
        logger.info(f"=== Identifying Element === Description: {element_desc}")
        
        try:
            # Preprocess HTML
            cleaned_html = self._preprocess_html(html)
            
            # Get LLM response with screenshot
            response = self._get_llm_response(element_desc, cleaned_html, screenshot)
            element_data = self._parse_llm_response(response)
            
            # Validate and log results
            self._validate_and_log_results(element_data, element_desc)
            
            return {
                "success": True,
                "element_data": element_data
            }
        except Exception as e:
            logger.error(f"Failed to identify element: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to identify element: {str(e)}"
            }

    def _preprocess_html(self, html: str) -> str:
        """Preprocess HTML to remove unnecessary elements and simplify structure."""
        try:
            original_size = len(html)
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style", "noscript"]):
                script.decompose()
            
            # Remove hidden elements
            for element in soup.find_all(style=re.compile(r"display:\s*none|visibility:\s*hidden")):
                element.decompose()
            
            # Remove elements with aria-hidden="true"
            for element in soup.find_all(attrs={"aria-hidden": "true"}):
                element.decompose()
            
            # Remove comments
            for comment in soup.find_all(text=lambda text: isinstance(text, str) and text.strip().startswith('//')):
                comment.extract()
            
            # Remove empty elements that don't contribute to structure
            for element in soup.find_all():
                if not element.get_text(strip=True) and not element.find_all() and not self._is_important_empty_element(element):
                    element.decompose()
            
            # Simplify complex nested structures
            self._simplify_structure(soup)
            
            # Pretty print with minimal indentation for readability
            cleaned_html = soup.prettify(formatter="minimal")
            final_size = len(cleaned_html)
            size_reduction = ((original_size - final_size) / original_size) * 100
            
            logger.info(f"HTML size reduced by {size_reduction:.1f}%")
            
            return cleaned_html
        except Exception as e:
            logger.warning(f"Error during HTML preprocessing: {str(e)}. Using original HTML.")
            return html

    def _simplify_structure(self, soup: BeautifulSoup):
        """Simplify complex HTML structures while preserving important elements."""
        # Remove excessive div nesting
        for div in soup.find_all('div'):
            if len(div.find_all()) == 1 and div.find().name == 'div':
                div.unwrap()
        
        # Preserve important attributes, remove others
        important_attrs = {'class', 'href', 'src', 'alt', 'title', 'aria-label', 'data-testid', 'type', 'name', 'value'}
        for tag in soup.find_all(True):
            attrs = dict(tag.attrs)
            for attr in attrs:
                if attr not in important_attrs:
                    del tag[attr]

    @staticmethod
    def _is_important_empty_element(element) -> bool:
        """Check if an empty element should be preserved."""
        important_elements = {'img', 'input', 'br', 'hr', 'meta', 'link', 'source', 'track', 'area'}
        important_attrs = {'src', 'href', 'value', 'placeholder', 'alt'}
        
        # Keep element if it's in the important elements list
        if element.name in important_elements:
            return True
        
        # Keep element if it has any important attributes
        return any(attr in important_attrs for attr in element.attrs)

    def _get_llm_response(self, element_desc: str, html: str, screenshot: str = None) -> str:
        """Get response from LLM."""
        prompt = self._build_prompt(element_desc, html)
        messages = self._build_messages(prompt, screenshot)
        
        logger.info("Sending request to LLM...")
        response = self.model.invoke(messages)
        logger.info(f"Raw LLM response: {response.content}")
        return response.content

    def _parse_llm_response(self, content: str) -> Dict[str, Any]:
        """Parse LLM response into structured data."""
        cleaned_content = re.sub(r'^```json\s*|\s*```$', '', content.strip())
        return json.loads(cleaned_content)

    def _validate_and_log_results(self, element_data: Dict[str, Any], element_desc: str):
        """Validate and log element identification results."""
        logger.info("=== Element Identified ===")
        logger.info(f"Selector: {element_data.get('selector')}")
        logger.info(f"Element Type: {element_data.get('element_type')}")
        logger.info(f"Text Content: {element_data.get('text_content')}")
        logger.info(f"Confidence: {element_data.get('confidence')}")

        if element_data.get('confidence', 0) < 0.7:
            logger.warning(f"Low confidence ({element_data.get('confidence')}) for element: {element_desc}")
        
        if not element_data.get('selector'):
            logger.error("No selector returned by LLM")
        elif 'http' in element_data['selector'].lower():
            logger.warning("Selector contains URL - this might be fragile")

    @staticmethod
    def _build_prompt(element_desc: str, html: str) -> str:
        """Build prompt for element identification."""
        return f"""Given the HTML content and element description below, identify the most appropriate DOM element.

Element Description: {element_desc}

HTML Content:
{html}

You MUST respond with a JSON object in this EXACT format:
{{
    "selector": "CSS selector to uniquely identify the element",
    "element_type": "Type of element (e.g., button, link, input)",
    "text_content": "Visible text content of the element",
    "confidence": "Number between 0 and 1 indicating confidence in the match"
}}

Requirements for selector generation:
1. ALWAYS use these selector strategies in order:
   - For exact text match: .titleline a[href*="economist.com"]
   - For partial text match: .titleline a[href*="canada"]
   - Simple class + element: .titleline a
   - Simple class: .classname

2. CRITICAL RULES:
   - NEVER use nth-child or nth-of-type
   - NEVER use IDs
   - NEVER use full URLs in selectors
   - NEVER use more than one > in a selector
   - NEVER use complex attribute combinations
   - NEVER use selectors longer than 2 parts
   - ALWAYS match text content when possible

3. For article links:
   - If text or URL is unique, use .titleline a[href*="unique-part"]
   - If domain is unique, use .titleline a[href*="domain"]
   - If neither is unique, use .titleline a and verify text content
   - ALWAYS verify the text content matches

4. Examples of GOOD selectors:
   - .titleline a[href*="economist.com"]  (for specific domain)
   - .titleline a[href*="canada"]  (for specific topic)
   - .votearrow
   - .clicky

5. Examples of BAD selectors (NEVER use):
   - tr:nth-child(4)
   - td:nth-of-type(3)
   - #id-123
   - [href="https://full.url.com"]
   - div > span > a
   - .class1 .class2 .class3 a

Example Responses:
For a specific article:
{{
    "selector": ".titleline a[href*='economist.com']",
    "element_type": "link",
    "text_content": "Why Canada Should Join the EU",
    "confidence": 0.95
}}

For a vote button:
{{
    "selector": ".votearrow",
    "element_type": "div",
    "text_content": "upvote",
    "confidence": 0.95
}}

For a navigation link:
{{
    "selector": ".morelink",
    "element_type": "link",
    "text_content": "More",
    "confidence": 0.95
}}

Analyze the HTML and provide the element details in the specified JSON format."""

    @staticmethod
    def _build_messages(prompt: str, screenshot: str = None) -> List[Dict[str, Any]]:
        """Build messages for LLM."""
        messages = [
            {
                "role": "system", 
                "content": """You are an expert at analyzing HTML and identifying DOM elements. 
                You specialize in handling complex table structures and news aggregator sites.
                You ALWAYS generate simple, reliable CSS selectors that won't break.
                You NEVER use IDs or complex chains of selectors.
                You ALWAYS respond with valid JSON in the exact format specified in the prompt.
                You NEVER include explanations or additional text outside the JSON structure."""
            }
        ]

        # Add prompt and screenshot if available
        if screenshot:
            messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": screenshot
                        }
                    }
                ]
            })
        else:
            messages.append({
                "role": "user",
                "content": prompt
            })

        return messages 