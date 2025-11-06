# Sales Assistant Context Window

This repository contains a minimal desktop chat window that keeps the full
conversation context for the duration of the session using the OpenAI API.

## Setup

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Set your OpenAI API key in the environment:

   ```bash
   export OPENAI_API_KEY=your_api_key_here
   ```

## Usage

Run the application from your terminal:

```bash
python context_window.py
```

Type into the input field and press **Enter** or click **Send** to converse with
the model. The conversation history is automatically preserved in the window for
the entire session.