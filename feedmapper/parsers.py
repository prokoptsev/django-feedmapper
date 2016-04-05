# coding: utf-8
from __future__ import unicode_literals, absolute_import
import os
from datetime import datetime

from lxml import etree

from django.conf import settings
from django.core.mail import send_mail
from django.utils import six
from django.apps import apps
from django.template.loader import render_to_string

from .settings import FEEDMAPPER


class Parser(object):
    """
    Base parser class for mapping Django model fields to feed nodes.
    """

    def __init__(self, mapping):
        self.mapping = mapping
        self.nsmap = {
            "media": "http://search.yahoo.com/mrss/",
            "geo": "http://www.w3.org/2003/01/geo/wgs84_pos#",
            "georss": "http://www.georss.org/georss",
            "slash": "http://purl.org/rss/1.0/modules/slash/",
            "sy": "http://purl.org/rss/1.0/modules/syndication/",
            "dc": "http://purl.org/dc/elements/1.1/",
            "wfw": "http://wellformedweb.org/CommentAPI/",
        }
        self.data_dir = FEEDMAPPER['DATA_DIR']

    @property
    def data_source(self):
        if not self.mapping.source.startswith('/') and '://' not in self.mapping.source:
            return os.path.join(self.data_dir, self.mapping.source)
        return self.mapping.source

    def validate_model_format(self, model_string):
        """
        Validate that a model in the JSON mapping is in the format app.model.
        """
        if '.' not in model_string or model_string.count('.') > 1:
            return False
        return True

    def generate_filter_kwargs(self, filter_string):
        """
        Convert a string to kwargs that can be passed to the Django ORM's filter
        method.

        >>> Parser(None).generate_filter_kwargs('slug__icontains="darth", name="Anakin"')
        {'slug__icontains': 'darth', 'name': 'Anakin'}
        """
        filters = filter_string.replace('"', '').replace("'", '').split(',')
        filter_kwargs = dict([str(filter).strip().split('=') for filter in filters])
        return filter_kwargs

    def notify_failure(self, subject=None):
        """
        Notify recipients, if specified, of an error during parsing.
        """

        if not subject:
            subject = "django-feedmapper parsing failure notice"
        message = render_to_string('feedmapper/notify_failure.txt', {
            'mapping': self.mapping,
            'parse_attempted': self.mapping.parse_attempted,
            'parse_log': self.mapping.parse_log
        })
        recipients = self.mapping.notification_recipients.split('\r\n')
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipients)

    def parse(self):
        raise NotImplementedError("You must override the parse method in a Parser subclass.")


class XMLParser(Parser):
    """
    A parser for XML that does not follow any standard.
    """

    def __init__(self, mapping):
        super(XMLParser, self).__init__(mapping)
        self.nsmap.update({'content': "http://purl.org/rss/1.0/modules/content/"})

    def get_value(self, node, path, as_text=True):
        """
        Attempts to retrieve either the node text or node attribute specified.
        :param node:
        :param path:
        :param as_text:
        :return:
        """
        context = node
        if path.startswith("/"):
            path = path[1:]
            context = node.getroottree()

        if '@' in path:
            if path.count('@') > 1:
                raise ValueError("You have more than one attribute accessor. (e.g. foo.@bar.@baz)")
            path, attr = path.rsplit('.@')
            resolved = context.find(path, namespaces=self.nsmap).attrib.get(attr, "")
        else:
            if path == ".":
                # this will get text in an XML node, regardless of placement
                resolved = ''.join([text.strip() for text in context.xpath("text()")])
            else:
                # fixme: hacky shit; separate get_value to get_value and get_value_text
                resolved = context.findall(path, namespaces=self.nsmap)
                resolved = ((len(resolved) > 0 and resolved[0].text) or "") if as_text else resolved

        return resolved.strip() if as_text else resolved

    def join_fields(self, node, fields):
        """
        Joins the text for the specified fields.
        :param node:
        :param fields:
        :return:
        """
        values = [self.get_value(node, field) for field in fields]
        return " ".join(values)

    def parse(self):
        """
        Traverses through the XML document and parses the data, applying it to the
        model specified in the :py:class:`~feedmapper.models.Mapping`.
        """
        self.mapping.parse_attempted = datetime.now()
        try:
            tree = etree.parse(self.data_source)
            root = tree.getroot()

            model_mappings = self.mapping.data_map['models']
            purge_filter = self.mapping.data_map.get('purge_filter')
            for model_string, configuration in model_mappings.items():
                if not self.validate_model_format(model_string):
                    raise ValueError("Invalid model format in JSON mapping: %s" % model_string)
                identifier = configuration.get('identifier')

                # allow transformation of identifiers
                identifier_transformer = None
                if isinstance(identifier, dict):
                    identifier_transformer = identifier["transformer"]
                    identifier = identifier["field"]

                if not identifier and not self.mapping.purge:
                    raise UserWarning("Purging is off and the JSON mapping doesn't supply an identifier.")
                model = apps.get_model(*model_string.split('.'))
                node_path = configuration['nodePath'].replace('.', '/')
                fields = configuration['fields']
                nodes = root.xpath(node_path, namespaces=self.nsmap)

                if self.mapping.purge:
                    # remove existing items
                    existing_items = model.objects.all()
                    if purge_filter:
                        filter_kwargs = self.generate_filter_kwargs(purge_filter)
                        if filter_kwargs:
                            existing_items = existing_items.filter(**filter_kwargs)
                    existing_items.delete()

                for node in nodes:
                    if self.mapping.purge:
                        instance = model()
                    else:
                        # purge is turned off, retrieve an existing instance
                        identifier_value = node.find(identifier, namespaces=self.nsmap).text
                        if identifier_transformer:
                            identifier_value = getattr(model, identifier_transformer)(identifier_value, parser=self)

                        kwargs = {identifier: identifier_value}
                        # TODO: get_or_create
                        try:
                            instance = model.objects.get(**kwargs)
                        except model.DoesNotExist:
                            instance = model(**kwargs)

                    many_to_many = {}
                    for field, target in fields.items():

                        transformer = getattr(instance, "parse_%s" % field, None)

                        if not transformer:
                            if isinstance(target, six.string_types):
                                # maps one model field to one feed node
                                value = self.get_value(node, target)
                            elif isinstance(target, list):
                                # maps one model field to multiple feed nodes
                                value = self.join_fields(node, target)

                        if transformer or isinstance(target, dict):
                            # we may have a transformer (parse_fieldname method) or an extended definition
                            value = None
                            if 'transformer' in target:
                                # maps one model field to a transformer method
                                transformer = getattr(instance, target['transformer'])
                            elif 'default' in target and not value:
                                # maps one model field to a default value
                                value = target['default']
                            else:
                                # we've got a single field definition with an implicit transformer
                                target = {"fields": [target]}

                            if transformer:
                                transformer_args = []

                                field_is_m2m = False
                                if len(target["fields"]) == 1 and target["fields"][0].endswith("*"):
                                    # we've hit a many2many relation
                                    transformer_args = self.get_value(node, target["fields"][0][:-1], as_text=False)
                                    field_is_m2m = True

                                else:
                                    for target_field in target["fields"]:

                                        if target_field.endswith("*"):
                                            raise ValueError(u"M2m fields can only contain one target field")
                                        else:
                                            transformer_args.append(self.get_value(node, target_field))

                                if field_is_m2m:
                                    many_to_many[field] = (
                                        transformer, transformer_args, {"parser": self}
                                    )
                                    continue
                                else:
                                    try:
                                        value = transformer(*transformer_args, parser=self)
                                    except TypeError:
                                        value = transformer(*transformer_args)

                        setattr(instance, field, value)
                    instance.save()

                    # handle m2m
                    for transformer, args, kwargs in many_to_many.values():
                        transformer(*args, **kwargs)

            self.mapping.parse_succeeded = True
            self.mapping.parse_log = ""
        except etree.Error as e:
            self.mapping.parse_succeeded = False
            self.mapping.parse_log = str(e.error_log)
        except IOError as e:
            self.mapping.parse_succeeded = False
            self.mapping.parse_log = e.args[0]
        # clear the lxml error log so errors don't compound
        etree.clear_error_log()
        self.mapping.save()

        # notify the authorities if a failure occured
        if not self.mapping.parse_succeeded and self.mapping.notification_recipients:
            self.notify_failure()


class AtomParser(XMLParser):
    """
    An XML parser for the Atom standard.
    """

    def __init__(self, mapping):
        super(AtomParser, self).__init__(mapping)
        self.nsmap.update({'atom': 'http://www.w3.org/2005/Atom'})
