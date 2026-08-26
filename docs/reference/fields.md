# Field Reference

How each Django field is converted into a Pydantic annotation.

## Scalar fields

| Django field | Python type | Notes |
| --- | --- | --- |
| `CharField` | `str` | `max_length` becomes a `MaxLen` constraint |
| `TextField` | `str` | |
| `SlugField` | `str` | |
| `FileField`, `FilePathField` | `str` | A `FieldFile` serializes to its `.url` |
| `EmailField` | `EmailStr` | Requires `pydantic[email]` |
| `URLField` | `AnyUrl` | |
| `UUIDField` | `UUID` | |
| `AutoField`, `IntegerField`, `SmallIntegerField`, `BigIntegerField`, `PositiveIntegerField`, `PositiveSmallIntegerField` | `int` | |
| `FloatField` | `float` | |
| `DecimalField` | `Decimal` | |
| `BooleanField`, `NullBooleanField` | `bool` | |
| `DateTimeField` | `datetime.datetime` | |
| `DateField` | `datetime.date` | |
| `TimeField` | `datetime.time` | |
| `DurationField` | `datetime.timedelta` | |
| `BinaryField` | `bytes` | |
| `IPAddressField`, `GenericIPAddressField` | `IPvAnyAddress` | |
| `JSONField` | `Json` | Django 3.2+ |
| Any field with `choices` | Generated `Enum` | See [Django Choices](../guides/choices.md) |

### PostgreSQL fields

| Django field | Python type |
| --- | --- |
| `ArrayField` | `list[<base field type>]` |
| `HStoreField` | `Json` |
| `JSONField` (`django.contrib.postgres`) | `Json` |
| `RangeField` | `list[<base field type>]` |

### Verified against a real model

```python title="models.py"
--8<-- "examples/models.py:speaker-profile"
```

`type_name` below only shortens the display: Python 3.14 renders `Optional[int]`
as `int | None`, so printing the annotation raw would read differently depending on
the interpreter. The annotation objects themselves are the same on every version.

```pycon
>>> from typing import get_args
>>> def type_name(annotation):
...     args = get_args(annotation)
...     if type(None) in args:
...         inner = ', '.join(type_name(arg) for arg in args if arg is not type(None))
...         return f'Optional[{inner}]'
...     return getattr(annotation, '__name__', str(annotation))
>>> class SpeakerProfileSchema(ModelSchema):
...     class Config:
...         model = models.SpeakerProfile
>>> for name, info in SpeakerProfileSchema.model_fields.items():
...     print(f'{name:16} {type_name(info.annotation)}')
id               Optional[int]
uuid             UUID
full_name        str
biography        Optional[str]
slug             str
email            EmailStr
website          AnyUrl
talks_given      int
rating           Optional[float]
fee              Optional[Decimal]
is_active        bool
joined_at        Optional[datetime]
birth_date       Optional[date]
preferred_slot   Optional[time]
session_length   Optional[timedelta]
last_login_ip    Optional[IPvAnyAddress]
metadata         Optional[Json]

```

## Relation fields

| Django field | `depth = 0` | `depth ≥ 1` |
| --- | --- | --- |
| `ForeignKey`, `OneToOneField` | `int` (related pk), alias `<name>_id` | Nested schema |
| `ManyToManyField` | `list[int]` of related pks | `list[NestedSchema]` |
| `OneToOneRel` (reverse) | `int` | Nested schema |
| `ManyToOneRel` (reverse FK) | Not generated | Not generated |
| `ManyToManyRel` (reverse M2M) | Not generated | Not generated |

Reverse `ForeignKey` and reverse `ManyToMany` are skipped when fields are
collected, so a schema never silently acquires a field that triggers a query.
Declare them with [`Source`](../guides/source.md#collections).

!!! note "Relations are written through `<name>_id`"

    `create()` and `update()` detect relation fields and hand the ORM the
    `<name>_id` attribute, which is the form Django accepts for a primary key.
    Many-to-many values are applied after the instance is saved, since they need
    a pk to attach to.

    ```pycon
    >>> class EventSchema(ModelSchema):
    ...     class Config:
    ...         model = models.Event
    >>> category = models.Category.objects.create(name='Python')
    >>> EventSchema.model_validate({'title': 'DjangoCon', 'category': category.pk}).create().category_id
    1

    ```

!!! note "Relations are read as the related primary key"

    A relation field accepts either the related instance or its primary key, so
    reading a Django object and accepting a pk from a JSON payload both work:

    ```pycon
    >>> EventSchema.model_validate({'title': 'DjangoCon', 'category': category}).category
    1
    >>> EventSchema.model_validate({'title': 'DjangoCon', 'category': category.pk}).category
    1

    ```

## What makes a field optional

Three independent rules can relax a generated field. Any one of them is enough.

| Rule | Effect |
| --- | --- |
| `null=True` on the Django field | Type becomes `Optional[...]`, default `None` |
| `blank=True` on the Django field | Type becomes `Optional[...]`, default `None` |
| Listed in `Config.optional` | Type becomes `Optional[...]`, default `None` |
| Is the primary key | Relaxed unless named in `fields` — see [the pk rule](../guides/model-schema.md#the-primary-key-rule) |

`blank=True` is worth calling out: it is a *form-level* flag in Django, not a
database one, but it does relax the schema field.

```pycon
>>> SpeakerProfileSchema.model_fields['biography'].is_required()   # blank=True
False
>>> SpeakerProfileSchema.model_fields['rating'].is_required()      # null=True
False
>>> SpeakerProfileSchema.model_fields['full_name'].is_required()   # neither
True

```

## Defaults

A Django `default` becomes the Pydantic default. A callable default becomes a
`default_factory`.

```pycon
>>> SpeakerProfileSchema.model_fields['talks_given'].default
0
>>> SpeakerProfileSchema.model_fields['is_active'].default
True

```

## Metadata carried across

`verbose_name` becomes the field title, `help_text` (falling back to
`verbose_name`) becomes the description, and `max_length` becomes a constraint:

```pycon
>>> info = SpeakerProfileSchema.model_fields['full_name']
>>> info.title
'Full Name'
>>> info.metadata
[MaxLen(max_length=120)]

```

All three surface in the JSON Schema:

```pycon
>>> print(json.dumps(SpeakerProfileSchema.model_json_schema()['properties']['full_name'], indent=2))
{
  "description": "",
  "maxLength": 120,
  "title": "Full Name",
  "type": "string"
}

```

!!! note "`max_length` is dropped for custom types"

    Fields converted to a non-`str` Pydantic type — `EmailStr`, `AnyUrl`, and
    any `choices` enum — do not carry `max_length`, because the constraint does
    not apply to the converted type.

    ```pycon
    >>> SpeakerProfileSchema.model_fields['email'].metadata
    []

    ```

## Unsupported fields

A field with no registered converter raises at class-creation time rather than
producing a silently wrong schema:

```text
Exception: Don't know how to convert the Django field <field> (<class>)
```

Handle it by excluding the field, or by
[declaring the annotation yourself](../guides/model-schema.md#overriding-a-generated-field).

## Related pages

- [Django Choices](../guides/choices.md) — enum generation in detail
- [Relations](../guides/relations.md) — relation fields and `depth`
- [ModelSchema configuration](configuration.md) — every `Config` option
