# Storytelling Channels Playbook (DramaFoundry × Fornace Stack)

A production-proven guide for authoring character-led visual stories, short dramas,
and vertical video channels with DramaFoundry and our generative model stack.

---

## 1. Core Operating Philosophy

1. **Audio First, Always:** Spoken performance establishes pacing, emotional cadence,
   and scene duration. The video model follows the voice, not vice-versa.
2. **Generative Only (No Traditional VFX):** Every altered or generated pixel comes
   from an approved generative model (Wan 2.7 / FLUX 3 for repairs; MiniMax H3 Max Turbo,
   H3 Max, Kling 3.0 Pro, Wan 3.0 for generation).
3. **Pluggable & Zero-Cost Infrastructure:**
   - Text & Vision: Mantice (`llm.fornace.net`) via OpenAI-compatible channel.
   - Video: Fal.ai hosted queue (MiniMax H3 Max Turbo default; Kling/Wan available).
   - Ambience / Foley: Local ThinkSound Native on Apple Silicon Metal 4 (zero API cost).
   - Voice: AuK local voice-cloning or uploaded studio tracks.

---

## 2. The 6-Node Scene Template (XiaHua Canvas)

On the XiaHua canvas (`/projects/<project>/freezone`), each narrative beat is laid out
using 6 connected nodes:

```
[1. Script / Beat] ─────────► [2. Voice Audio] ──(audio ref)──┐
       │                                                      │
       ▼                                                      ▼
[3. Identity Frame] ──(first frame)──────────────────────► [5. Video Gen] ──► [6. Compose]
                                                                                ▲
[4. ThinkSound Bed] ──(ambient layer)───────────────────────────────────────────┘
```

### Node Details:
* **Node 1 (Script / Beat Context):** Defines character entry emotional state,
  dialogue line, and scene action.
* **Node 2 (Voice AudioNode):** Studio voiceover or AuK-cloned narration track.
  Connected as an audio reference edge to Node 5.
* **Node 3 (Image / Character Reference):** Consistent front/three-quarter portrait.
  Connected as the `first_frame` input to Node 5.
* **Node 4 (Soundbed AudioNode):** Local environmental audio generated via `thinksound-native`
  (e.g., `"rain against window pane, quiet room tone, distant thunder"`).
* **Node 5 (VideoNode — MiniMax-H3MaxTurbo):**
  - Prompt: Describes camera movement and physical action.
  - Receives `first_frame` from Node 3 and `target_audio_url` from Node 2.
  - Renders synchronized video matching the exact audio duration.
* **Node 6 (VideoComposeNode):** Muxes the video with the primary voice track and
  the ambient soundbed mixed under dialogue (target -33 LUFS).

---

## 3. Supported Model Roster & Switching

All models are managed via `scripts/provision_local_gateway.py` or the Settings panel:

| Model ID | Provider | Modes | Best Used For |
|---|---|---|---|
| `MiniMax-H3MaxTurbo` | Fal | Text, I2V (with Audio Pin) | **Default:** Ultra-fast, lip-synced character performance |
| `MiniMax-H3Max` | Fal | Text, I2V, Multi-Ref (4 img, 3 audio) | Complex scenes needing multiple character/prop references |
| `Kling-3-Pro` | Fal | Text, I2V (1080p) | Cinematic B-roll, complex physics, action choreography |
| `Wan-3` | Fal | Text, I2V (1080p + Audio toggle) | Atmospheric wide shots, stylized visual drama |
| `thinksound-native` | Local | Text to Ambient Sound (WAV/MP3) | Zero-cost local background audio on Apple Silicon Metal 4 |

To change default models or add credentials:
```bash
uv run python scripts/provision_local_gateway.py
```

---

## 4. Multi-Language Storytelling (English & Italian)

DramaFoundry CE now natively supports multilingual channels:

* **Interface:** Choose `English` or `Italiano` from the account menu.
* **Prose Detection:** Italian scripts automatically trigger Italian model prompts
  (`"Write every user-visible prose field in Italian. Keep character names verbatim."`).
* **Audio Voiceover:** Pair Italian script nodes with Italian voice references.
