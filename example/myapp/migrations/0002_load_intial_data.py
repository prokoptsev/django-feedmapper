# coding: utf-8
from __future__ import unicode_literals, absolute_import
from os import path

from django.core.management import call_command
from django.db import migrations


fixture_filename = 'initial_data.json'
fixture_dir = path.abspath(path.join(
    path.dirname(path.dirname(__file__)),
    'fixtures'
))


def load_fixture(apps, schema_editor):
    fixture_file = path.join(fixture_dir, fixture_filename)
    call_command('loaddata', fixture_file)


def unload_fixture(apps, schema_editor):
    Thing = apps.get_model("myapp", "Thing")
    Thing.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ('myapp', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(load_fixture, reverse_code=unload_fixture),
    ]
