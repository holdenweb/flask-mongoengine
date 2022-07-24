"""Extended version of :mod:`mongoengine.document`."""
import logging
from typing import List, Optional, Type, Union

import mongoengine
from flask import abort
from mongoengine.errors import DoesNotExist
from mongoengine.queryset import QuerySet

from flask_mongoengine.decorators import wtf_required
from flask_mongoengine.pagination import ListFieldPagination, Pagination

try:
    from flask_mongoengine.wtf.models import ModelForm
except ImportError:  # pragma: no cover
    ModelForm = None
logger = logging.getLogger("flask_mongoengine")


class BaseQuerySet(QuerySet):
    """Extends :class:`~mongoengine.queryset.QuerySet` class with handly methods."""

    def _abort_404(self, _message_404):
        """Returns 404 error with message, if message provided.

        :param _message_404: Message for 404 comment
        """
        abort(404, _message_404) if _message_404 else abort(404)

    def get_or_404(self, *args, _message_404=None, **kwargs):
        """Get a document and raise a 404 Not Found error if it doesn't exist.

        :param _message_404: Message for 404 comment, not forwarded to
            :func:`~mongoengine.queryset.QuerySet.get`
        :param args: args list, silently forwarded to
            :func:`~mongoengine.queryset.QuerySet.get`
        :param kwargs: keywords arguments, silently forwarded to
            :func:`~mongoengine.queryset.QuerySet.get`
        """
        try:
            return self.get(*args, **kwargs)
        except DoesNotExist:
            self._abort_404(_message_404)

    def first_or_404(self, _message_404=None):
        """
        Same as :func:`~BaseQuerySet.get_or_404`, but uses
        :func:`~mongoengine.queryset.QuerySet.first`, not
        :func:`~mongoengine.queryset.QuerySet.get`.

        :param _message_404: Message for 404 comment, not forwarded to
            :func:`~mongoengine.queryset.QuerySet.get`
        """
        return self.first() or self._abort_404(_message_404)

    def paginate(self, page, per_page):
        """
        Paginate the QuerySet with a certain number of docs per page
        and return docs for a given page.
        """
        return Pagination(self, page, per_page)

    def paginate_field(self, field_name, doc_id, page, per_page, total=None):
        """
        Paginate items within a list field from one document in the
        QuerySet.
        """
        # TODO this doesn't sound useful at all - remove in next release?
        item = self.get(id=doc_id)
        count = getattr(item, f"{field_name}_count", "")
        total = total or count or len(getattr(item, field_name))
        return ListFieldPagination(
            self, doc_id, field_name, page, per_page, total=total
        )


class WtfFormMixin:
    """Special mixin, for form generation functions."""

    @classmethod
    def _get_fields_names(
        cls: Union["WtfFormMixin", mongoengine.document.BaseDocument],
        only: Optional[List[str]],
        exclude: Optional[List[str]],
    ):
        """
        Filter fields names for further form generation.

        :param only:
            An optional iterable with the property names that should be included in
            the form. Only these properties will have fields.
            Fields are always appear in provided order, this allows user to change form
            fields ordering, without changing database model.
        :param exclude:
            An optional iterable with the property names that should be excluded
            from the form. All other properties will have fields.
            Fields are appears in order, defined in model, excluding provided fields
            names. For adjusting fields ordering, use :attr:`only`.
        """
        field_names = cls._fields_ordered

        if only:
            field_names = [field for field in only if field in field_names]
        elif exclude:
            field_names = [field for field in field_names if field not in exclude]

        return field_names

    @classmethod
    @wtf_required
    def to_wtf_form(
        cls: Union["WtfFormMixin", mongoengine.document.BaseDocument],
        base_class: Type[ModelForm] = ModelForm,
        only: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        field_args=None,
    ) -> Type[ModelForm]:
        """
        Generate WTForm from Document model.

        :param base_class:
            Base form class to extend from. Must be a :class:`.ModelForm` subclass.
        :param only:
            An optional iterable with the property names that should be included in
            the form. Only these properties will have fields.
            Fields are always appear in provided order, this allows user to change form
            fields ordering, without changing database model.
        :param exclude:
            An optional iterable with the property names that should be excluded
            from the form. All other properties will have fields.
            Fields are appears in order, defined in model, excluding provided fields
            names. For adjusting fields ordering, use :attr:`only`.
        :param field_args:
            An optional dictionary of field names mapping to keyword arguments used
            to construct each field object.
        """
        form_fields_dict = {}
        fields_names = cls._get_fields_names(only, exclude)

        for field_name in fields_names:
            # noinspection PyUnresolvedReferences
            field_class = cls._fields[field_name]
            try:
                form_fields_dict[field_name] = field_class.to_wtf_field(
                    field_args.get(field_name)
                )
            except AttributeError:
                logger.warning(
                    f"Field {field_name} ignored, field type does not have "
                    f".to_wtf_field() method."
                )

        form_fields_dict["model_class"] = cls
        # noinspection PyTypeChecker
        return type(f"{cls.__name__}Form", (base_class,), form_fields_dict)


class Document(WtfFormMixin, mongoengine.Document):
    """Abstract Document with QuerySet and WTForms extra helpers."""

    meta = {"abstract": True, "queryset_class": BaseQuerySet}

    def paginate_field(self, field_name, page, per_page, total=None):
        """Paginate items within a list field."""
        # TODO this doesn't sound useful at all - remove in next release?
        count = getattr(self, f"{field_name}_count", "")
        total = total or count or len(getattr(self, field_name))
        return ListFieldPagination(
            self.__class__.objects, self.pk, field_name, page, per_page, total=total
        )


class DynamicDocument(WtfFormMixin, mongoengine.DynamicDocument):
    """Abstract DynamicDocument with QuerySet and WTForms extra helpers."""

    meta = {"abstract": True, "queryset_class": BaseQuerySet}


class EmbeddedDocument(WtfFormMixin, mongoengine.EmbeddedDocument):
    """Abstract EmbeddedDocument document with extra WTForms helpers."""

    meta = {"abstract": True}


class DynamicEmbeddedDocument(WtfFormMixin, mongoengine.DynamicEmbeddedDocument):
    """Abstract DynamicEmbeddedDocument document with extra WTForms helpers."""

    meta = {"abstract": True}
