# coding: utf-8
from __future__ import unicode_literals, absolute_import
from django.db import models


class AtomEntry(models.Model):
    """
    Dummy model for testing an Atom feed.
    """
    atom_id = models.CharField(max_length=255, primary_key=True)
    title = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255)


class Thing(models.Model):
    """
    Dummy model for testing.
    """
    email = models.EmailField()
    name = models.CharField(max_length=255)
    nick = models.CharField(max_length=50)
    combined = models.TextField()
    other = models.CharField(max_length=50)
    master = models.CharField(max_length=50)

    def convert_name(self, first_name, last_name):
        return "%s %s" % (first_name, last_name)
