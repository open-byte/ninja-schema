"""Guards the reading of class-body annotations across the PEP 649 boundary.

Python 3.14 stopped evaluating class annotations when the body runs: the metaclass
receives an `__annotate_func__` to call instead of a ready `__annotations__` dict.
Reading the namespace directly silently returned nothing there, so every field a
schema *declared* — `Source`, `MethodSource`, custom overrides — was dropped.
"""

import sys
import typing as t

import pytest
from tests.models import Event

from django_modern_schemas import MethodSource, ModelSchema, Source
from django_modern_schemas.pydanticutils import get_namespace_annotations


class TestGetNamespaceAnnotations:
    def test_reads_the_annotations_a_class_body_declared(self):
        seen = {}

        class Capture(type):
            def __new__(mcs, name, bases, namespace, **kwargs):
                seen.update(get_namespace_annotations(namespace))
                return super().__new__(mcs, name, bases, namespace, **kwargs)

        class Declared(metaclass=Capture):
            title: str
            tags: list[int]
            untyped = 1

        assert seen == {'title': str, 'tags': list[int]}

    def test_an_unannotated_body_has_no_annotations(self):
        seen = []

        class Capture(type):
            def __new__(mcs, name, bases, namespace, **kwargs):
                seen.append(get_namespace_annotations(namespace))
                return super().__new__(mcs, name, bases, namespace, **kwargs)

        class Bare(metaclass=Capture):
            pass

        assert seen == [{}]

    def test_prefers_an_already_evaluated_dict(self):
        # `from __future__ import annotations` fills `__annotations__` eagerly with
        # strings on every version, and PEP 649 leaves that dict in place.
        assert get_namespace_annotations({'__annotations__': {'title': 'str'}}) == {'title': 'str'}

    def test_returns_a_dict_the_caller_owns(self):
        namespace = {'__annotations__': {'title': str}}

        get_namespace_annotations(namespace).pop('title')

        assert namespace['__annotations__'] == {'title': str}


class TestSchemaAnnotations:
    def test_declared_fields_survive_lazy_annotations(self):
        class EventDeclaredSchema(ModelSchema):
            category_name: t.Annotated[str, Source('category.name')]
            display_title: t.Annotated[str, MethodSource('display_title')]

            class Config:
                model = Event
                fields = ['title']

        assert list(EventDeclaredSchema.model_fields) == ['title', 'category_name', 'display_title']

    def test_the_class_reports_the_computed_annotations(self):
        class EventComputedSchema(ModelSchema):
            category_name: t.Annotated[str, Source('category.name')]

            class Config:
                model = Event
                fields = ['title']

        assert set(EventComputedSchema.__annotations__) == {'title', 'category_name'}

    @pytest.mark.skipif(sys.version_info < (3, 14), reason='PEP 649 lazy annotations land in 3.14')
    def test_the_class_body_annotate_function_no_longer_answers(self):
        # The metaclass replaces the declared annotations with the ones it computed. A
        # surviving `__annotate_func__` would keep answering STRING requests with the
        # original, much smaller, set.
        from annotationlib import Format, get_annotations

        class EventStringSchema(ModelSchema):
            category_name: t.Annotated[str, Source('category.name')]

            class Config:
                model = Event
                fields = ['title']

        assert set(get_annotations(EventStringSchema, format=Format.STRING)) == {'title', 'category_name'}
