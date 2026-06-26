# AI Campus Assistant

A lightweight multi-agent campus assistant project. It classifies a student query, routes it to the most relevant expert agent, and returns a clean student-friendly answer.

## Agents

- Knowledge Agent: answers factual questions using only provided document context.
- Study Planner Agent: creates realistic study plans and revision strategies.
- Admin Help Agent: handles exams, notices, rules, fees, and faculty guidance.
- Advisor Agent: gives practical motivation, career, and productivity advice.

## Supabase Setup

1. Create a Supabase project.
2. Open the SQL editor in Supabase.
3. Run the SQL from `database/supabase_schema.sql`.
4. Copy `.env.example` to `.env`.
5. Add your Supabase project URL and anon key.

```text
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-supabase-anon-key
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
```

The app works in demo mode without Supabase, but document saving, notice saving, retrieval, and chat storage need Supabase.

OpenAI is optional and configured only on the backend through `.env`. Do not show or place the key in frontend code. Without `OPENAI_API_KEY`, the app uses the local agent logic.

## Run

```powershell
python backend/server.py
```

Then open:

```text
http://localhost:8000
```

## Project Structure

```text
backend/
  app_logic.py      Core intent classification and agent responses
  config.py         Environment loading
  rag.py            Text chunking and keyword retrieval
  server.py         Standard-library HTTP server and API
  supabase_client.py Supabase REST client
  openai_client.py Optional OpenAI Responses API client
database/
  supabase_schema.sql Tables and RLS policies
frontend/
  index.html        Student-facing web app
  styles.css        Interface styling
  app.js            Browser behavior and API calls
tests/
  test_app_logic.py Basic logic tests
```

## API

`POST /api/ask`

```json
{
  "query": "Make me a 7 day study plan for DBMS and DSA",
}
```

Other endpoints:

- `GET /api/health`
- `GET /api/documents`
- `POST /api/documents`
- `GET /api/notices`
- `POST /api/notices`

## Test

```powershell
python -B tests/test_app_logic.py
```

Response:

```json
{
  "intent": "study_plan",
  "agent": "Study Planner Agent",
  "answer": {
    "direct_answer": "...",
    "explanation": "...",
    "action_steps": ["..."]
  }
}
```
