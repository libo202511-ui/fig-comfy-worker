"""fig：Comfy 把 WanVideoModelLoader 的 combo 传成 int 时，在取参和调用处收成字符串。

创建人：LYC
创建时间：2026-09-20
目录名 zzz_ 保证排在 WanVideoWrapper 之后加载。
"""

from __future__ import annotations

FIG_MARK = "FIG_WAN_PATCH=v11"


def _as_str(value, default=""):
    """任意值收成字符串，避免后续 '"x" in 3'。"""
    if isinstance(value, str):
        return value
    if value is None:
        return default
    return str(value)


def _wrap_loadmodel(orig):
    """入口强制 sdpa，TypeError 带 FIG_WAN_V11 以便确认新代码已执行。"""

    def loadmodel(self, *args, **kwargs):
        kwargs["attention_mode"] = "sdpa"
        if "quantization" in kwargs:
            kwargs["quantization"] = _as_str(kwargs["quantization"], "disabled")
        if "model" in kwargs:
            kwargs["model"] = _as_str(kwargs["model"])
        if "base_precision" in kwargs:
            kwargs["base_precision"] = _as_str(kwargs["base_precision"], "fp16")
        if "load_device" in kwargs:
            kwargs["load_device"] = _as_str(kwargs["load_device"], "offload_device")
        args = list(args)
        if args:
            args[0] = _as_str(args[0])
        try:
            return orig(self, *args, **kwargs)
        except TypeError as exc:
            raise TypeError(f"FIG_WAN_V11 {exc}") from exc

    loadmodel._fig_wan_wrapped = True
    return loadmodel


def _patch_mapping() -> int:
    """NODE_CLASS_MAPPINGS 里能找到就包一层。"""
    try:
        import nodes as comfy_nodes
    except Exception as exc:
        print(FIG_MARK, "nodes import failed", exc, flush=True)
        return 0
    mappings = getattr(comfy_nodes, "NODE_CLASS_MAPPINGS", None)
    if not isinstance(mappings, dict):
        return 0
    cls = mappings.get("WanVideoModelLoader")
    if not isinstance(cls, type):
        print(FIG_MARK, "mapping missing", flush=True)
        return 0
    fn = getattr(cls, "loadmodel", None)
    if fn is None or getattr(fn, "_fig_wan_wrapped", False):
        return 0
    cls.loadmodel = _wrap_loadmodel(fn)
    print(FIG_MARK, "mapped WanVideoModelLoader", flush=True)
    return 1


def ensure_hooks() -> bool:
    """钩住 execution.get_input_data，节点取参后再改 int→str。"""
    try:
        import execution
    except Exception as exc:
        print(FIG_MARK, "execution import failed", exc, flush=True)
        return False
    orig = getattr(execution, "get_input_data", None)
    if orig is None:
        print(FIG_MARK, "get_input_data missing", flush=True)
        return False
    if getattr(orig, "_fig_wan_hooked", False):
        return True

    def hooked(inputs, class_def, *args, **kwargs):
        result = orig(inputs, class_def, *args, **kwargs)
        try:
            if getattr(class_def, "__name__", "") == "WanVideoModelLoader":
                data = result[0] if isinstance(result, tuple) else result
                if isinstance(data, dict):
                    data["attention_mode"] = ["sdpa"]
                    if "quantization" in data:
                        data["quantization"] = [_as_str(x, "disabled") for x in data["quantization"]]
                    if "model" in data:
                        data["model"] = [_as_str(x) for x in data["model"]]
                    print(FIG_MARK, "coerced", data.get("attention_mode"), flush=True)
        except Exception as exc:
            print(FIG_MARK, "coerce skip", exc, flush=True)
        return result

    hooked._fig_wan_hooked = True
    execution.get_input_data = hooked
    print(FIG_MARK, "hooked get_input_data", flush=True)
    return True


def _boot() -> None:
    """只钩 execution、包 class，不再 reload，避免碰到 torch.classes。"""
    hooked = ensure_hooks()
    mapped = _patch_mapping()
    print(FIG_MARK, "boot hooked", hooked, "mapped", mapped, flush=True)


_boot()

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
