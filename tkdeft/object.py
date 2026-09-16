"""``DObject``：一个极简的"配置容器"。

tkdeft / tkfluent 里的控件大多需要一堆可读写的配置项（文本、配色、状态、
回调……）。``DObject`` 把它们统一放在 :attr:`attributes` 这个
:class:`easydict.EasyDict` 里，于是既能 ``obj.attributes.text``
按属性访问，也能 ``obj.dcget("text")`` 按名字取值。

用法
----
::

    class MyWidget(DObject):
        attributes = EasyDict({"text": "", "state": "normal"})

    widget = MyWidget()
    widget.dconfigure(text="你好")     # 批量写
    widget.dcget("text")              # -> "你好"
    widget.dcget("missing")           # -> None
    widget.dcget("missing", "默认")    # -> "默认"

设计约定
--------
* :attr:`attributes` 在**类**上给出默认值；:meth:`dconfigure` /
  :meth:`dcget` 会在首次使用时把它复制到实例上，避免两个实例互相串改。
  （子类在 ``_init`` 里直接 ``self.attributes = EasyDict({...})`` 也是允许的，
  这是 tkfluent 各组件一直以来的写法。）
* :meth:`dconfigure` **只认已知的键**，多余的键会被忽略：
  这样上层可以放心地传入"这个版本还不支持"的参数而不会崩。
* :meth:`dcget` 永远不会抛 ``KeyError``，缺键返回 ``None``（或调用方给的默认值）。
"""

from __future__ import annotations

from typing import Any, Iterable, Iterator

from easydict import EasyDict

__all__ = ["DObject"]


class DObject(object):
    """带属性字典的轻量基类。

    :cvar attributes: 配置项的默认值（类级）。实例第一次写/读时会拿到一份
        自己的副本，因此实例之间互不影响。
    """

    attributes = EasyDict({"class": "DObject"})

    # ------------------------------------------------------------------
    # 内部：保证实例有自己的属性字典
    # ------------------------------------------------------------------
    def _own_attributes(self) -> "EasyDict":
        """返回实例自己的属性字典（必要时从类默认值复制一份）。

        旧实现里 :attr:`attributes` 只有类级那一个字典，任何实例
        ``dconfigure()`` 都是往"所有实例共享"的字典里写。
        组件都会在 ``_init`` 里重新赋值，所以问题被掩盖了；
        直接使用 ``DObject`` 时就会出现"改一个、全变样"。
        """
        store = self.__dict__.get("attributes")
        if store is None:
            store = EasyDict(dict(type(self).attributes))
            self.__dict__["attributes"] = store
        return store

    # ------------------------------------------------------------------
    # 读
    # ------------------------------------------------------------------
    def dcget(self, key: str, default: Any = None) -> Any:
        """取一个配置项。

        :param key: 配置项名字
        :param default: 配置项不存在时返回什么（默认 ``None``）
        :returns: 配置项的值，或 ``default``

        与 ``self.attributes[key]`` 的区别：这里**不会**抛 ``KeyError``。
        """
        attributes = self._own_attributes()
        return attributes[key] if key in attributes else default

    #: :meth:`dcget` 的别名
    dget = dcget

    def dhas(self, key: str) -> bool:
        """是否存在某个配置项。"""
        return key in self._own_attributes()

    def dkeys(self) -> Iterable[str]:
        """所有配置项的名字。"""
        return self._own_attributes().keys()

    def dvalues(self) -> Iterable[Any]:
        """所有配置项的值。"""
        return self._own_attributes().values()

    def ditems(self) -> Iterable[tuple]:
        """``(名字, 值)`` 序列。"""
        return self._own_attributes().items()

    # ------------------------------------------------------------------
    # 写
    # ------------------------------------------------------------------
    def dconfigure(self, *args, **kwargs) -> "DObject":
        """批量写入配置项，只更新**已知**的键。

        :param args: 可选的映射（``dict`` / ``EasyDict``）
        :param kwargs: 要写入的配置项
        :returns: ``self``，支持链式调用：``obj.dconfigure(a=1).dconfigure(b=2)``

        不在 :attr:`attributes` 里的键会被安静地忽略——这是刻意的：
        组件常把"一整份主题字典"直接丢进来，其中难免有当前版本用不到的字段。
        """
        attributes = self._own_attributes()
        for source in args:
            if source is None:
                continue
            for key, value in dict(source).items():
                if key in attributes:
                    attributes[key] = value
        for key, value in kwargs.items():
            if key in attributes:
                attributes[key] = value
        return self

    #: :meth:`dconfigure` 的历史缩写
    dconfig = dconfigure

    def dupdate(self, mapping=None, **kwargs) -> "DObject":
        """与 :meth:`dconfigure` 相同，但语义是"合并一份字典"。

        :param mapping: 要合并进来的映射，可以为 ``None``
        :param kwargs: 额外的配置项
        :returns: ``self``
        """
        return self.dconfigure(mapping, **kwargs)

    def dcopy(self) -> "EasyDict":
        """把当前配置复制一份普通 ``EasyDict``（改它不会影响本对象）。"""
        return EasyDict(dict(self._own_attributes()))

    def dreset(self) -> "DObject":
        """把配置重置回类默认值。"""
        self.__dict__["attributes"] = EasyDict(dict(type(self).attributes))
        return self

    # ------------------------------------------------------------------
    # 协议
    # ------------------------------------------------------------------
    def __contains__(self, key: str) -> bool:
        return key in self._own_attributes()

    def __iter__(self) -> Iterator[str]:
        return iter(self._own_attributes())

    def __len__(self) -> int:
        return len(self._own_attributes())

    def __repr__(self) -> str:  # pragma: no cover - 调试友好
        return f"<{type(self).__name__} {dict(self._own_attributes())!r}>"
