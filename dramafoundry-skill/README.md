# DramaFoundry skill fork

Fork of the upstream novel-to-video agent skill, Fornace-owned. Original kept
untouched at `../.hermes/skills/dramafoundry/`.

Identity: DramaFoundry is the product and assistant name. No upstream 虾导/SuperTale branding.

## Environment

- `FORNACE_GATEWAY_URL`: backend base. Team install sets `https://dramafoundry.fornace.net`; local development defaults to `http://127.0.0.1:8780`.
- `FORNACE_AGENT_TOKEN`: persistent team credential in `~/.pi/agent/credentials/dramafoundry.json`, provisioned by `pi fornace install` and reconciled by `pi fornace update`.
- `FORNACE_PROJECT_ID`: bound project id (ULID from `POST /api/v1/projects`). A project is selected or created after account provisioning.

## Stack this skill drives

- Backend: DramaFoundry CE (`src/novelvideo`), FastAPI, port 8780
- Gateway: dramafoundry-gateway (Go), port 3300, channels: mantice (llm.fornace.net) + fal
- Models: fornace-fast / fornace-vision / fornace-embed (LLM tiers),
  fornace-image / fornace-image-lite (sketches, portraits),
  h3-max / h3-max-turbo / kling-3-pro / wan-3 (video), index-tts-2 (voice)

## Differences from the original

- Env contract: `DRAMAFOUNDRY_API_URL`/`DRAMAFOUNDRY_AGENT_TOKEN`/`DRAMAFOUNDRY_PROJECT_ID`
  reduced to `FORNACE_GATEWAY_URL`/`FORNACE_PROJECT_ID`, with `FORNACE_AGENT_TOKEN` provisioned for the hosted team instance.
- Identity text: 虾导 -> DramaFoundry, DramaFoundry -> DramaFoundry, 虾料 -> 剧本上传页, 虾塘 -> 声线库.
- Tool names: `dramaclaw_*` -> `fornace_*`; in this fork they are plain HTTP calls
  (curl semantics) against the local backend, not a hosted plugin surface.
- Chinese trigger vocabulary and all pipeline discipline rules unchanged.
- Default video backend line updated: `huimeng_seedance-1.0-pro-fast` -> `h3-max`
  (edit SKILL.md §5 default model if the fleet changes).
