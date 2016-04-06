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


class Event(models.Model):
    title = models.CharField(max_length=255)
    is_free = models.NullBooleanField()

    def __str__(self):
        return self.title


class Place(models.Model):
    title = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=10, decimal_places=6, null=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=6, null=True)
    events = models.ManyToManyField("Event", through="Schedule")


class Schedule(models.Model):
    event = models.ForeignKey("Event")
    place = models.ForeignKey("Place")
    date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    finish_time = models.TimeField(null=True, blank=True)
