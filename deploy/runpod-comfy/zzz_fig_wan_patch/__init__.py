"""fig：Comfy 把 WanVideoModelLoader 的 combo 传成 int，在取参之后改成字符串。

创建人：LYC
创建时间：2026-09-20
目录名 zzz_ 保证排在 WanVideoWrapper 之后加载。
"""

from __future__ import annotations

FIG_MARK = "FIG_WAN_PATCH=v10"
FORCE_MARK = "FIG_WAN_FORCE_SDPA"

ATTENTION_MODES = (
    "sdpa",
    "flash_attn_2",
    "flash_attn_3",
    "sageattn",
    "sageattn_3",
    "radial_sage_attention",
    "sageattn_compiled",
    "sageattn_ultravico",
    "comfy",
)


def _coerce_mode(value):
    """把 combo 下标或其它非字符串还原成 attention_mode 名。"""
    if isinstance(value, str):
        return value
    try:
        return ATTENTION_MODES[int(value)]
    except Exception:
        return "sdpa"


def _as_str(value, default=""):
    """任意值收成字符串，避免后续 `"x" in 3`。"""
    if
