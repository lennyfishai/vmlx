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
