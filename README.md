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

## RAG over Units (Supabase)

To enable retrieval-augmented answers from your `units_rows.csv` data:

- Ensure env vars are available (either exported or in a `.env` file):
  - `OPENAI_API_KEY`
  - `SUPABASE_URL`
  - `SUPABASE_SERVICE_ROLE_KEY` (preferred for ingestion) or `SUPABASE_ANON_KEY`

- In your Supabase SQL editor, apply the vector schema and RPC:
  - `supabase/schema_rag.sql` (creates `units_embeddings` and `match_units` RPC)

  If you also use the relational `units` table, see `supabase/schema.sql` for a baseline schema.

- Prepare your data CSV at `supabase/units_rows.csv` (already included per instructions).

- Ingest embeddings (one-off or whenever the CSV changes):

  ```bash
  python supabase/ingest_units_embeddings.py
  ```

  This script:
  - Reads `supabase/units_rows.csv`
  - Builds a compact text summary per row
  - Creates OpenAI embeddings (text-embedding-3-small)
  - Upserts rows into `public.units_embeddings` in Supabase

- Run the chat app. The assistant fetches top-k matches via `match_units` and includes them in the prompt as context.

Notes:
- If you restrict RLS, grant your chosen role execute on `public.match_units` and write access to `public.units_embeddings` for ingestion.
- You can tune `k` and `min_similarity` inside `supabase/retriever.py` or by changing the call in `context_window.py`.
