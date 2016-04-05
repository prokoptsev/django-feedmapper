# coding: utf-8
from __future__ import unicode_literals

from django.db import migrations, models
import jsonfield.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Mapping',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(help_text='Label for your reference', max_length=255, verbose_name='label')),
                ('source', models.CharField(help_text='The source feed for your data', max_length=255, verbose_name='source')),
                ('parser', models.CharField(choices=[('feedmapper.parsers.AtomParser', 'Atom'), ('feedmapper.parsers.XMLParser', 'XML')], help_text='Which parser to use when synchronizing', max_length=255, verbose_name='parser')),
                ('purge', models.BooleanField(default=False, help_text='Purge existing items on sync?', verbose_name='purge')),
                ('data_map', jsonfield.fields.JSONField(verbose_name='data map')),
                ('notification_recipients', models.TextField(blank=True, help_text='Specify one email address per line to be notified of parsing errors.', verbose_name='notification recipients')),
                ('parse_attempted', models.DateTimeField(blank=True, null=True, verbose_name='parse attempted')),
                ('parse_succeeded', models.BooleanField(default=False, verbose_name='parse succeeded')),
                ('parse_log', models.TextField(blank=True, verbose_name='parse log')),
            ],
        ),
    ]
