#!/usr/bin/env python3
"""Translate frontend translation catalog to Italian using Fornace Flash.

Reads frontend/public/locales/en/translation.json, translates in batches,
and writes frontend/public/locales/it/translation.json matching exact structure.
"""

from __future__ import annotations

import asyncio
import json
import urllib.request
from pathlib import Path
from typing import Any

MANTICE_KEY = Path("~/.agent_credentials/tokens/mantice.env").expanduser().read_text().strip()
ENDPOINT = "https://llm.fornace.net/v1/chat/completions"
MODEL = "fornace-flash"
CONCURRENCY = 8
BATCH_SIZE = 80


def flatten_json(obj: dict, prefix: str = "") -> dict[str, str]:
    items: dict[str, str] = {}
    for k, v in obj.items():
        curr = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            items.update(flatten_json(v, curr))
        else:
            items[curr] = str(v)
    return items


def unflatten_json(flat: dict[str, Any]) -> dict[str, Any]:
    tree: dict[str, Any] = {}
    for path, val in flat.items():
        parts = path.split(".")
        d = tree
        for part in parts[:-1]:
            if part not in d or not isinstance(d[part], dict):
                d[part] = {}
            d = d[part]
        d[parts[-1]] = val
    return tree


async def translate_batch(
    client_session: asyncio.Semaphore,
    batch: dict[str, str],
    batch_idx: int,
    total_batches: int,
) -> dict[str, str]:
    async with client_session:
        prompt = (
            "You are a professional software localization translator for Italian. "
            "Translate the following JSON string values from English to natural, idiomatic Italian UI copy. "
            "Keep technical placeholders like {{count}}, {{name}}, {0}, {1}, HTML tags like <b></b> exactly intact. "
            "Never change or translate brand names like DramaClaw, SuperTale, XiaHua, MiniMax, Wan, Kling, fal.ai. "
            "Return ONLY a strictly valid JSON object with the exact same keys.\n\n"
            + json.dumps(batch, ensure_ascii=False)
        )

        payload = {
            "model": MODEL,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }

        loop = asyncio.get_running_loop()
        for attempt in range(3):
            try:
                def do_request():
                    req = urllib.request.Request(
                        ENDPOINT,
                        data=json.dumps(payload).encode("utf-8"),
                        headers={
                            "Authorization": f"Bearer {MANTICE_KEY}",
                            "Content-Type": "application/json",
                        },
                    )
                    with urllib.request.urlopen(req, timeout=60) as resp:
                        return json.loads(resp.read().decode("utf-8"))

                res = await loop.run_in_executor(None, do_request)
                content = res["choices"][0]["message"]["content"]
                translated = json.loads(content)
                # Verify keys
                result = {}
                for k, orig in batch.items():
                    result[k] = translated.get(k, orig)
                print(f"Batch {batch_idx+1}/{total_batches} translated successfully.")
                return result
            except Exception as e:
                print(f"Batch {batch_idx+1} error (attempt {attempt+1}): {e}")
                await asyncio.sleep(2)

        print(f"Batch {batch_idx+1} fallback to original English after retries.")
        return batch


async def main():
    en_path = Path("frontend/public/locales/en/translation.json")
    it_path = Path("frontend/public/locales/it/translation.json")
    it_path.parent.mkdir(parents=True, exist_ok=True)

    with open(en_path, "r", encoding="utf-8") as f:
        en_tree = json.load(f)

    flat_en = flatten_json(en_tree)
    items = list(flat_en.items())
    print(f"Total keys to translate: {len(items)}")

    batches = []
    for i in range(0, len(items), BATCH_SIZE):
        batches.append(dict(items[i : i + BATCH_SIZE]))

    sem = asyncio.Semaphore(CONCURRENCY)
    tasks = [
        translate_batch(sem, b, idx, len(batches))
        for idx, b in enumerate(batches)
    ]
    results = await asyncio.gather(*tasks)

    flat_it = {}
    for r in results:
        flat_it.update(r)

    # Specific overrides
    flat_it["header.account.languageChinese"] = "Cinese"
    flat_it["header.account.languageEnglish"] = "Inglese"
    flat_it["header.account.languageVietnamese"] = "Vietnamita"
    flat_it["header.account.languageItalian"] = "Italiano"

    it_tree = unflatten_json(flat_it)
    with open(it_path, "w", encoding="utf-8") as f:
        json.dump(it_tree, f, ensure_ascii=False, indent=2)

    print(f"Done! Italian catalog saved to {it_path} with {len(flat_it)} keys.")


if __name__ == "__main__":
    asyncio.run(main())
