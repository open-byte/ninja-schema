import logging
import sys
import warnings
from typing import TYPE_CHECKING, Any

from pydantic.version import VERSION as _PYDANTIC_VERSION

from ..errors import ConfigError

if TYPE_CHECKING:
    from pydantic.typing import DictStrAny

__all__ = ['PYDANTIC_VERSION', 'compute_field_annotations', 'get_namespace_annotations']

logger = logging.getLogger()

PYDANTIC_VERSION = list(map(int, _PYDANTIC_VERSION.split('.')))[:2]


if sys.version_info >= (3, 14):

    def get_namespace_annotations(namespace: 'DictStrAny') -> 'DictStrAny':
        """Returns the annotations a class body declared, as a dict we own.

        PEP 649 stopped evaluating class annotations eagerly, so from 3.14 on a
        metaclass no longer finds `__annotations__` in the namespace: it finds an
        `__annotate_func__` that has to be called. `annotationlib` is the supported
        way to call it, and `FORWARDREF` keeps names that are not defined yet as
        `ForwardRef`s instead of raising, so a schema may reference a type declared
        further down the module.
        """
        # `from __future__ import annotations` still fills `__annotations__` eagerly
        # (with strings), and takes precedence when both are present.
        if '__annotations__' in namespace:
            return dict(namespace['__annotations__'])

        from annotationlib import Format, call_annotate_function, get_annotate_from_class_namespace

        annotate = get_annotate_from_class_namespace(namespace)
        if annotate is None:
            return {}
        return call_annotate_function(annotate, format=Format.FORWARDREF)

else:

    def get_namespace_annotations(namespace: 'DictStrAny') -> 'DictStrAny':
        """Returns the annotations a class body declared, as a dict we own.

        Before 3.14 the class body evaluates its annotations on the spot, so they are
        already sitting in the namespace. The copy keeps callers free to consume it.
        """
        return dict(namespace.get('__annotations__', {}))


def is_valid_field_name(name: str) -> bool:
    return not name.startswith('_')


def compute_field_annotations(namespace: 'DictStrAny', **field_definitions: Any) -> 'DictStrAny':
    fields = {}
    annotations = {}

    for f_name, f_def in field_definitions.items():
        if not is_valid_field_name(f_name):  # pragma: no cover
            warnings.warn(
                f'fields may not start with an underscore, ignoring "{f_name}"',
                RuntimeWarning,
                stacklevel=1,
            )
        if isinstance(f_def, tuple):
            try:
                f_annotation, f_value = f_def
            except ValueError as e:  # pragma: no cover
                raise ConfigError(
                    'field definitions should either be a tuple of (<type>, <default>) or just a '
                    'default value, unfortunately this means tuples as '
                    'default values are not allowed'
                ) from e
        else:
            f_annotation, f_value = None, f_def

        if f_annotation:
            annotations[f_name] = f_annotation
        fields[f_name] = f_value

    # On 3.14+ the class body left behind an `__annotate_func__` describing what the
    # *source* declared. We are replacing that with the fields we just computed, so the
    # stale function has to go: `__annotations__` wins for VALUE and FORWARDREF, but a
    # surviving `__annotate_func__` would still answer STRING requests with the old set.
    namespace.pop('__annotate_func__', None)
    namespace.update(__annotations__=annotations)
    namespace.update(fields)

    return namespace
