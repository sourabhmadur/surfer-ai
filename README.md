# Surfer AI

A browser automation assistant that helps users navigate web pages using natural language commands and visual analysis.

## Features

- Natural language command processing
- Visual page analysis using GPT-4 Vision
- Smart scrolling with context awareness
- Support for multiple navigation goals:
  - Count-based scrolling (e.g., "scroll down 2 times")
  - Position-based scrolling (e.g., "scroll to bottom", "scroll to top")
  - Content-based scrolling (e.g., "scroll until you see X")

## Project Structure

```
surfer-ai/
├── backend/             # Python FastAPI backend
│   └── src/
│       ├── main.py     # FastAPI application
│       └── workflow.py # Core agent logic
├── src/                # Frontend React/TypeScript
├── public/             # Static assets
└── scripts/           # Utility scripts
```

## Setup

1. Install dependencies:
   ```bash
   # Backend
   cd backend
   pip install -r requirements.txt

   # Frontend
   npm install
   ```

2. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your OpenAI API key
   ```

3. Run the development servers:
   ```bash
   # Backend
   cd backend/src
   uvicorn main:app --reload

   # Frontend
   npm run dev
   ```

## Usage

1. Open the browser extension
2. Enter a navigation command (e.g., "scroll down 2 times", "scroll to bottom")
3. The AI will analyze the page and execute the appropriate scrolling actions

## Development

- Backend uses FastAPI and LangChain with GPT-4 Vision
- Frontend is a Chrome extension built with React and TypeScript
- WebSocket communication for real-time interaction

## License

MIT
