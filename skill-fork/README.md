# Fornace Video skill fork

Fork of the DramaFoundry novel-to-video agent skill, Fornace-owned. Original kept
untouched at `../.hermes/skills/dramafoundry/`.

Identity: 炉导 (agent), Fornace Video (product). No DramaFoundry / 虾导 / SuperTale branding.

## Environment

- `FORNACE_GATEWAY_URL`: backend base, default `http://127.0.0.1:8780`
- `FORNACE_PROJECT_ID`: bound project id (ULID from `POST /api/v1/projects`)
- Auth: loopback needs no token; every request carries `Cookie: st_session=local`.
  Remote deployments add `FORNACE_AGENT_TOKEN` as a Bearer token.

## Stack this skill drives

- Backend: DramaFoundry CE (`src/novelvideo`), FastAPI, port 8780
- Gateway: dramaclaw-gateway (Go), port 3300, channels: mantice (llm.fornace.net) + fal
- Models: fornace-fast / fornace-vision / fornace-embed (LLM tiers),
  fornace-image / fornace-image-lite (sketches, portraits),
  h3-max / h3-max-turbo / kling-3-pro / wan-3 (video), index-tts-2 (voice)

## Differences from the original

- Env contract: `DRAMAFOUNDRY_API_URL`/`DRAMAFOUNDRY_AGENT_TOKEN`/`DRAMAFOUNDRY_PROJECT_ID`
  reduced to `FORNACE_GATEWAY_URL`/`FORNACE_PROJECT_ID` (token only off-loopback).
- Identity text: 虾导 -> 炉导, DramaFoundry -> Fornace Video, 虾料 -> 剧本上传页, 虾塘 -> 声线库.
- Tool names: `dramaclaw_*` -> `fornace_*`; in this fork they are plain HTTP calls
  (curl semantics) against the local backend, not a hosted plugin surface.
- Chinese trigger vocabulary and all pipeline discipline rules unchanged.
- Default video backend line updated: `huimeng_seedance-1.0-pro-fast` -> `h3-max`
  (edit SKILL.md §5 default model if the fleet changes).
