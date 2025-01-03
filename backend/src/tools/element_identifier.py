"""Element identification using LLM."""
import logging
import json
import re
from typing import Dict, Any, List
from langchain_core.language_models.base import BaseLanguageModel

logger = logging.getLogger(__name__)

class ElementIdentifier:
    """Handles element identification using LLM."""
    def __init__(self, model: BaseLanguageModel):
        self.model = model

    def identify_element(self, element_desc: str, html: str) -> Dict[str, Any]:
        """Identify DOM element based on description."""
        logger.info(f"=== Identifying Element === Description: {element_desc}")
        
        try:
            # Get LLM response
            response = self._get_llm_response(element_desc, html)
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

    def _get_llm_response(self, element_desc: str, html: str) -> str:
        """Get response from LLM."""
        prompt = self._build_prompt(element_desc, html)
        messages = self._build_messages(prompt)
        
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
1. PREFER these selector strategies in order:
   - Simple link selector: a[href*='relevant-text']
   - Simple class selector: .classname
   - Simple attribute selector: [data-testid='x']
   - Parent class + element: .title a, .titleline a
   - Table cell + class: td.title, td.votelinks

2. For table structures:
   - Avoid using tr# or td# with IDs as they may change
   - Use class names instead: td.title, td.votelinks
   - For nested elements use immediate child: td.title > a
   - For deeper nesting use classes: .titleline a[href]

3. For links and anchors:
   - Use href partial match: a[href*='relevant-text']
   - Use simple class: a.clicky
   - Combine with parent if needed: .title a[href]
   - Avoid complex attribute combinations

4. NEVER use these selectors:
   - IDs with numbers (they change frequently)
   - Complex chains of > operators
   - Attribute selectors with full URLs
   - nth-child or nth-of-type
   - Comma-separated complex selectors

5. Special Cases:
   - For vote arrows: .votearrow or a.clicky
   - For title links: .titleline a[href]
   - For site bits: .sitebit a
   - For comments: .comment a

Example Responses:
For a vote arrow:
{{
    "selector": "a.clicky .votearrow",
    "element_type": "div",
    "text_content": "upvote",
    "confidence": 0.95
}}

For a title link:
{{
    "selector": ".titleline a[href]",
    "element_type": "link",
    "text_content": "Article Title",
    "confidence": 0.95
}}

For a table cell:
{{
    "selector": "td.votelinks",
    "element_type": "cell",
    "text_content": "",
    "confidence": 0.95
}}

Analyze the HTML and provide the element details in the specified JSON format."""

    @staticmethod
    def _build_messages(prompt: str) -> List[Dict[str, str]]:
        """Build messages for LLM."""
        return [
            {
                "role": "system", 
                "content": """You are an expert at analyzing HTML and identifying DOM elements. 
                You specialize in handling complex table structures and news aggregator sites.
                You ALWAYS generate simple, reliable CSS selectors that won't break.
                You NEVER use IDs or complex chains of selectors.
                You ALWAYS respond with valid JSON in the exact format specified in the prompt.
                You NEVER include explanations or additional text outside the JSON structure."""
            },
            {"role": "user", "content": prompt}
        ] 