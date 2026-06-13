# vMLX — Default Cache Policy + Mandatory Live‑App Testing Protocol

**Status:** MANDATORY from 2026‑06‑13. Directive by Eric.
**Scope:** Python `vmlx_engine` + panel (Electron) app. Applies to every model family.
**Rule of thumb:** A model + engine is **only** declared "OK" after it has been driven
**live, in the real dev‑build app, as a real user**, end‑to‑end, per the checklist in
Part C. Inventory gates and unit tests are *necessary but never sufficient* — they do
not load weights and do not prove coherence, tool calling, reasoning, cache reuse, or
the absence of leaks. **Live proof or it didn't happen.**

---

## Part A — Default Cache Policy (NEW — inverts prior behavior)

### A.1 The two hard defaults

1. **Paged cache memory is OFF by default for ALL models.**
   No family may silently "upgrade prefix‑only → paged". The prior policy
   (`_apply_zaya_cca_cache_policy`, `_apply_dsv4_cache_policy` forcing
   `args.use_paged_cache = True`) is **reversed**: paged is opt‑in only.

2. **SSD cache is the default prefix‑cache backing for ALL models.**
   "SSD cache" = the on‑disk store (`disk_cache.py` L2 + `block_disk_store.py`
   per‑family records). Prefix caching stays **ON by default**, but its storage
   tier is **SSD**, not paged GPU/host‑RAM blocks and not the in‑RAM memory‑aware
   LRU as the primary.

> Net effect on flags (engine CLI / SettingsStore):
> - `use_paged_cache` → default **False** for every family.
> - `enable_prefix_cache` → default **True** (SSD‑backed).
> - `enable_block_disk_cache` / disk L2 → default **True** (this is now the prefix tier).
> - The "prefix requires paged" coupling in `cli.py` per‑family policy blocks must be
>   rewritten so prefix → SSD, not prefix → paged.

### A.2 Per‑family SSD prefix‑cache storage types (each must be confirmed)

Every family needs its **own** SSD record format that captures *all* state required to
resume, not just generic KV. Each must show a confirmed **HIT**, good **TTFT** on the
hit, and correct **RQ (TurboQuant) KV encode/decode** round‑trip through SSD.

| Family | State that MUST persist to SSD | SSD record notes |
|---|---|---|
| Standard dense LLM (Llama/Qwen dense) | KV only | TurboQuant RQ KV encode→SSD→decode round‑trip |
| MoE (DeepSeek/GLM/MiniMax/Gemma‑4‑26B‑A4B) | KV (CacheList, recursive) | per‑expert routing unaffected; RQ KV round‑trip |
| Hybrid SSM (Nemotron‑H, Qwen3.5/Qwen3‑Next GatedDeltaNet, Jamba, Falcon‑H1, Baichuan‑M1, LFM2, GraniteMoeHybrid) | KV **+ SSM companion state** | both must be in the SSD record; companion is cumulative — deep‑copy on fetch |
| CCA (ZAYA) | KV **+ CCA conv_state + prev_hs** | SSD form of `zaya_cca_v1`; `block_disk_store` already has a `_zaya_kv` lane to extend |
| CSA / HCA composite (DSV4‑Flash) | SWA window **+ CSA/HCA compressed pools** (prompt‑boundary `DeepseekV4Cache` snapshot) | composite record, not generic KV pages |
| SWA / sliding window (generic) | `RotatingKVCache` window state | preserve window offset/left‑padding |
| **Gemma SWA** (Gemma 4 family) | per‑layer SWA windows; **asymmetric KV heads** | preserve **all** config‑declared KV head counts (full vs SWA layers can declare different KV‑head counts — never slice every layer to the primary count) |
| MLA (Mistral 4 / DeepSeek‑V3) | KV (MLA‑shaped) | KV‑quant disabled for MLA; SSD record honors that |
| VL — text‑only turn | standard prefix SSD cache (+ SSM if hybrid VL) | routes via MLLM scheduler; `num_images == 0` → standard tokenizer path |
| VL — image/audio/video turn | **no cache — full prefill** | `num_images > 0` (or media salt set) → never cache‑reuse the media turn |

### A.3 TurboQuant (RQ) KV through SSD

- TurboQuant stays auto‑enabled for the KV component (attention layers) where the
  family allows it (disabled for MLA; attn‑only for hybrids).
- The RQ **encode → SSD serialize → SSD deserialize → decode** path must round‑trip
  bit‑faithfully. Confirm via TQ‑native serialization markers (`__tq_native__`) and a
  live restart→recall HIT, not just an in‑process store/fetch.

---

## Part B — Autodetection requirements (verified live, in app)

For each model load, confirm in the app/load logs:

- [ ] **Model loads** without error in the real dev build.
- [ ] **Family / model_type autodetected** correctly (three‑tier: text_config →
      config.json model_type → name regex). VL detection uses `jang_config.has_vision`
      first, then config.json `vision_config`.
- [ ] **Generative config param defaults** resolved **from the model** (engine resolves
      per‑model gen‑config universally). The **panel must NOT override** model gen‑config.
      **No fake fallbacks** (e.g. the forbidden `DEFAULT_BOUNDED_TOP_K=40`). temperature /
      top_p / top_k / repetition come from `generation_config.json` / model owner.
- [ ] **`config.json` + `jang_config.json` honored** (incl. `mxtq_bits` per‑projection
      schema, `mxtq_seed`, block/group size, `has_vision`, routed‑expert bits).
- [ ] **Reasoning parser autodetected** (family‑correct).
- [ ] **Tool parser autodetected** (family‑correct).
- [ ] **Cache types detected** and logged: **paged OFF**, **SSD prefix ON**, correct
      per‑family SSD store (SSM companion / CCA / CSA‑HCA / SWA / MLA).

---

## Part C — Mandatory live in‑app test sequence (THE only proof)

Run this **per model, in the real dev‑build app, behaving as a real user**. Do not
substitute curl/pytest for the user‑facing steps — they are part of the proof.

1. **Build a temporary real dev build** of vMLX (actual app bundle, not just the engine
   CLI). Use a throwaway/dev build so production `/Applications/vMLX.app` is untouched.
2. **Launch the app, load the model from the UI.** Capture load logs (Part B).
3. **Send a real first message** in chat → confirm a coherent, usable response.
4. **Multi‑turn conversation** (≥3 turns) as a real user.
5. **Enable the built‑in native tools** via the UI toggles, then **drive multi‑turn
   tool calling** — the model must actually call tools and consume results across turns
   **without issue** (no malformed `<tool_call>`, no zero‑parsed‑tool‑call failures).
6. **Reasoning toggle** — exercise **on / off / auto** from the UI; confirm each mode
   behaves correctly and the reasoning parser produces clean thinking separation.
7. **Tool parser** — confirm parsed tool calls are structurally valid for the family;
   no raw markup leaking into visible content.
8. **Cache reuse** — repeat / extend the conversation to force a **prefix SSD cache
   HIT**; confirm in logs (HIT, store type, tokens matched) **and** a visible **TTFT**
   improvement. Verify across endpoints: Chat Completions (content + stream delta),
   `/v1/responses` (content + delta), Ollama chat/generate, Anthropic messages.
9. **VL models** — test with a **real image** (vision) **and real audio** (and **video**
   where the row requires it). Confirm the media turn does full prefill (no cache) and
   the *next* text turn can still hit the text prefix SSD cache.
10. **Streaming integrity** — token‑by‑token frames, heartbeat keep‑alive, final
    `[DONE]`, no batching artifacts.
11. **Leak / hygiene check (utter)** — **zero** thinking‑tag leaks, **zero** stray
    template/tool markup, **no** weird characters, **no** broken spacing/syntax in any
    visible content across all of the above.
12. **Verdict** — only if 1–11 all pass: model is "OK". Otherwise record the exact
    failing surface as a blocker (no smoothing over).

---

## Part D — Per‑model coverage matrix (fill per release)

Focus families (current): **Gemma 4** — E2B, E4B, 12B, 26B‑A4B, 31B —
× formats **JANG_4M / MXFP4 / MXFP8 / QAT** × the columns below.
Extend rows for every other shipped family.

| Model · format | Loads | Autodetect (B) | Gen‑cfg defaults | SSD prefix HIT + TTFT | RQ KV enc/dec | Reasoning on/off/auto | Tool parser (multiturn) | VL image | Audio | Video | Streaming/leaks | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| gemma‑4‑E2B‑it‑qat‑MXFP4 |  |  |  |  |  |  |  |  |  |  |  |  |
| gemma‑4‑E2B‑it‑qat‑JANG_4M |  |  |  |  |  |  |  |  |  |  |  |  |
| gemma‑4‑E4B‑it‑qat‑MXFP4 |  |  |  |  |  |  |  |  |  |  |  |  |
| gemma‑4‑E4B‑it‑qat‑JANG_4M |  |  |  |  |  |  |  |  |  |  |  |  |
| gemma‑4‑12B‑it‑qat‑MXFP4 |  |  |  |  |  |  |  |  |  |  |  |  |
| gemma‑4‑12B‑it‑qat‑JANG_4M |  |  |  |  |  |  |  |  |  |  |  |  |
| gemma‑4‑26B‑A4B‑it‑qat‑MXFP4 |  |  |  |  |  |  |  |  |  |  |  |  |
| gemma‑4‑26B‑A4B‑it‑qat‑JANG_4M |  |  |  |  |  |  |  |  |  |  |  |  |
| gemma‑4‑31B‑it‑qat‑MXFP4 |  |  |  |  |  |  |  |  |  |  |  |  |
| gemma‑4‑31B‑it‑qat‑JANG_4M |  |  |  |  |  |  |  |  |  |  |  |  |

Legend: ✅ pass · ❌ fail (link evidence) · ➖ N/A for this model · ⏳ not yet run.

---

## Part E — Definition of done

- Engine default cache policy matches Part A (paged OFF, SSD prefix ON per family).
- Every focus‑family row in Part D is ✅ across **all** applicable columns, proven by
  the Part C live‑app sequence with captured evidence (logs, screenshots, transcripts).
- Any ❌ is an explicit, named release blocker — never reclassified as a packaging or
  inventory pass.

---

## Implementation backlog (tracking — to execute against this protocol)

- [ ] **Code:** flip engine defaults — `use_paged_cache=False`, SSD/L2 prefix default ON,
      for all families; rewrite the per‑family "prefix→paged" coupling in `cli.py`
      (`_apply_zaya_cca_cache_policy`, `_apply_dsv4_cache_policy`) to "prefix→SSD".
- [ ] **Code:** ensure each family's SSD record (Part A.2) persists full resume state —
      extend `block_disk_store.py` lanes (SSM companion, `_zaya_kv` CCA conv_state+prev_hs,
      DSV4 SWA+CSA/HCA composite, Gemma SWA asymmetric heads, MLA).
- [ ] **Code:** panel/SettingsStore + UI defaults reflect paged‑off / SSD‑prefix‑on;
      reasoning on/off/auto toggle wired and correct per family.
- [ ] **Test:** run Part C live in the dev‑build app for each Gemma 4 QAT row, fill Part D.
