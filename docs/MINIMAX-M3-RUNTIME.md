# MiniMax-M3 vMLX Python Runtime + MSA Dual-Cache

Serves `JANGQ-AI/MiniMax-M3-REAP22-JANG_2L` (104.5 GB, `model_type=minimax_m3_vl`, 60 layers /
100 experts/layer, JANG_2L affine). MLX 1:1 port of the validated torch reference
(`~/jang/jang-tools/jang_tools/minimax_m3/layer_forward.py`). Full design/plan:
`~/jang/research/m3-runtime-scaffold/MINIMAX-M3-RUNTIME-PLAN.md`.

## Status (2026-06-13) — text runtime + 4-tier cache COMPLETE & AUDITED

Module: `vmlx_engine/models/minimax_m3/` (minimax_m3.py, cache.py, runtime.py,
minimax_m3_register.py + tests). MSA **dual cache**: dense layers 0-2 -> `("kv", k, v)`;
sparse layers 3-59 -> **`("minimax_m3", k, v, idx_keys)`** (append-only, block-anchored to
`pos // 128`, never shift/rotate/evict). Wired through ALL tiers:
- `prefix_cache.py` — L1 block-aware (serialize + reconstruct `restore_minimax_m3_sparse`)
- `block_disk_store.py` — L2 SSD (serialize/deserialize incl. `layer_{i}_idx_keys`)
- `cache_record_validator.py` — tag whitelist (the silent-reject culprit, now fixed)
- `memory_cache.py` — counts idx_keys bytes (was under-reporting ~11%)

**Audit (re-run 2026-06-13 on the real 97 GB model — all PASS):**
- `test_tier_micro.py` — tag wiring correct across tiers (dense `kv` / sparse `minimax_m3`).
- `test_other_models_regression.py` — kv/quantized_kv/rotating_kv/cumulative intact; unknown rejected.
- `test_cache_roundtrip.py <bundle>` — restore preserves decode: identical tokens, `max|logitA-logitB| = 0`.
- `test_prefix_cache_e2e.py <bundle>` — L1 split+reconstruct exact MSA decode + L2 SSD k/v/idx exact (maxdiff 0).
- Live decode ~9.8 tok/s through the MSA dual cache; coherent `<mm:think>` reasoning.

Run a test:
`.venv/bin/python vmlx_engine/models/minimax_m3/test_cache_roundtrip.py ~/.mlxstudio/models/JANGQ-AI/MiniMax-M3-REAP22-JANG_2L`

## REMAINING (for the team)

1. **VL wrapper** — `minimax_m3_vl.py` (CLIP tower + projector + patch_merge) not yet built; the
   model is `minimax_m3_vl`, so image input needs it. Then test with a real image.
2. **Live in-app verification** — load M3 in the real dev-build vMLX app and chat live (multiturn,
   reasoning on/off/auto, prefix-cache HIT, tool-calls, no leaks) per `docs/LIVE-APP-TESTING-PROTOCOL.md`.
   Only scripts/CLI proven so far.
3. **Release integration** — register / gen-config / capability-detection wiring into the engine
   serve path; long-ctx MSA top-16 block selection is implemented but not yet long-ctx stress-tested.

## Status Update (2026-06-17) — packaged app proof is PARTIAL

Current live target tested: `/Applications/vMLX.app` with bundled Python
`vmlx_engine 1.5.62`, loading
`~/.mlxstudio/models/JANGQ-AI/MiniMax-M3-REAP40-d3-JANG_2L` through the Electron UI
and `/v1/responses`.

Source/runtime fixes landed in this lane:
- M3 autodetect keeps paged cache off, JIT off, generic TurboQuant KV disabled,
  native MSA cache active (`MiniMaxM3SparseCache` on sparse layers 3-59), memory-aware
  prefix cache enabled, and SSD prompt cache enabled.
- M3 reasoning parser handles both `<mm:think>` and fallback `<think>` tags, and
  classifies prompt-opened no-tag deltas as reasoning.
- M3 thinking-off no longer receives the legacy MiniMax/M2 plain `<think>` sentinel;
  it keeps the native M3 `</mm:think>` sentinel only.
- Responses streaming has a MiniMax-M3 visible-answer pass for the case where forced
  reasoning consumes the first generation budget and yields no visible content.
- Packaging guard fixed: `build-and-install.sh` now runs bundled-source parity checks,
  `verify-bundled-python.sh` hash-gates the M3/cache/runtime files, and
  `bundle-python.sh` removes stale setuptools `build/` artifacts before building the
  local `vmlx` wheel. This was necessary because stale `output_collector.py` with
  `error_message=new.error_message` shipped despite correct source.

Source checks run:
- `pytest tests/test_minimax_m3_cache_paths.py tests/test_streaming_reasoning.py tests/test_thinking_template_render.py -k 'minimax_m3 or test_minimax_m3' -q`
  -> `16 passed, 154 deselected`.
- `scripts/verify-bundled-python.sh` -> bundled source parity and critical imports OK.
- `/Applications/vMLX.app` code signature -> valid on disk, satisfies Designated Requirement.

Live app evidence from the rebuilt app:
- Startup CLI included `--tool-call-parser minimax_m3`, `--reasoning-parser minimax_m3`,
  `--cache-memory-percent 0.15`, `--enable-disk-cache`, `--disk-cache-max-gb 10`,
  `--continuous-batching`; no `--enable-jit` and no paged-cache flag.
- Logs: `MiniMax-M3 AUTODETECTED ... paged_cache=OFF, tq_kv=SKIP(native MSA),
  vl_route=ON, tool_parser=minimax_m3, reasoning_parser=minimax_m3, jit=off,
  msa_per_step_sync=ON`.
- Logs: `Runtime cache layout` = layers 0-2 `KVCache`, layers 3-59
  `MiniMaxM3SparseCache`.
- Logs: `MemoryAwarePrefixCache initialized` and `Disk cache initialized`.
- 10-turn Thinking Off UI run: no blank turn, no visible think tags, no reasoning leak,
  no repetition loop. The formerly blank "profile options" turn returned visible content.
- Long-context UI run: first prompt 8050 tokens; follow-up cache hits at 8045 and
  8092 cached tokens; no blank output, no repeat loop, no engine error.

Open / partial:
- Reasoning On is still not a full semantic pass. The current app separates the
  reasoning rail when the model emits one and no longer crashes/blanks, but one live
  forced-thinking factual prompt returned visible content with `reasoningChars=0`
  (the model appears to close the think rail immediately). Another live run emitted
  reasoning but miscomputed `17 + 28` as `41`. Treat Reasoning On as PARTIAL until a
  deterministic forced-reasoning behavior is proven or the UI contract is clarified.
- Long-context cache reuse is structurally healthy in the tested run, but exact recall
  was imperfect: the model remembered `DELTA-742` and both runbook rules, but missed
  one exact required phrase. Do not call long-context QA quality fully passing.
- This is a local ad-hoc signed app install, not a notarized release artifact.
