# Parliamo di Musica

A fully local, privacy-focused AI chat app for music questions. It combines:

- **FastAPI** backend
- **Chainlit** chat UI at `/chat`
- **Ollama** with `qwen3:8b` for local inference
- **Music tools**: Spotify, MusicBrainz, and optional Genius

## Quick start

1. Copy environment variables and add your API keys:

```bash
cp .env.example .env
```

2. Set `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` in `.env` (required for Spotify tools).
   Optionally set `GENIUS_ACCESS_TOKEN` for lyrics metadata.

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

- "Recommend 5 tracks similar to Blinding Lights by The Weeknd but more synthwave"
- "Who is Miles Davis and what are his notable releases?"
- "Give me the audio features of Bohemian Rhapsody"
- "What is Hotel California about?"

## Project structure

```
backend/
├── main.py              # FastAPI entrypoint + Chainlit mount
├── chainlit_app.py      # Chainlit handlers
├── config.py            # Settings from environment
├── llm/                 # Ollama client + chat orchestration
├── tools/               # Spotify, MusicBrainz, Genius tools
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
- MusicBrainz works without credentials.
- Spotify and Genius require tokens in `.env`.
- Full lyrics are not reproduced; the assistant summarizes themes and links to Genius when available.