from django.contrib import admin

from .models import Mapping
from .tasks import feedmapper_sync


def run_mapping(modeladmin, request, queryset):
    """
    Initiates the `benchmarking` (TODO: ref required) of the selected epubs.
    """
    for mapping in queryset.all():
        feedmapper_sync.delay(mapping.id)


run_mapping.short_description = "Run selected mappings"


class MappingAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Mapping details", {
            'fields': ('label', 'source', 'parser', 'purge', 'data_map')
        }),
        ("Parsing results", {
            'fields': ('notification_recipients', 'parse_attempted',
                       'parse_succeeded', 'parse_log')
        })
    )
    list_display = ('label', 'parser', 'purge', 'parse_attempted', 'parse_succeeded')
    list_filter = ('parser', 'parse_succeeded')
    readonly_fields = ('parse_log',)

    actions = [run_mapping]

admin.site.register(Mapping, MappingAdmin)
