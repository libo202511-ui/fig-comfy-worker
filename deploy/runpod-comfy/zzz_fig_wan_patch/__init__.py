"""fig：Comfy 把 WanVideoModelLoader 的 combo 传成 int，运行时改成字符串。

创建人：LYC
创建时间：2026-09-20
目录名 zzz_ 保证排在 WanVideoWrapper 之后加载。
"""

from __future__ import annotations

FIG_MARK = "FIG_WAN_PATCH=v8"

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


def _stringify_combo(spec, key):
    """把 combo 下拉改成 STRING，避免 Comfy 把 API 值收成下标。"""
    if not isinstance(spec, dict):
        return
    for section in ("required", "optional"):
        fields = spec.get(section)
        if isinstance(fields, dict) and key in fields:
            fields[key] = ("STRING", {"default": "sageattn" if key == "attention_mode" else "disabled"})


def _is_node_class(cls) -> bool:
    """排除 torch.classes 代理：对它做 getattr 会抛 RuntimeError。"""
    return isinstance(cls, type)


def _patch_class(cls) -> bool:
    """包装 loadmodel，并把 attention_mode / quantization 改成 STRING。"""
    if not _is_node_class(cls):
        return False
    changed = False
    fn = getattr(cls, "loadmodel", None)
    if fn is not None and not getattr(fn, "_fig_wan_wrapped", False):
        cls.loadmodel = _wrap_loadmodel(fn)
        changed = True
    orig_types = getattr(cls, "INPUT_TYPES", None)
    if orig_types is not None and not getattr(cls, "_fig_input_patched", False):

        def input_types(_cls=cls, _orig=orig_types):
            spec = _orig() if callable(_orig) else _orig
            _stringify_combo(spec, "attention_mode")
            _stringify_combo(spec, "quantization")
            return spec

        cls.INPUT_TYPES = classmethod(lambda _cls, _fn=input_types: _fn())
        cls._fig_input_patched = True
        changed = True
    return changed


def _patch_all() -> int:
    """只打 NODE_CLASS_MAPPINGS 里的 WanVideoModelLoader。"""
    count = 0
    try:
        import nodes as comfy_nodes
    except Exception as exc:
        print(FIG_MARK, "nodes import failed", exc, flush=True)
        comfy_nodes = None
    mappings = getattr(comfy_nodes, "NODE_CLASS_MAPPINGS", None) if comfy_nodes else None
    if isinstance(mappings, dict):
        cls = mappings.get("WanVideoModelLoader")
        try:
            if cls is not None and _patch_class(cls):
                count += 1
                print(FIG_MARK, "mapped WanVideoModelLoader", flush=True)
        except Exception as exc:
            print(FIG_MARK, "map skip", exc, flush=True)
    print(FIG_MARK, "patched", count, flush=True)
    return count


_patch_all()

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
