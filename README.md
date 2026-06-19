# Parliamo di Musica

A fully local, privacy-focused AI chat app for music questions. It combines:

- **FastAPI** backend
- **Chainlit** chat UI at `/chat`
- **Ollama** with `qwen3:8b` for local inference
- **Music tools**: MusicBrainz, Last.fm, and optional Genius

## Quick start

1. Copy environment variables and add your API keys:

```bash
cp .env.example .env
```

2. Set `LASTFM_API_KEY` in `.env` (required for recommendations and similar artists/tracks).
   Get a free key at https://www.last.fm/api/account/create.
   Optionally set `GENIUS_ACCESS_TOKEN` for lyrics lookup at https://genius.com/developers.

3. Start the stack:

```bash
docker compose up --build
```

The first run pulls `qwen3:8b`, which can take several minutes.

4. Open the app:

- Chat UI: http://localhost:8000/chat
- API root: http://localhost:8000/
- Health: http://localhost:8000/health
- Ollama test: http://localhost:8000/test-ollama

## Example questions

- "Recommend artists similar to Daft Punk"
- "Find tracks similar to Get Lucky by Daft Punk"
- "Who is Miles Davis and what are his notable releases?"
- "Get lyrics for Bohemian Rhapsody"
- "What is Hotel California about?"

## Project structure

```
backend/
├── main.py              # FastAPI entrypoint + Chainlit mount
├── chainlit_app.py      # Chainlit handlers
├── config.py            # Settings from environment
├── llm/                 # Ollama client + chat orchestration
├── tools/               # MusicBrainz, Last.fm, Genius tools
└── persistence/         # SQLite chat history
```

## Development

Code is mounted into the API container with hot reload. After adding dependencies:

```bash
docker compose build api
docker compose up
```

View logs:

```bash
docker compose logs -f api ollama
```

## GPU support

If you have an NVIDIA GPU, uncomment the GPU section in `docker-compose.yml` for faster inference.

## Notes

- Chat history is stored in a Docker volume at `/app/data/chat.db`.
- MusicBrainz works without credentials (only a User-Agent is required).
- Last.fm requires a free API key; Genius is optional for lyrics.
- Full lyrics are not reproduced; the assistant summarizes themes and links to Genius when available.