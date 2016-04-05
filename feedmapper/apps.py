# coding: utf-8
from __future__ import unicode_literals, absolute_import

from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


class DebugToolbarConfig(AppConfig):
    name = 'feedmapper'
    verbose_name = _("Feedmapper")
