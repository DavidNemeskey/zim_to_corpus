#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Miscellaneous utility functions."""

from argparse import ArgumentTypeError
import importlib
import inspect
import json
from typing import Any, Dict, List, Type


def parse_json(value: str, arg=None) -> Any:
    """
    A json type for argparse.

    :param value: the argument value
    :param arg: the name of the argument. If not specified, the error message
                will contain the argument value if anything goes wrong. If it
                is, by e.g. binding it with :func:`functools.partial`, the
                name of the argument is used for brevity and readability.
    :returns: the result of parsing the json string _value_.
    """
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        if arg:
            raise ArgumentTypeError(f'The value of {arg} is not valid json')
        else:
            raise ArgumentTypeError(f'"{value}" is not valid json')


def prefix_name(cls: Type) -> str:
    """
    Returns the (lower cased) prefix before _superclass_'s name; e.g.
    (``BERTConverter`` becomes ``bert``).

    .. note::
    Only takes the first superclass into account in case of multiple
    inheritence.
    """
    return cls.__name__[:cls.__name__.find(cls.__bases__[0].__name__)].lower()

def get_subclasses_of(superclass: str, module: str) -> Dict[str, Type]:
    """
    Enumerates all subclasses of _superclass_ in module _module_.

    .. note::
    This function is very specific of the layout of the classes in this package.
    It won't work in other contexts.

    :param superclass: the name of the class whose subclasses we enumerate.
    :param module: the where both _superclass_ and its subclasses are defined.
    :returns: a dictionary of {{class name: its type}}. Class name is not the
              full name of the class, but rather its (lower cased) prefix before
              _superclass_'s name; e.g. (``BERTConverter`` becomes ``bert``).
    """
    mod = importlib.import_module(module)
    scls = getattr(mod, superclass)
    return {
        prefix_name(cls): cls
        for name, cls in inspect.getmembers(mod, inspect.isclass)
        if name != superclass and issubclass(cls, scls)
    }


def instantiate(cls: str, module: str = None,
                args: List[Any] = None, kwargs: Dict[str, Any] = None) -> Any:
    """
    Instantiates a class with specified arguments.

    :param cls: the name of the class. It can be an absolute class name, with
                module names included, or just the name of the class. In the
                latter case, the ``module`` key needs to be specified as well.
    :param module: see above.
    :param args: the list of the parameters to support to the ``__init__``
                 method of the class.
    :param kwargs: another way to specify the arguments to ``__init__``.
    :return: the instantiated object.
    """
    if not module:
        module, _, cls = cls.rpartition('.')
    mod_obj = importlib.import_module(module)
    cls_obj = getattr(mod_obj, cls)
    return cls_obj(*(args or []), **(kwargs or {}))


def instantiate_json(json_dict: str) -> Any:
    """
    Instantiates an object from the JSON dictionary string. This is a wrapper
    around :func:`instantiate` and it supports (and expects) the same keys as
    the arguments of the latter function.
    """
    return instantiate(**json.loads(json_dict))


def identity(obj: Any) -> Any:
    """An identity function, to be used for a noop transformation."""
    return obj
