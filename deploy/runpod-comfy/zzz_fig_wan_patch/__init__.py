"""fig：覆盖 WanVideoModelLoader，按节点选项表还原 combo 下标，并在 TypeError 时报出出错文件行。

创建人：LYC
创建时间：2026-09-21
目录名 zzz_ 保证 Comfy 合并映射时后写覆盖官方类。
"""

from __future__ import annotations

import inspect
import sys
import traceback
from pathlib import Path

FIG_MARK = "FIG_WAN_PATCH=v17"

# 入参快照进 RunPod details，过长会被平台截断
MAX_DUMP_CHARS = 700
# 只留最后几层栈，足够定位到出错的 in 判断
TRACE_FRAMES = 4
# comfy 的 load_torch_file 在 except 里做 '...' in e.args[0]，errno 是 int 时它自己会崩，
# 把真实异常盖成 TypeError。原异常还挂在 __context__ 上，往上捞这么多层
CAUSE_DEPTH = 3


def _combo_options(cls) -> dict[str, list[str]]:
    """从节点 INPUT_TYPES 取出 combo 选项表。

    @param cls 原始节点类
    @return {入参名: 选项列表}，取不到时为空
    """
    options: dict[str, list[str]] = {}
    try:
        spec = cls.INPUT_TYPES()
    except Exception as exc:
        print(FIG_MARK, "input_types skip", exc, flush=True)
        return options
    for section in ("required", "optional"):
        group = spec.get(section) if isinstance(spec, dict) else None
        if not isinstance(group, dict):
            continue
        for name, item in group.items():
            if not isinstance(item, (list, tuple)) or not item:
                continue
            choices = item[0]
            if isinstance(choices, (list, tuple)) and choices and all(isinstance(c, str) for c in choices):
                options[name] = list(choices)
    return options


def _str_default_names(orig) -> set[str]:
    """默认值是字符串的形参，这些位置收到数字一定是 combo 被写成了下标。

    @param orig 原始 loadmodel 函数
    @return 形参名集合
    """
    return {
        param.name
        for param in inspect.signature(orig).parameters.values()
        if isinstance(param.default, str)
    }


def _coerce_value(name: str, value, options: dict[str, list[str]], str_names: set[str]):
    """把 combo 下标换成选项名；越界或无选项表时退化成字符串。

    @param name      入参名
    @param value     入参值
    @param options   combo 选项表
    @param str_names 默认值为字符串的形参名
    @return 收敛后的值
    """
    if isinstance(value, bool) or not isinstance(value, int):
        return value
    choices = options.get(name)
    if choices:
        if 0 <= value < len(choices):
            return choices[value]
        print(FIG_MARK, "index out of range", name, value, flush=True)
        return choices[0]
    if name in str_names:
        return str(value)
    return value


def _dump_arguments(arguments: dict) -> str:
    """把入参的值和类型压成一行，便于在失败 JSON 里直接看出谁是 int。

    @param arguments 已绑定的入参
    @return 单行快照
    """
    parts = []
    for key, value in arguments.items():
        if key == "self":
            continue
        shown = value if isinstance(value, (str, int, float, bool, type(None))) else type(value).__name__
        parts.append(f"{key}={shown!r}:{type(value).__name__}")
    text = " ".join(parts)
    return text[:MAX_DUMP_CHARS]


def _cause_chain(exc: BaseException) -> str:
    """捞出被 comfy 错误处理盖掉的原始异常。

    @param exc 捕获到的异常
    @return 形如 FileNotFoundError: [Errno 2] ...，没有则为空串
    """
    parts = []
    cur = exc.__cause__ or exc.__context__
    while cur is not None and len(parts) < CAUSE_DEPTH:
        parts.append(f"{type(cur).__name__}: {cur}")
        cur = cur.__cause__ or cur.__context__
    return " <- ".join(parts)


def _lora_probe(lora) -> str:
    """报出每个 LoRA 的路径、是否存在、大小，定位盘上文件问题。

    @param lora WanVideoLoraSelect 传进来的列表
    @return 单行快照，非列表时为空串
    """
    if not isinstance(lora, (list, tuple)):
        return ""
    parts = []
    for index, item in enumerate(lora):
        if not isinstance(item, dict):
            parts.append(f"lora[{index}]={type(item).__name__}")
            continue
        path = item.get("path")
        info = f"lora[{index}] path={path!r} strength={item.get('strength')!r}"
        try:
            target = Path(str(path))
            info += f" exists={target.is_file()}"
            if target.is_file():
                info += f" size={target.stat().st_size}"
        except OSError as exc:
            info += f" stat_err={exc}"
        parts.append(info)
    return " | ".join(parts)


def _format_frames(exc: BaseException) -> str:
    """取异常栈最后几层的 文件:行:函数，定位真正出错的 in 判断。

    @param exc 捕获到的异常
    @return 形如 a.py:12:f > b.py:34:g
    """
    frames = traceback.extract_tb(exc.__traceback__)[-TRACE_FRAMES:]
    return " > ".join(f"{Path(f.filename).name}:{f.lineno}:{f.name}" for f in frames)


def _call_coerced(orig, self, args, kwargs, options, str_names):
    """按签名绑定后还原 combo，再调用原 loadmodel。

    @param orig      原始 loadmodel
    @param self      节点实例
    @param args      位置参数
    @param kwargs    关键字参数
    @param options   combo 选项表
    @param str_names 默认值为字符串的形参名
    @return 原 loadmodel 返回值
    """
    bound = inspect.signature(orig).bind(self, *args, **kwargs)
    bound.apply_defaults()
    arguments = bound.arguments
    for key in list(arguments):
        if key == "self":
            continue
        arguments[key] = _coerce_value(key, arguments[key], options, str_names)
    dump = _dump_arguments(arguments)
    loras = _lora_probe(arguments.get("lora"))
    print(FIG_MARK, "call", dump, loras, flush=True)
    try:
        return orig(*bound.args, **bound.kwargs)
    except TypeError as exc:
        raise ValueError(
            f"FIG_WAN_V17 {exc} | cause {_cause_chain(exc) or 'none'}"
            f" | {loras or 'no lora'} | at {_format_frames(exc)} | {dump}"
        ) from None


def _make_wrapper(orig_cls):
    """生成覆盖用的子类。

    @param orig_cls 原始节点类
    @return 同名子类
    """
    options = _combo_options(orig_cls)
    str_names = _str_default_names(orig_cls.loadmodel)
    print(FIG_MARK, "combo inputs", sorted(options), flush=True)

    class FigWanVideoModelLoader(orig_cls):
        """覆盖 loadmodel，入口先把 combo 下标还原成选项名。"""

        def loadmodel(self, *args, **kwargs):
            """还原 combo 后转交原实现。

            @param args   位置参数
            @param kwargs 关键字参数
            @return 原 loadmodel 返回值
            """
            return _call_coerced(orig_cls.loadmodel, self, args, kwargs, options, str_names)

    FigWanVideoModelLoader.__name__ = "WanVideoModelLoader"
    FigWanVideoModelLoader.__qualname__ = "WanVideoModelLoader"
    return FigWanVideoModelLoader


def _is_loader_class(cls) -> bool:
    """确认是 Wan 的模型加载节点。

    @param cls 待判定对象
    @return 是否为目标节点类
    """
    return isinstance(cls, type) and getattr(cls, "FUNCTION", None) == "loadmodel"


def _find_original():
    """从已加载的 Wan 模块取原类，不依赖尚未合并的 nodes.NODE_CLASS_MAPPINGS。

    @return 原始节点类，找不到返回 None
    """
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
    NODE_CLASS_MAPPINGS = {"WanVideoModelLoader": _make_wrapper(_original)}
    print(FIG_MARK, "export wrapper", flush=True)
else:
    NODE_CLASS_MAPPINGS = {}
    print(FIG_MARK, "export empty", flush=True)

NODE_DISPLAY_NAME_MAPPINGS = {}
