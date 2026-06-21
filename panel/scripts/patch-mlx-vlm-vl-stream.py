#!/usr/bin/env python3
"""Build-time patch: make mlx_vlm.generate.wired_limit teardown sync stream-safe.

vMLX P0 VL stream fix. The simple-MLLM VL path runs the mlx_vlm generation on
the mllm-worker executor thread. mlx_vlm's ``wired_limit`` captures the module
global ``generation_stream`` (a ``Stream(gpu, 0)`` bound to the import thread),
and its ``finally`` block calls ``mx.synchronize(s)`` on a thread that has no
such stream -> ``RuntimeError: There is no Stream(gpu, 0) in current thread``
AFTER a perfectly good generation. Guard each per-stream sync so it falls back
to a plain current-thread ``mx.synchronize()``.

Usage: python patch-mlx-vlm-vl-stream.py <site-packages-dir>
Idempotent; exits 0 whether it patched, was already patched, or the upstream
shape changed (logged, non-fatal — the engine-side rebind still covers the
common case).
"""
import os
import sys

OLD = (
    "    finally:\n"
    "        if streams is not None:\n"
    "            for s in streams:\n"
    "                mx.synchronize(s)\n"
    "        else:\n"
    "            mx.synchronize()\n"
    "        mx.set_wired_limit(old_limit)"
)

NEW = (
    "    finally:\n"
    "        if streams is not None:\n"
    "            for s in streams:\n"
    "                try:\n"
    "                    mx.synchronize(s)\n"
    "                except Exception:\n"
    "                    try:\n"
    "                        mx.synchronize()\n"
    "                    except Exception:\n"
    "                        pass\n"
    "        else:\n"
    "            mx.synchronize()\n"
    "        try:\n"
    "            mx.set_wired_limit(old_limit)\n"
    "        except Exception:\n"
    "            pass"
)


def main() -> int:
    site = sys.argv[1] if len(sys.argv) > 1 else ""
    path = os.path.join(site, "mlx_vlm", "generate.py")
    if not os.path.exists(path):
        print("  mlx_vlm generate.py not found; VL wired_limit patch skipped")
        return 0
    with open(path) as f:
        content = f.read()
    if NEW in content or "                    mx.synchronize(s)\n" in content:
        print("  Already patched: mlx_vlm generate.py wired_limit (VL stream fix)")
        return 0
    if OLD in content:
        with open(path, "w") as f:
            f.write(content.replace(OLD, NEW))
        print("  Patched: mlx_vlm generate.py wired_limit sync-safe (VL stream fix)")
        return 0
    print("  WARN: mlx_vlm generate.py wired_limit shape changed; VL patch not applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
