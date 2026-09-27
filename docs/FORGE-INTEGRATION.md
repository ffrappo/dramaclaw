# DramaFoundry × Fornace integration plan

Date: 2026-09-26. Owner: Francesco. Executor: this worker session, reviewed by the
pi-fornace-supervisor-stack supervisor.

## What DramaFoundry is (studied, not guessed)

- Source: github.com/dramaclaw/dramaclaw (Elastic-2.0, "SuperTale CE" python pkg
  `novelvideo`) + gateway repo github.com/dramaclaw/dramaclaw-gateway (Go, NewAPI fork,
  module `new-api`, served as the model gateway).
- Shape: FastAPI `:8780` (`uv run novelvideo api`) + React/Vite frontend + NewAPI-style
  gateway. Docker compose builds all three; CE needs NO external DB (SQLite + local state).
- Two faces sharing one asset library: **XiaHua canvas** (node workbench: upload, image
  gen/edit, storyboard, script, video, video compose, audio, style, 3D world, export; 18
  node types) and the **novel→film production line** (cognee knowledge graph → episode
  planner agents → script → keyframes/storyboard → video gen → compose/export).
  Plus **Xia Director** chat agent driving the canvas.
- Model access: ALL models (text/vision/embedding/image/video/audio) go through one
  OpenAI-compatible gateway in three modes: Official (RelayClaw key), Custom (local
  dramaclaw-gateway with provider channels: OpenRouter, VolcEngine, fal.ai, DoubaoAudio,
  ComfyUI...), Hybrid. Media model catalog = `official_media_models.json` shape:
  `{provider, upstreamModel, mediaType, config{supportedModes, ratios, resolutions,
  durations, referenceImage/Video/AudioMax, request.parameters[]}}`.
- Video path: `NewApiVideoGenerator` POSTs `{gw}/video/generations` and polls
  `{gw}/video/generations/{id}`; references go as data-URLs in `references[]`
  (image_url/video_url/audio_url types). Canvas video node already supports audio
  references (allReference mode, up to 3 by catalog).
- Audio path: speech via gateway `/audio/speech` (edge-tts default; index-tts-2 via
  fal/newapi); user voice upload exists (`user_audio_voices`); music via eleven-music.
- i18n: frontend i18next catalogs zh/en/vi, 6165 leaf keys, en complete (9 CJK leftovers);
  backend emits stable `code` + Chinese fallback (`lmsg`), en catalog covers all 34
  existing codes; ~292 raw Chinese `log(...)` sites remain; `AssetLanguage = zh|en`
  drives agent output language; ~6000 CJK literals in backend overall (prompts, comments).
- Gateway channel types relevant to us: fal(61), ali(DashScope wan), kling, hailuo
  (MiniMax-H3), DoubaoVideo, ComfyUI(63). fal task adaptor currently maps only Seedance
  video routes.

## Our stack to wire in (from MODELS.md + skills)

- Video (fal): `minimax/h3-max-turbo/image-to-video` + `/text-to-video` (CURRENT
  DEFAULT "h3 max turbo"), `minimax/h3-max/{text-to-video,image-to-video,reference-to-video}`,
  `fal-ai/kling-video/v3/{pro,standard}/...`, wan 3.0 (also via cavallo/DashScope),
  happyhorse 1.1 (via cavallo/DashScope). fal key: `~/.agent_credentials/tokens/fal.env`.
- Audio-first: voice made OUTSIDE (AuK `say`), uploaded into the canvas, attached as
  audio reference to the video node. H3 family accepts audio references.
- Soundbed: local `thinksound-native` (`~/works/repos/thinksound-native/build/ts-native`,
  weights in /tmp/ts-weights, caption+cot, seed, dur, out wav; no voice in prompts).
- Gateway for text/vision: mantice `https://llm.fornace.net/v1` (OpenRouter-ish catalog).

## Workstreams

- **A. Run it locally** (compose or uv+pnpm+go), verify UI in English end to end.
- **B. Italian + English completeness**: add `it` to SUPPORTED + labels +
  full `locales/it/translation.json`; fix 9 en CJK leftovers; sweep hardcoded
  user-facing CJK in frontend; extend `AssetLanguage` to `it`; route remaining
  raw-Chinese log/progress sites through lmsg codes (Chinese fallback stays for zh).
- **C. Model stack**: extend gateway fal task adaptor with h3-max / h3-max-turbo /
  kling-v3 routes incl. audio references; add CE media-model catalog + provider profile
  JSON (one file, easy to swap models); default video model = H3 Max Turbo.
- **D. Audio-first + local soundbed**: audio upload → video reference flow verified;
  local soundbed generator adapter (ts-native) in the audio node as a pluggable local
  provider; config-driven so future changes are one file.
- **E. Review + polish**: supervisor adversarial review of every milestone; one short
  test film produced through the product in EN (and IT) using audio-first + soundbed +
  H3 Max Turbo; commits per milestone in this clone.

## Non-goals / guardrails

- No traditional VFX anywhere (repo RULE ONE untouched; DramaFoundry only generates via
  models + deterministic cut/mux plumbing, same philosophy).
- Upstream mergeability: keep our changes as clean local commits, avoid rewriting
  upstream files wholesale where a surgical patch works.
- Keys never committed.
