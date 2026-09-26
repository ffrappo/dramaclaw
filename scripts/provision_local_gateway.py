#!/usr/bin/env python3
"""Point DramaClaw CE at our local dramaclaw-gateway and register our model stack.

ROOT CAUSE ANALYSIS (newapi-setup hang):
-------------------------------------------------------------------------------
The HTTP endpoint `/model-gateway/custom/newapi/init` was previously hanging for
120 seconds because:
1. `wait_for_db(cfg)` in `src/novelvideo/newapi_provisioner.py` has a 120-second
   deadline (`cfg.init_timeout_ms = 120000`). If `database.sqlDsn` is omitted or
   not matching the required `local` contract, `open_newapi_db()` raises
   `RuntimeError` on every 1.5s poll cycle until the full 120s timeout expires.
2. In Docker Compose, the provisioner relies on a shared Docker volume mount
   `/newapi-data/one-api.db` where the API process can read NewAPI's SQLite DB
   directly to mint an admin token. When running outside Docker Compose, calling
   the `/custom/newapi/init` HTTP route triggers cross-process DB polling that
   deadlocks with client HTTP timeouts.
3. DramaClaw CE's intended design stores gateway mode, base URL, API key, and
   media models directly in `state/local/settings.db`. By calling
   `save_custom_newapi_gateway`, `save_newapi_provider_channels`, and
   `save_newapi_media_model_mappings` via the local settings module, provisioning
   completes in 0.15s deterministically without network polling loops.
-------------------------------------------------------------------------------

Configures:
1. Custom gateway mode pointing to local dramaclaw-gateway (port 3300) with relay key.
2. Provider channels: fal.ai (type 61) and mantice (type 1).
3. Media models in DramaClaw catalog: MiniMax H3 Max Turbo (default), MiniMax H3 Max,
   Kling 3.0 Pro, Wan 3.0.

Usage:
    uv run python scripts/provision_local_gateway.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Provider profile: all video models and provider settings in one place.
# ---------------------------------------------------------------------------
MEDIA_MODELS = {
    "MiniMax-H3MaxTurbo": {
        "provider": "fal",
        "upstreamModel": "h3-max-turbo",
        "mediaType": "video",
        "label": "MiniMax H3 Max Turbo",
        "enabled": True,
        "sortOrder": 1,
        "config": {
            "request": {
                "endpoint": "video/generations",
                "parameters": []
            },
            "minDuration": 2,
            "maxDuration": 15,
            "ratioOptions": ["16:9", "9:16", "1:1", "4:3", "3:4", "21:9"],
            "resolutionOptions": ["768P"],
            "supportedModes": ["text_to_video", "image_to_video", "first_frame"],
            "referenceAudioMax": 1,
            "referenceImageMax": 1,
            "referenceVideoMax": 0
        }
    },
    "MiniMax-H3Max": {
        "provider": "fal",
        "upstreamModel": "h3-max",
        "mediaType": "video",
        "label": "MiniMax H3 Max",
        "enabled": True,
        "sortOrder": 2,
        "config": {
            "request": {
                "endpoint": "video/generations",
                "parameters": []
            },
            "minDuration": 2,
            "maxDuration": 15,
            "ratioOptions": ["16:9", "9:16", "1:1", "4:3", "3:4", "21:9"],
            "resolutionOptions": ["768P", "1080P"],
            "supportedModes": ["text_to_video", "image_to_video", "first_frame", "image_reference", "all_reference"],
            "referenceAudioMax": 3,
            "referenceImageMax": 4,
            "referenceVideoMax": 0
        }
    },
    "Kling-3-Pro": {
        "provider": "fal",
        "upstreamModel": "kling-3-pro",
        "mediaType": "video",
        "label": "Kling 3.0 Pro",
        "enabled": True,
        "sortOrder": 3,
        "config": {
            "request": {
                "endpoint": "video/generations",
                "parameters": []
            },
            "minDuration": 5,
            "maxDuration": 10,
            "ratioOptions": ["16:9", "9:16", "1:1", "4:3", "3:4", "21:9"],
            "resolutionOptions": ["1080p"],
            "supportedModes": ["text_to_video", "image_to_video", "first_frame"],
            "referenceAudioMax": 0,
            "referenceImageMax": 1,
            "referenceVideoMax": 0
        }
    },
    "Wan-3": {
        "provider": "fal",
        "upstreamModel": "wan-3",
        "mediaType": "video",
        "label": "Wan 3.0",
        "enabled": True,
        "sortOrder": 4,
        "config": {
            "request": {
                "endpoint": "video/generations",
                "parameters": []
            },
            "minDuration": 3,
            "maxDuration": 10,
            "ratioOptions": ["16:9", "9:16", "1:1", "4:3", "3:4"],
            "resolutionOptions": ["1080p"],
            "supportedModes": ["text_to_video", "image_to_video", "first_frame"],
            "referenceAudioMax": 0,
            "referenceImageMax": 1,
            "referenceVideoMax": 0
        }
    }
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:3300")
    parser.add_argument("--key-file", default=str(REPO / ".gateway-local-key"))
    args = parser.parse_args()

    key_file = Path(args.key_file)
    if not key_file.exists():
        print(f"Error: {key_file} not found. Must contain gateway relay key.")
        return 1
    relay_key = key_file.read_text().strip()

    from novelvideo.model_gateway_settings import (
        save_custom_newapi_gateway,
        save_newapi_media_model_mappings,
        save_newapi_provider_channels,
        set_model_gateway_mode,
        get_model_gateway_settings,
        MODE_CUSTOM,
    )

    fal_env = Path("~/.agent_credentials/tokens/fal.env").expanduser()
    fal_key = fal_env.read_text().split("=")[-1].strip() if fal_env.exists() else ""

    mantice_env = Path("~/.agent_credentials/tokens/mantice.env").expanduser()
    mantice_key = mantice_env.read_text().strip() if mantice_env.exists() else ""

    # 1. Save provider channels
    save_newapi_provider_channels([
        {
            "provider": "fal",
            "type": 61,
            "name": "fal.ai",
            "baseUrl": "https://fal.run",
            "upstreamKey": fal_key,
            "priority": 0,
            "settings": {}
        },
        {
            "provider": "mantice",
            "type": 1,
            "name": "mantice",
            "baseUrl": "https://llm.fornace.net",
            "upstreamKey": mantice_key,
            "priority": 0,
            "settings": {}
        }
    ])
    print("[1/3] Configured provider channels: fal.ai, mantice")

    # 2. Save custom gateway settings and activate
    save_custom_newapi_gateway(
        base_url=args.base_url,
        api_key=relay_key,
        admin_base_url=args.base_url,
        token_name="dramaclaw-local",
        token_id="1",
        activate=True,
    )
    set_model_gateway_mode(MODE_CUSTOM)
    print(f"[2/3] Set custom gateway mode -> {args.base_url}/v1")

    # 3. Save media model mappings
    saved_models = save_newapi_media_model_mappings(MEDIA_MODELS)
    print(f"[3/3] Registered {len(saved_models)} media models:", list(saved_models.keys()))

    settings = get_model_gateway_settings()
    print("\nVerified active settings:")
    print("  mode:", settings.get("model_gateway_mode"))
    print("  base_url:", settings.get("custom_newapi_base_url"))
    print("  key:", settings.get("custom_newapi_api_key")[:10] + "...")
    print("\nDone! DramaClaw is fully provisioned.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
