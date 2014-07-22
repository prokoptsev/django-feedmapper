import os
from datetime import datetime
from lxml import etree

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import get_model
from django.template.loader import render_to_string

from .settings import FEEDMAPPER


class Parser(object):
    "Base parser class for mapping Django model fields to feed nodes."

    def __init__(self, mapping):
        self.mapping = mapping
        self.nsmap = {}
        self.data_dir = FEEDMAPPER['DATA_DIR']

    @property
    def data_source(self):
        if not self.mapping.source.startswith('/') and not '://' in self.mapping.source:
            return os.path.join(self.data_dir, self.mapping.source)
        return self.mapping.source

    def validate_model_format(self, model_string):
        "Validate that a model in the JSON mapping is in the format app.model."
        if not '.' in model_string or model_string.count('.') > 1:
            return False
        return True

    def generate_filter_kwargs(self, filter_string):
        """
        Convert a string to kwargs that can be passed to the Django ORM's filter
        method. For example, 'slug__icontains="darth", name="Anakin"' will get
        converted to {'slug__icontains': 'darth', 'name': 'Anakin'}.
        """
        filters = filter_string.replace('"', '').replace("'", '').split(',')
        filter_kwargs = dict([str(filter).strip().split('=') for filter in filters])
        return filter_kwargs

    def notify_failure(self, subject=None):
        "Notify recipients, if specified, of an error during parsing."
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
    "A parser for XML that does not follow any standard."

    def get_value(self, node, path, as_text=True):
        "Attempts to retrieve either the node text or node attribute specified."
        if '@' in path:
            if path.count('@') > 1:
                raise ValueError("You have more than one attribute accessor. (e.g. foo.@bar.@baz)")
            path, attr = path.rsplit('.@')
            resolved = node.find(path, namespaces=self.nsmap).attrib.get(attr, "")
        else:
            if path == ".":
                # this will get text in an XML node, regardless of placement
                resolved = ''.join([text.strip() for text in node.xpath("text()")])
            else:
		#fixme: hacky shit; separate get_value to get_value and get_value_text
                resolved = node.findall(path, namespaces=self.nsmap)
		resolved = ((len(resolved) > 0 and resolved[0].text) or "") if as_text else resolved

        return resolved.strip() if as_text else resolved

    def join_fields(self, node, fields):
        "Joins the text for the specified fields."
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
                if not identifier and not self.mapping.purge:
                    raise UserWarning("Purging is off and the JSON mapping doesn't supply an identifier.")
                model = get_model(*model_string.split('.'))
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

			kwargs = {identifier: identifier_value}
			new = False
			try:
                    	    instance = model.objects.get(**kwargs)
			except model.DoesNotExist:
			    instance = model(**kwargs)
			    new = True

		    many_to_many = {}
                    for field, target in fields.items():
                        #if field != identifier:
                        if isinstance(target, basestring):
                            # maps one model field to one feed node
                            value = self.get_value(node, target)
                        elif isinstance(target, list):
                            # maps one model field to multiple feed nodes
                            value = self.join_fields(node, target)
                        elif isinstance(target, dict):
                            value = None
                            if 'transformer' in target:
                                # maps one model field to a transformer method
                                transformer = getattr(instance, target['transformer'])

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

                                value = transformer(*transformer_args)

				if field_is_m2m:
				    many_to_many[field] = value
				    continue

                            if 'default' in target and not value:
                                # maps one model field to a default value
                                value = target['default']
                        setattr(instance, field, value)
                    instance.save()

		    # handle m2m
		    for field, values in many_to_many.iteritems():
			instance_field = getattr(instance, field)
			old_m2ms = instance_field.all()

			# remove not anymore existing m2ms
			for old_m2m_value in old_m2ms:
			    if not old_m2m_value in values:
				instance_field.remove(old_m2m_value)

			# add new m2ms
			for value in values:
			    if not value in old_m2ms:
				instance_field.add(value)
		    

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
    "An XML parser for the Atom standard."

    def __init__(self, mapping):
        super(AtomParser, self).__init__(mapping)
        self.nsmap = {'atom': 'http://www.w3.org/2005/Atom'}