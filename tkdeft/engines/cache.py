"""绘制结果缓存。

为什么需要
----------
tkfluent 的一次 hover 会让同一个 ``RoundRectSpec`` 被反复绘制（rest→hover 的
渐变动画最多几十帧，多个同尺寸按钮更是完全同参）。没有缓存时每次都要重新
光栅化并新建 ``PhotoImage``——实测这正是端到端耗时的大头。

缓存键
------
``(引擎名, spec)``。spec 是 ``frozen dataclass``，天然可哈希。

生命周期与"空图"陷阱
--------------------
``PhotoImage`` 绑定在具体的 Tk 解释器上，且 **一旦被垃圾回收，引用它的
canvas item 会变成空白**。因此这里刻意 **不做 LRU 淘汰**，而是采用
"像素预算 + 满了就不再写入"的策略：已经发出去的图片永远保持存活，
新的、缓存不下的规格就退化为"每次都重新渲染"——只损失速度，绝不损坏画面。

解释器用 ``id()`` 作键（``_tkinter.tkapp`` 不支持 weakref），并用对象同一性
校验，避免 id 复用导致的串台。
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from typing import Any, Dict, Optional, Tuple

__all__ = ["get_cache", "clear_cache", "cache_stats", "set_cache_budget"]

#: 默认像素预算：约 8M 像素（32 MB 位图 + Tk 侧副本），足够覆盖常见界面
DEFAULT_PIXEL_BUDGET = 8_000_000

#: 同时保留的解释器缓存上限（多窗口 / 反复重建 root 的场景）
_MAX_INTERPRETERS = 8


class ImageCache:
    """单个 Tk 解释器对应的绘制结果缓存。"""

    __slots__ = ("_entries", "_pixels", "_budget", "_hits", "_misses", "_overflow")

    def __init__(self, budget: int = DEFAULT_PIXEL_BUDGET) -> None:
        self._entries: "OrderedDict[Any, Tuple[Any, int]]" = OrderedDict()
        self._pixels = 0
        self._budget = budget
        self._hits = 0
        self._misses = 0
        self._overflow = 0

    # -- 查询 -------------------------------------------------------------
    def get(self, key: Any):
        item = self._entries.get(key)
        if item is None:
            self._misses += 1
            return None
        self._hits += 1
        self._entries.move_to_end(key)
        return item[0]

    # -- 写入 -------------------------------------------------------------
    def put(self, key: Any, photo, pixels: int) -> bool:
        """写入缓存；超出预算时 **静默放弃**（已发出的图片保持有效）。

        返回是否真的写入了缓存。
        """
        if key in self._entries:
            return True
        if self._pixels + pixels > self._budget:
            self._overflow += 1
            return False
        self._entries[key] = (photo, pixels)
        self._pixels += pixels
        return True

    # -- 维护 -------------------------------------------------------------
    def clear(self) -> int:
        count = len(self._entries)
        self._entries.clear()
        self._pixels = 0
        return count

    @property
    def budget(self) -> int:
        return self._budget

    @budget.setter
    def budget(self, value: int) -> None:
        self._budget = max(0, int(value))

    def stats(self) -> Dict[str, Any]:
        total = self._hits + self._misses
        return {
            "entries": len(self._entries),
            "pixels": self._pixels,
            "budget": self._budget,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": (self._hits / total) if total else 0.0,
            "overflow": self._overflow,
        }

    def reset_stats(self) -> None:
        self._hits = self._misses = self._overflow = 0


# --------------------------------------------------------------------------
# 解释器 → 缓存
# --------------------------------------------------------------------------
_CACHES: "OrderedDict[int, Tuple[Any, ImageCache]]" = OrderedDict()
_LOCK = threading.RLock()
_PIXEL_BUDGET = DEFAULT_PIXEL_BUDGET


def _is_alive(tk) -> bool:
    """Tk 解释器是否仍然可用。"""
    try:
        tk.call("info", "exists", ".")
    except Exception:
        return False
    return True


def _prune_locked() -> None:
    """回收已销毁解释器的缓存；仍然超限时淘汰最久未用的。"""
    if len(_CACHES) <= _MAX_INTERPRETERS:
        return
    for key in [k for k, (tk, _) in _CACHES.items() if not _is_alive(tk)]:
        _CACHES.pop(key, None)
    while len(_CACHES) > _MAX_INTERPRETERS:
        _CACHES.popitem(last=False)


def _cache_for(master) -> ImageCache:
    tk = getattr(master, "tk", None)
    if tk is None:  # 传入的就是 tkapp 本身
        tk = master
    key = id(tk)
    with _LOCK:
        entry = _CACHES.get(key)
        if entry is not None and entry[0] is not tk:
            entry = None  # id 被复用，串台了
        if entry is None:
            entry = (tk, ImageCache(_PIXEL_BUDGET))
            _CACHES[key] = entry
            _CACHES.move_to_end(key)
            _prune_locked()
        else:
            _CACHES.move_to_end(key)
        return entry[1]


def get_cache(master) -> ImageCache:
    """取（必要时创建）某个 Tk 解释器对应的缓存。"""
    return _cache_for(master)


def clear_cache(master=None) -> int:
    """清空缓存。``master=None`` 时清空全部解释器。

    .. warning::
       清空后，仍然存在于画布上的 item 会因为图片被回收而变空白。
       仅在确实要重建整个界面时调用。
    """
    with _LOCK:
        if master is None:
            total = sum(cache.clear() for _, cache in _CACHES.values())
            _CACHES.clear()
            return total
        return _cache_for(master).clear()


def set_cache_budget(pixels: Optional[int]) -> None:
    """设置像素预算（``None`` 表示不限制）。应用于所有解释器。"""
    global _PIXEL_BUDGET
    with _LOCK:
        _PIXEL_BUDGET = DEFAULT_PIXEL_BUDGET if pixels is None else max(0, int(pixels))
        for _, cache in _CACHES.values():
            cache.budget = _PIXEL_BUDGET


def cache_stats(master=None) -> Dict[str, Any]:
    """缓存统计，便于性能诊断。"""
    with _LOCK:
        if master is not None:
            return _cache_for(master).stats()
        merged: Dict[str, Any] = {
            "interpreters": len(_CACHES),
            "entries": 0,
            "pixels": 0,
            "budget": _PIXEL_BUDGET,
            "hits": 0,
            "misses": 0,
            "overflow": 0,
        }
        for _, cache in _CACHES.values():
            stats = cache.stats()
            for field in ("entries", "pixels", "hits", "misses", "overflow"):
                merged[field] += stats[field]
        total = merged["hits"] + merged["misses"]
        merged["hit_rate"] = (merged["hits"] / total) if total else 0.0
        return merged
