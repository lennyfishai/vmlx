# vMLX Python Engine — WIP Handoff / Status / TODO (PLACEHOLDER)

**Paused 2026-06-13** by directive (pivoting to the MiniMax M3 prefix-cache task in `~/jang`).
This PR captures all in-flight work on the vMLX Python engine + harness + docs so it can be
resumed cleanly later. Base: `main @ a4cde7862` (v1.5.58).

See also: `docs/LIVE-APP-TESTING-PROTOCOL.md` (mandatory live-app test protocol + cache policy)
and `docs/LIVE-APP-TESTING-STATUS.md` (full findings + cross-check matrix + harness usage).

---

## ✅ Done
- **Mandatory live-app testing protocol + SSD/paged cache policy** written down
  (`docs/LIVE-APP-TESTING-PROTOCOL.md`).
- **Reusable live-app automation harness** (`panel/scripts/uidrv.cjs` + dev-only env-gated CDP
  switch in `panel/src/main/index.ts`; `playwright-core` devDep). Drives the real dev-build app
  over CDP without touching `/Applications/vMLX.app`.
- **Gemma 4 E2B QAT MXFP4 — validated live (everything except VL):** load + autodetect
  (gemma4 / VL / SWA RotatingKVCache), coherent multiturn, prefix cache HIT, reasoning On = clean
  (no leaks), multiturn tool-calling (engine emits clean `tool_calls`), streaming clean.

## 🔴 Open — P0 (NOT fixed)
- **VL image input completely broken:** every image request →
  `RuntimeError: There is no Stream(gpu, 0) in current thread`. Confirmed on a fresh engine
  (not a sleep/wake artifact). Root cause: Gemma4 media turns run through
  `BatchedEngine._simple_mllm_chat_output` (`engine/batched.py`) on a ThreadPoolExecutor worker
  with no default GPU stream; mlx_vlm `wired_limit`'s bare `mx.synchronize()` + the vision encoder
  fail there.
  - **Two fix attempts in this PR are INSUFFICIENT** (kept, clearly labeled, harmless to text):
    `models/mllm.py` wraps `generate()` in `_MaybeVLMStream()`; `engine/batched.py` sets the
    worker thread default stream. Neither resolves it.
  - **Recommended real fix (TODO):** route Gemma4 media turns through the working batched VLM
    scheduler (other VL families work that way), OR run the simple media `chat()` on the model's
    loader/main thread, OR fix upstream mlx_vlm thread/stream handling.

## ⏳ TODO (not started)
- **Headline cache-policy change — paged OFF / SSD prefix default for ALL families.** Fully mapped,
  not implemented (release-engine-wide, correctness-critical). Touch points:
  - panel `src/shared/cacheControlPolicy.ts` `resolveCacheLaunchPolicy`, and `src/main/sessions.ts`
    `cacheTypeRequiresPaged` (hybrid/mamba/rotating_kv) + `cacheSubtypeRequiresPaged`
    (step3p7_full_sliding_kv / mixed_swa_kv / mimo_v2_asymmetric_swa) + `buildArgs` (stops adding
    `--use-paged-cache`, adds SSD/disk prefix flags).
  - engine `cli.py` `_apply_zaya_cca_cache_policy` (forces paged) + `_apply_dsv4_cache_policy`
    (paged-first) → rewrite "prefix→paged" to "prefix→SSD".
  - `block_disk_store.py` already has typed lanes (`zaya_cca`, `dsv4_composite`, `rotating_kv` +
    TQ-quant) but they are **paged-block-coupled** — must be decoupled to back a standalone SSD
    prefix tier (or port lanes into `disk_cache.py`). **Do not flip ZAYA/DSV4/hybrid to paged-off
    before their SSD record persists full resume state — else silent wrong outputs.**
- VL **audio** test; reasoning **Off** spot-check.
- Matrix: **E4B / 12B / 26B-A4B / 31B** × **JANG_4M / MXFP4 / MXFP8 / QAT**.
- TurboQuant RQ-KV is **skipped** for native MXFP4 Gemma (uses q4 affine) — confirm intended.

## Notes / gotchas (harness)
- Don't fire `sessions.*` IPC while the renderer drives the same flow (deadlocks the session lock).
- To send a chat: model awake (Server→Wake if standby) + ChatSettings drawer closed.
- Built-in coding tools require a `workingDirectory` (native picker; set via `chat.setOverrides` IPC).
- UX bugs found: idle deep-sleep disables Send; open ChatSettings drawer blocks Send; tools checkbox
  needs a real click to persist.
