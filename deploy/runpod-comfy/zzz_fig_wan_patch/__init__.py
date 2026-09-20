"""fig：用包装类覆盖 WanVideoModelLoader，避免 combo 传 int 时 '"x" in 3'。

创建人：LYC
创建时间：2026-09-20
目录名 zzz_ 保证在 WanVideoWrapper 之后合并 NODE_CLASS_MAPPINGS。
"""

from __future__ import annotations

import inspect

FIG_MARK = "FIG_WAN_PATCH=v12"


def _as_str(value, default=""):
    """任意值收成字符串。"""
    if isinstance(value, str):
        return value
    if value is None:
        return default
    return str(value)


def _call_coerced(orig, self, args, kwargs):
    """按签名绑定后强制 sdpa，再调用原 loadmodel。"""
    bound = inspect.signature(orig).bind(self, *args, **kwargs)
    bound.apply_defaults()
    arguments = bound.arguments
    arguments["attention_mode"] = "sdpa"
    if "quantization" in arguments:
        arguments["quantization"] = _as_str(arguments["quantization"], "disabled")
    if "model" in arguments:
        arguments["model"] = _as_str(arguments["model"])
    if "base_precision" in arguments:
        arguments["base_precision"] = _as_str(arguments["base_precision"], "fp16")
    if "load_device" in arguments:
        arguments["load_device"] = _as_str(arguments["load_device"], "offload_device")
    print(FIG_MARK, "call", arguments.get("model"), arguments.get("attention_mode"), flush=True)
    try:
        return orig(*bound.args, **bound.kwargs)
    except TypeError as exc:
        raise ValueError(f"FIG_WAN_V12 {exc}") from None


def _make_wrapper(orig_cls):
    """生成覆盖用的子类。"""

    class FigWanVideoModelLoader(orig_cls):
        """覆盖 loadmodel，入口先把 combo 收成字符串。"""

        def loadmodel(self, *args, **kwargs):
            return _call_coerced(orig_cls.loadmodel, self, args, kwargs)

    FigWanVideoModelLoader.__name__ = "WanVideoModelLoader"
    FigWanVideoModelLoader.__qualname__ = "WanVideoModelLoader"
    return FigWanVideoModelLoader


def _find_original():
    """从全局映射取出尚未包装的原类。"""
    try:
        import nodes as comfy_nodes
    except Exception as exc:
        print(FIG_MARK, "nodes import failed", exc, flush=True)
        return None
    mappings = getattr(comfy_nodes, "NODE_CLASS_MAPPINGS", None)
    if not isinstance(mappings, dict):
        return None
    cls = mappings.get("WanVideoModelLoader")
    if not isinstance(cls, type):
        print(FIG_MARK, "original missing", flush=True)
        return None
    return cls


_original = _find_original()
if _original is not None:
    _wrapper = _make_wrapper(_original)
    try:
        import nodes as comfy_nodes
        comfy_nodes.NODE_CLASS_MAPPINGS["WanVideoModelLoader"] = _wrapper
        print(FIG_MARK, "replaced global mapping", flush=True)
    except Exception as exc:
        print(FIG_MARK, "global replace skip", exc, flush=True)
    NODE_CLASS_MAPPINGS = {"WanVideoModelLoader": _wrapper}
    print(FIG_MARK, "export wrapper", flush=True)
else:
    NODE_CLASS_MAPPINGS = {}
    print(FIG_MARK, "export empty", flush=True)

NODE_DISPLAY_NAME_MAPPINGS = {}
