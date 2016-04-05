# coding: utf-8
from __future__ import unicode_literals, absolute_import
import os
from datetime import datetime

from lxml import etree

from django.utils import six
from django.apps import apps

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

    def parse(self):
        raise NotImplementedError("You must override the parse method in a Parser subclass.")


class XMLParser(Parser):
    """
    A parser for XML that does not follow any standard.
    """

    def __init__(self, mapping):
        super(XMLParser, self).__init__(mapping)
        self.nsmap.update({'content': "http://purl.org/rss/1.0/modules/content/"})

    def get_value(self, node, path):
        """
        Attempts to retrieve either the node text or node attribute specified.
        :param node:
        :param path:
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
            if path:
                resolved = context.find(path, namespaces=self.nsmap)
                if resolved is not None:
                    resolved = resolved.attrib.get(attr, "")
            else:
                resolved = context.attrib.get(attr, "")
        else:
            if path == ".":
                # this will get text in an XML node, regardless of placement
                resolved = ''.join([text.strip() for text in context.xpath("text()")])
            else:
                # fixme: hacky shit; separate get_value to get_value and get_value_text
                resolved = context.findall(path, namespaces=self.nsmap)
                resolved = ((len(resolved) > 0 and resolved[0].text) or "")

        return resolved.strip() if resolved is not None else None

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
                    instance = model()
                    if not self.mapping.purge:
                        # purge is turned off, retrieve an existing instance
                        identifier_value = node.find(identifier, namespaces=self.nsmap).text
                        if identifier_transformer:
                            identifier_value = getattr(model, identifier_transformer)(identifier_value, parser=self)

                        kwargs = {identifier: identifier_value}
                        instance, created = model.objects.get_or_create(**kwargs)

                    for field, target in fields.items():
                        value = None
                        transformer = None
                        transformer_args = []

                        if isinstance(target, six.string_types):
                            # maps one model field to one feed node
                            value = self.get_value(node, target)
                        elif isinstance(target, list):
                            # maps one model field to multiple feed nodes
                            value = self.join_fields(node, target)
                        elif isinstance(target, dict):
                            if 'field' in target:
                                value = self.get_value(node, target['field'])

                            if 'transformer' in target:
                                # maps one model field to a transformer method
                                transformer = getattr(instance, target['transformer'])
                                if value:
                                    transformer_args = [value]
                                elif 'fields' in target:
                                    for target_field in target['fields']:
                                        transformer_args.append(self.get_value(node, target_field))

                            if 'default' in target and not (value or transformer):
                                # maps one model field to a default value
                                value = target['default']

                            if transformer:
                                value = transformer(*transformer_args)
                        setattr(instance, field, value)

                    instance.save()

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
