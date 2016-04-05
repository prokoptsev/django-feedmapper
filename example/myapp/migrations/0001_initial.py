# coding: utf-8
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Thing',
            fields=[
                ('atom_id', models.CharField(max_length=255, primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=255)),
                ('link', models.URLField(blank=True, null=True)),
                ('summary', models.TextField()),
                ('content', models.TextField()),
            ],
        ),
    ]
