"""fig：覆盖 WanVideoModelLoader。从已 import 的 Wan 模块取原类，不读尚未合并的全局映射。

创建人：LYC
创建时间：2026-09-21
目录名 zzz_ 保证 Comfy 合并映射时后写覆盖官方类。
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

FIG_MARK = "FIG_WAN_PATCH=v13"


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
        raise ValueError(f"FIG_WAN_V13 {exc}") from None


def _make_wrapper(orig_cls):
    """生成覆盖用的子类。"""

    class FigWanVideoModelLoader(orig_cls):
        """覆盖 loadmodel，入口先把 combo 收成字符串。"""

        def loadmodel(self, *args, **kwargs):
            return _call_coerced(orig_cls.loadmodel, self, args, kwargs)

    FigWanVideoModelLoader.__name__ = "WanVideoModelLoader"
    FigWanVideoModelLoader.__qualname__ = "WanVideoModelLoader"
    return FigWanVideoModelLoader


def _is_loader_class(cls) -> bool:
    """确认是 Wan 的模型加载节点。"""
    return isinstance(cls, type) and getattr(cls, "FUNCTION", None) == "loadmodel"


def _find_original():
    """从已加载的 Wan 模块取原类，不依赖尚未合并的 nodes.NODE_CLASS_MAPPINGS。"""
    for name, mod in list(sys.modules.items()):
        if name.startswith("torch"):
            continue
        path = getattr(mod, "__file__", None) or ""
        if "wanvideo" not in path.replace("\\", "/").lower():
            continue
        cls = getattr(mod, "WanVideoModelLoader", None)
        if _is_loader_class(cls):
            print(FIG_MARK, "found module", name, path, flush=True)
            return cls
    base = Path("/comfyui/custom_nodes")
    if not base.is_dir():
        return None
    for loader in base.glob("*/nodes_model_loading.py"):
        if "wan" not in str(loader).lower():
            continue
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("fig_wan_loader_orig", loader)
            if spec is None or spec.loader is None:
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            cls = getattr(mod, "WanVideoModelLoader", None)
            if _is_loader_class(cls):
                print(FIG_MARK, "found file", loader, flush=True)
                return cls
        except Exception as exc:
            print(FIG_MARK, "file skip", loader, exc, flush=True)
    print(FIG_MARK, "original missing", flush=True)
    return None


_original = _find_original()
if _original is not None:
    _wrapper = _make_wrapper(_original)
    NODE_CLASS_MAPPINGS = {"WanVideoModelLoader": _wrapper}
    print(FIG_MARK, "export wrapper", flush=True)
else:
    NODE_CLASS_MAPPINGS = {}
    print(FIG_MARK, "export empty", flush=True)

NODE_DISPLAY_NAME_MAPPINGS = {}
