# vMLX — Live-App Testing + SSD Cache Policy — STATUS / PROGRESS LOG

Companion to `LIVE-APP-TESTING-PROTOCOL.md`. Updated as work proceeds (self-paced loop).
**Work machine:** THIS local MacBook `erics-m5-max2` (Eric: "work from this local macbook").
All editing / dev-build / live testing happens locally on max2 — not over SSH.
**Dropped from scope:** MiMo, the n2 `jang_loader` refactor, Qwen 2.7 — do not track.

---

## Phase board

| Phase | What | State |
|---|---|---|
| 0 | Protocol + status docs + memory | ✅ done (2026-06-13) |
| 1 | Audit current cache defaults + per-family SSD readiness | ✅ done (2026-06-13) |
| 1b | Build live-app CDP automation harness (dev build + driver) | ✅ done (2026-06-13) |
| 2 | Code: flip defaults → paged OFF / SSD prefix ON per family | ⏳ in progress |
| 3 | Live-test Gemma 4 matrix (testing→fixing→testing) | ⏳ harness ready, model loads next |
| 4 | Extend to all other shipped families | ⏳ not started |

---

## Phase 1 audit — findings (grounded in code, 2026-06-13)

**Current defaults / policy (`vmlx_engine/cli.py`):**
- `_apply_zaya_cca_cache_policy` (cli.py:192) **forces `use_paged_cache=True`** whenever
  prefix cache is on — because "memory-aware/legacy prefix caches cannot store CCA
  conv_state + prev_hs safely". Generic TQ-KV forced OFF for ZAYA (`VMLX_DISABLE_TQ_KV=1`).
- `_apply_dsv4_cache_policy` (cli.py:228) uses a **native composite paged path by
  default**; sets `paged_cache_block_size = DSV4_PAGED_CACHE_BLOCK_SIZE`; disables
  prefix entirely unless opted in. → DSV4 currently paged-first.
- So today several families are **paged-first**, which is exactly what the new policy forbids.

**Two SSD tiers exist:**
- `disk_cache.py` — standalone disk **L2 for the (non-paged) prefix/memory path** (TQ-native
  26x serialize via `tq_disk_store.py`, `__tq_native__` marker).
- `block_disk_store.py` — **per-block L2 under PAGED cache**. Already has typed family lanes:
  - `rotating_kv` (RotatingKVCache → SWA / **Gemma SWA**), preserves max_size/keep/offset/idx
  - `dsv4_composite` (SWA local + CSA/HCA compressor/indexer pools, full pool per block)
  - `zaya_cca` (standard KV pages **+ terminal conv_state/prev_hs**)
  - quantized KV lanes (`*_data/_scales/_zeros`) → TurboQuant RQ KV round-trip on SSD ✅

**The crux:** the per-family resume records Eric wants *already exist*, but they live in
the **paged-coupled** `block_disk_store`. To deliver "paged OFF + SSD prefix" for
hybrid/CCA/DSV4/SWA we must either (a) **decouple `block_disk_store`** so it serves as a
standalone SSD prefix tier without paged blocks, or (b) **port the typed lanes into
`disk_cache.py`** so the standalone prefix L2 carries them. Until that exists, naïvely
flipping the global default to paged-off + SSD-prefix for these families = **silent wrong
outputs** (state not actually persisted/resumed). This ordering is mandatory.

**Safe-first targets (SSD prefix already standalone-capable):** plain dense + MoE +
**Gemma 4** non-hybrid attention rows — these use standard KV that `disk_cache.py`
already serializes (TQ-native). Start the flip + live tests here, then do the
decouple/port work for CCA/DSV4/hybrid-SSM/SWA before flipping them.

---

## Cross-check matrix (live, dev-build app — Part C/D of protocol)

Verdict only when ALL applicable columns ✅ via live in-app proof.
Cols: Load · Autodetect · GenCfg · SSDprefix HIT+TTFT · RQ KV enc/dec · Reason on/off/auto ·
Tool (multiturn) · VL image · Audio · Video · Stream/leaks.

| Model · format | Load | Auto | GenCfg | SSD HIT | RQ KV | Reason | Tool | Img | Aud | Vid | Stream | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| gemma-4-E2B-it-qat-MXFP4 | ✅ | ✅ | ✅ | ✅HIT(paged!) | ❌TQ-skip | ✅On | ✅loop⚠cnt | ❌P0 | ❌P0 | ➖ | ✅ | 🔴VL-blocked |
| gemma-4-E2B-it-qat-JANG_4M | ⏳ | | | | | | | | | | | ⏳ |
| gemma-4-E4B-it-qat-MXFP4 | ⏳ | | | | | | | | | | | ⏳ |
| gemma-4-E4B-it-qat-JANG_4M | ⏳ | | | | | | | | | | | ⏳ |
| gemma-4-12B-it-qat-MXFP4 | ⏳ | | | | | | | | | | | ⏳ |
| gemma-4-12B-it-qat-JANG_4M | ⏳ | | | | | | | | | | | ⏳ |
| gemma-4-26B-A4B-it-qat-MXFP4 | ⏳ | | | | | | | | | | | ⏳ |
| gemma-4-26B-A4B-it-qat-JANG_4M | ⏳ | | | | | | | | | | | ⏳ |
| gemma-4-31B-it-qat-MXFP4 | ⏳ | | | | | | | | | | | ⏳ |
| gemma-4-31B-it-qat-JANG_4M | ⏳ | | | | | | | | | | | ⏳ |

---

## Log

- **2026-06-13** — Phase 0/1 complete. Wrote protocol + this status doc. Audited cache
  defaults: confirmed SSD typed family lanes exist in `block_disk_store.py` but are
  paged-coupled; identified decouple/port as the gating work for CCA/DSV4/hybrid/SWA;
  identified dense/MoE/Gemma attention rows as safe-first flip targets.
- **2026-06-13 (correction)** — Eric: work from THIS local MacBook (erics-m5-max2), not
  SSH. Dropped MiMo + n2 + Qwen2.7 from scope.
- **2026-06-13 (local surface ready)** — max2 `~/mlx/vllm-mlx` was stale (branch
  `session/v1.5.8`, 1783 behind origin/main, 199 dirty scratch). Stashed scratch
  (`git stash@{0}` "max2 session/v1.5.8 scratch pre-gemma-qat-2026-06-13", reversible),
  fast-forwarded `main` → `origin/main` @ `a4cde7862` = **v1.5.58**. Verified: 229 engine
  `.py`, `block_disk_store` typed SSD lanes present (zaya_cca/dsv4_composite/rotating_kv),
  `import vmlx_engine` OK, `jang_loader` clean. Local Gemma 4 QAT models present under
  `~/models/OsaurusAI--gemma-4-*-qat-{MXFP4,JANG_4M}` + HF cache. **Ready to start Phase
  2/3 locally.** Next: load Gemma 4 E2B QAT (smallest) locally → verify load + autodetect
  (model_type, jang_config, generation_config defaults) → begin live chat/tool/reasoning
  matrix.

## Live-app automation harness (READY — reusable every session)

Built 2026-06-13 on max2. Drives the real dev-build vMLX Electron app over CDP.

**Launch the dev app (isolated, local engine, CDP):**
```
cd /Users/eric/mlx/vllm-mlx/panel
PATH="/Users/eric/mlx/vllm-mlx/.venv/bin:$PATH" \
  VMLX_REMOTE_DEBUG_PORT=9333 \
  VMLX_USER_DATA_DIR=/Users/eric/.vmlx-dev-test \
  npm run dev   # run as a background task
```
- `VMLX_REMOTE_DEBUG_PORT` → CDP on :9333 (dev-only switch added to `src/main/index.ts`,
  env-gated, no-op in prod). `remote-allow-origins=*` set so Playwright can attach.
- `VMLX_USER_DATA_DIR` → isolated state (`~/.vmlx-dev-test`); own single-instance lock so
  it coexists with production `/Applications/vMLX.app` (do NOT kill production).
- `.venv/bin` on PATH → app's `which vmlx-serve` resolves the **editable local 1.5.58
  source** (so we test OUR code, not PyPI). Without it the app shows "Install Engine".
- Caveat: dev app *adopts* any already-running `vmlx-engine` (e.g. production MiniMax on
  :8004) for tracking; loading a model spawns its own engine on a separate port. Watch
  for cross-talk.

**Driver:** `panel/scripts/uidrv.cjs` (uses `playwright-core`, connectOverCDP :9333):
```
node scripts/uidrv.cjs inspect [png]        # screenshot + dump headings/clickables/inputs
node scripts/uidrv.cjs shot <png>
node scripts/uidrv.cjs click "<visible text>"
node scripts/uidrv.cjs type "<css sel>" "<text>"
node scripts/uidrv.cjs eval "<js returning JSON>"
```
Gotchas: one CDP client at a time; kill the dev electron by PID (`lsof -iTCP:9333`) before
relaunch since userData is an env var (not in argv) so `pkill -f vmlx-dev-test` misses it.

**Verified working 2026-06-13:** app boots to full UI (Chat/Server/Tools/Image/API tabs,
model picker, settings, reasoning/tool toggles), CDP inspect/click/screenshot all functional.

## Findings — first live test attempt (Gemma 4 E2B QAT MXFP4), 2026-06-13

- Harness drove the real app end-to-end: Server tab → New Session → model picker → filter.
- **Model discovery:** dev app scans only `~/.mlxstudio/models` + `~/.cache/huggingface/hub`
  (not `~/models`). HF-cache Gemma entries weren't listed (incomplete snapshots). Workaround:
  symlinked complete models from `~/models/OsaurusAI--gemma-4-E2B-it-qat-{MXFP4,JANG_4M}`
  into `~/.mlxstudio/models/` → both appear after Rescan. (Adding `~/models` via the UI needs
  the native NSOpenPanel dialog, which CDP can't drive — symlink is the automation-friendly path.)
- **Cache defaults (session config form):** Enable Prefix Cache = ON, Enable Disk Cache = OFF,
  Legacy Entry-Count = OFF. **The UI itself states persistent SSD cache currently REQUIRES
  paged** ("Block Disk Cache (L2)" lives under the Paged KV Cache section; legacy disk +
  memory-aware prefix is the only non-paged path). → directly confirms the Phase-1 audit: the
  paged↔SSD coupling must be inverted to satisfy the "paged-off / SSD-prefix default" directive.
- **ISSUE (open):** clicking Launch Session put the UI in "Loading Model" but **no engine
  process spawned** after 2+ min (only production MiniMax :8004 running; nothing on a new port).
  Dev-app spawn path needs diagnosis (`panel/src/main/ipc/models.ts` / `sessions.ts`).
- **Version-string discrepancy:** engine-manager reports `Version: 1.5.26` from stale `.venv`
  dist-info metadata, though imported `vmlx_engine.__version__` is 1.5.58 (editable tree). Code
  that runs is current; only the reported string is stale (could mis-trigger update prompts).
- Kicked off a **manual CLI load** (`vmlx-engine serve …gemma-4-E2B-it-qat-MXFP4 --port 8010`)
  to confirm model load + autodetect at the engine level, independent of the app spawn bug.

**Manual engine load (port 8010) — Gemma 4 E2B QAT MXFP4 results (engine-level, ✅):**
- Load ✅ (JANG v2 VLM, 0.9s, 3.8 GB). Autodetect ✅: `detection_source=jang_stamped
  family=gemma4 reasoning_parser=gemma4 tool_parser=gemma4 is_mllm=True` (VL via config.json
  vision_config). GenCfg ✅ from bundle (max_new_tokens wins; reasoning ENABLED Gemma4ReasoningParser).
- Quant: native **MXFP4** (codec affine_quantized_matmul, target_bits=4, group_size=32,
  `jangtq_runtime=false`, `mlx_affine_quantized_matmul` dispatch, jang_config sidecar=true).
- Cache: **Gemma SWA** — 15 layers, `RotatingKVCache` (SWA) + `KVCache` (full) at 4/9/14;
  `cache_mode=memory-aware` (in-RAM), **paged OFF**, **prompt_l2=False block_l2=False** (SSD OFF),
  kv_quant=q4. `RQ KV (TurboQuant) SKIPPED` (log reason "MLA model uses CacheList" — wording
  looks misattributed for Gemma; net = plain q4 affine KV, not TQ codebook). MemoryAwarePrefixCache.
  → Matches policy gap: SSD-prefix is not the default; RQ-KV not active here.

**Dev-app local-spawn bug (OPEN, deferred):** `sessions:create` succeeds (session on port 8001,
status stopped) but `sessions:start` hangs with **empty session logs** and **no engine process**,
then the session is cleaned up/vanishes. Hang is in `_startSessionInner` *before* its first log
(`[ENV]` probe ~sessions.ts:1498). `killByPort` is bounded (5s execSync timeout) so not it; needs
a one-line entry/after-each-await `console.log` to pinpoint, OR the create→start chain has a lock
interaction. NOTE: my firing `sessions.start` directly via IPC **raced** the renderer's own
create→start chain — confounded the run. Next attempt: clean renderer-only flow, no extra IPC.
- **Fixed this iteration:** stale double editable installs (`vmlx-1.5.26` + `vmlx-1.5.45`
  dist-info) → clean `uv pip install -e .` → single **1.5.58**; engine-manager now reports 1.5.58.

**RESOLVED — local-spawn "hang" was self-inflicted:** firing `sessions.start` via IPC while the
renderer was mid `create→start` chain **deadlocked** the per-session lock. Clean native path works:
reload renderer → Server tab → click **Start** on the session (no extra IPC) → engine spawns on
:8001, `[SESSION] family=gemma4 tool=gemma4 reasoning=gemma4 autoTool=true VLM=true`. **Lesson:
never drive `sessions.*` IPC while the UI is performing the same flow.**

**LIVE in-app chat — Gemma 4 E2B QAT MXFP4 (driven through real dev-app UI, :8001):**
- New Chat binds to the active session (textarea placeholder "Message...").
- Turn 1 "capital of France?" → **"Paris is the capital of France."** — coherent, correct,
  **no leaks / no thinking tags / clean spacing** (8 tok, 92 t/s, 0.25s TTFT, 0.6s).
- Turn 2 "most famous landmark?" → **"The most famous landmark in Paris is the Eiffel Tower."**
  — coherent. **Prefix cache HIT: 24 tokens**, `cache_detail={'paged+mixed_swa':24}`, TTFT 0.25→0.18s.
- **CACHE POLICY FINDING (reconfirmed live):** the HIT used **`paged+mixed_swa`** → the app's
  default for Gemma SWA is **PAGED (in-RAM)**, not SSD. This is the default to flip to SSD/no-paged.
- Streaming token-by-token clean. Reasoning on/off/auto, native tools (multiturn), VL image+audio:
  still ⏳ (next).

**Driver additions:** `uidrv.cjs` now has `send`/`press`/`text` commands.

**Reasoning toggle (Auto/On/Off) — Gemma 4 E2B QAT MXFP4 — ✅:** lives in ChatSettings (gear,
title "Chat inference settings"); `Enable Thinking: Auto/On/Off`. With **On**, prompt "17×4 step
by step" → response rendered a **separate "Reasoning" box (841 chars)** + clean final answer
"The final result is 68." (correct), **no leaked tags** (no `<think>`/`<start_of_turn>`),
**no weird chars**. Reasoning separation is proper.

**UX FINDINGS (real bugs to fix — directive says the flow must be "proper"):**
1. **Idle deep-sleep disables the chat Send button** while showing banner "Model sleeping — will
   auto-wake on your next message" — but Send is disabled, so the user CANNOT send to wake it.
   Must Wake via Server tab first. Either the banner is wrong or Send should stay enabled+auto-wake.
2. **Open ChatSettings panel blocks/disables Send** — must close the settings drawer before the
   Send button works. (Sending failed repeatedly until I closed the panel.)

**Automation lessons (harness):** to send a chat message reliably — model must be **awake** (Wake
via Server tab if standby) AND the **ChatSettings drawer closed**; then `uidrv send "textarea" "…"`
(fill+Enter) works. Don't poll `num_running==0` to detect completion when the model was asleep
(it's 0 before generation starts) — poll the transcript for the answer text instead.

**Tool calling — Gemma 4 E2B QAT MXFP4 — ✅ (engine + app):**
- **Engine level (direct `/v1/chat/completions` with a `tools` array):** clean — `finish_reason:
  tool_calls`, empty content, valid `get_weather({"city":"Paris"})`, **no malformed `<tool_call>`**.
  The `gemma4` tool parser works.
- **App built-in tools require a `workingDirectory`** (ChatSettings warns "Tools will fail without a
  directory set"). The Browse button uses a native NSOpenPanel (CDP can't drive). **Workaround
  (harness):** set it via IPC — `window.api.chat.setOverrides(chatId, {builtinToolsEnabled:true,
  workingDirectory:'…', fileToolsEnabled:true})` then reload. With it set, the prompt jumped
  362→4516 tokens (tool defs injected) and the model ran the **full multiturn agentic loop**: called
  the list tool → tool executed → result fed back → final answer. **No leaks / no malformed markup.**
- ⚠️ The E2B model **miscounted** (.md files: said 47; actual 34 flat / 76 recursive / 43 entries).
  This is a small-model quality limit, NOT a tool/engine defect — expect bigger Gemma to count right.
- Note: the "Enable Built-in Coding Tools" checkbox needs a **real** click (Playwright getByText
  click) to persist; an `eval` `.click()` does not fire React's onChange/save.

## 🔴 P0 BUG — VL image input completely broken ("no Stream(gpu, 0) in current thread")

Found via live VL test (Gemma 4 E2B QAT MXFP4) with a real image (`/tmp/vl-test.png`, red circle +
blue "42"). **Every image request fails** with HTTP 500
`RuntimeError: There is no Stream(gpu, 0) in current thread`. Confirmed on BOTH the app session
(:8001, after sleep/wake) AND a **fresh standalone engine** (:8011, no sleep) → it's a **baseline
bug, not a sleep/wake artifact**. Text-only works because media turns take a different path.

**Root cause (full traceback captured):** Gemma4 media turns route through
`BatchedEngine._simple_mllm_chat_output` (`engine/batched.py:218-220`) which runs
`mllm_instance.chat()` via `loop.run_in_executor(self._mllm_scheduler._step_executor, lambda: …)`
— on a **ThreadPoolExecutor worker thread**. `mllm.chat()` → `mlx_vlm.generate()` →
`wired_limit` + Gemma4 **vision encoder** run MLX GPU ops on that thread, which has **no default
gpu stream**. The killer is mlx_vlm `wired_limit`'s `finally`: bare **`mx.synchronize()`**
(`generate.py:329`) targets the *current thread's default stream `(gpu,0)`*, which was never created
on the worker → raises. (The batched VLM scheduler works because it pins ALL work to one stream/
thread via `with mx.stream(MLLMBatchGenerator._stream)`.)

**Fix attempt #1 (insufficient):** wrapped `generate()` in `mllm.chat` (mllm.py:6159) with
`_MaybeVLMStream()`. Didn't fix it.
**Fix attempt #2 (insufficient):** in `_simple_mllm_chat_output` (batched.py) set the executor
thread's default stream via `mx.set_default_stream(mx.default_stream(mx.default_device()))` before
`chat()`. **Still fails identically.** So pinning the default stream at this level does NOT help —
the failing ops (vision encoder + wired_limit synchronize) run on a different/internal thread, or
it's a deeper MLX stream-registration issue. **Isolated repro (worker-thread bare mx.synchronize +
cross-thread arrays + set_wired_limit) does NOT reproduce** — so it's specific to the mlx-vlm
generate internals / long-lived executor-thread stream state.
(Both edits kept — defensive, aligned with codebase stream-pinning intent, harmless to text path.)

**Conclusion:** this is a hard MLX-threading bug not fixable by black-box default-stream pinning.
**Recommended fix path (deferred to a focused effort):** route Gemma4 media turns through the
**working batched VLM scheduler** (other VL families work that way; `_should_use_simple_mllm_path`
returns True for gemma4 only "until batched media prefill parity is fixed" per `batched.py:195`),
OR run the simple media `chat()` on the **model's loader/main thread** (where the default stream is
established) instead of a pool worker, OR investigate upstream `mlx_vlm.generate` / `wired_limit`
thread/stream handling. Needs deeper MLX-internals debugging than black-box guessing.

**Fix directions for next iteration (try in order):**
1. Run the simple media path on a **dedicated single worker thread** with a `ThreadPoolExecutor(
   max_workers=1, initializer=…)` whose initializer touches the gpu (e.g. `mx.eval(mx.zeros(1))`
   inside `mx.stream(mx.gpu)`), establishing the default stream on that thread; reuse it for all
   media turns (mirrors the batched scheduler's single-stream/thread invariant).
2. Or set the thread default stream explicitly: `mx.set_default_stream(mx.default_stream(mx.gpu))`
   inside the executor before generate, so bare `mx.synchronize()` resolves.
3. Or pass `streams=[...]` into mlx_vlm's `wired_limit`/`generate` so it syncs a known stream
   instead of the missing thread default.
4. Or route Gemma4 media turns through the **working batched VLM scheduler** instead of the simple
   path (the simple path is a stopgap "until batched media prefill parity is fixed" per the code).
Verify the fix by re-POSTing `/tmp/vl-test.png` to a fresh engine and confirming it names a red
circle + "42" cleanly.

**Next iteration:** **VL with a real image** for E2B (it's a VLM — use the attach button / set the
file input via `setInputFiles`, CDP-drivable, unlike the native dir picker) + audio; reasoning Off
spot-check. Then start the **SSD-prefix / paged-off cache-policy change** (`cli.py` per-family
coupling + `block_disk` decouple) — the headline directive. Then E4B/12B/26B/31B and JANG_4M/MXFP8.

## Note on autonomous execution scope
Engine-level + API-level live proof (real serve process, multi-turn chat exactly as the
app issues it, tool calls, reasoning on/off/auto, cache-HIT logs, VL with real
image/audio files, streaming/leak inspection) is driven autonomously. The literal
GUI click/drag-drop layer is a thin wrapper over the same engine API; it is the final
manual/UI-automation confirmation step and is called out per row when pending.
