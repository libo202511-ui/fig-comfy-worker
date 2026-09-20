"""fig：Comfy 把 WanVideoModelLoader 的 combo 传成 int，在取参之后改成字符串。

创建人：LYC
创建时间：2026-09-20
目录名 zzz_ 保证排在 WanVideoWrapper 之后加载。
"""

from __future__ import annotations

FIG_MARK = "FIG_WAN_PATCH=v9"

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
    if isinstance(value, str):
        return value
    if value is None:
        return default
    return str(value)


def _coerce_input_data_all(data) -> None:
    """原地改 input_data_all（值为 list）。"""
    if not isinstance(data, dict):
        return
    if "attention_mode" in data:
        data["attention_mode"] = [_coerce_mode(item) for item in data["attention_mode"]]
    if "quantization" in data:
        data["quantization"] = [_as_str(item, "disabled") for item in data["quantization"]]
    if "model" in data:
        data["model"] = [_as_str(item) for item in data["model"]]
    print(FIG_MARK, "coerced", data.get("attention_mode"), data.get("quantization"), flush=True)


def _wrap_loadmodel(orig):
    """调用原 loadmodel 前先把 attention_mode / quantization / model 变成 str。"""

    def loadmodel(self, *args, **kwargs):
        if "attention_mode" in kwargs:
            kwargs["attention_mode"] = _coerce_mode(kwargs["attention_mode"])
        if "quantization" in kwargs:
            kwargs["quantization"] = _as_str(kwargs["quantization"], "disabled")
        if "model" in kwargs:
            kwargs["model"] = _as_str(kwargs["model"])
        args = list(args)
        if args:
            args[0] = _as_str(args[0])
        if len(args) >= 4:
            args[3] = _as_str(args[3], "disabled")
        if len(args) >= 6:
            args[5] = _coerce_mode(args[5])
        return orig(self, *args, **kwargs)

    loadmodel._fig_wan_wrapped = True
    return loadmodel


def _is_node_class(cls) -> bool:
    """排除 torch.classes 代理。"""
    return isinstance(cls, type)


def _patch_class(cls) -> bool:
    """包装 loadmodel。"""
    if not _is_node_class(cls):
        return False
    fn = getattr(cls, "loadmodel", None)
    if fn is None or getattr(fn, "_fig_wan_wrapped", False):
        return False
    cls.loadmodel = _wrap_loadmodel(fn)
    return True


def _patch_mapping() -> int:
    """NODE_CLASS_MAPPINGS 里能找到就包一层。"""
    count = 0
    try:
        import nodes as comfy_nodes
    except Exception as exc:
        print(FIG_MARK, "nodes import failed", exc, flush=True)
        return 0
    mappings = getattr(comfy_nodes, "NODE_CLASS_MAPPINGS", None)
    if not isinstance(mappings, dict):
        return 0
    cls = mappings.get("WanVideoModelLoader")
    try:
        if cls is not None and _patch_class(cls):
            count += 1
            print(FIG_MARK, "mapped WanVideoModelLoader", flush=True)
    except Exception as exc:
        print(FIG_MARK, "map skip", exc, flush=True)
    return count


def ensure_hooks() -> bool:
    """钩住 execution.get_input_data，节点真正取参后再改 int→str。"""
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
                _coerce_input_data_all(data)
        except Exception as exc:
            print(FIG_MARK, "coerce skip", exc, flush=True)
        return result

    hooked._fig_wan_hooked = True
    execution.get_input_data = hooked
    print(FIG_MARK, "hooked get_input_data", flush=True)
    return True


def _boot() -> None:
    """加载时先钩 execution，再包 class。"""
    hooked = ensure_hooks()
    mapped = _patch_mapping()
    print(FIG_MARK, "boot hooked", hooked, "mapped", mapped, flush=True)


_boot()

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
