# -*- coding: utf-8 -*-

from django.contrib import admin
from geonode.base.admin import MediaTranslationAdmin, ResourceBaseAdminForm
from geonode.base.admin import metadata_batch_edit
from .models import Video

class VideoAdminForm(ResourceBaseAdminForm):

    class Meta:
        model = Video
        fields = '__all__'
        exclude = (
            'resource',
        )


class VideoAdmin(MediaTranslationAdmin):
    list_display = ('id',
                    'title',
                    'date',
                    'category',
                    'group',
                    'is_approved',
                    'is_published',
                    'metadata_completeness')
    list_display_links = ('id',)
    list_editable = ('title', 'category', 'group', 'is_approved', 'is_published')
    list_filter = ('date', 'date_type', 'restriction_code_type', 'category',
                   'group', 'is_approved', 'is_published',)
    search_fields = ('title', 'abstract', 'purpose',
                     'is_approved', 'is_published',)
    date_hierarchy = 'date'
    form = VideoAdminForm
    actions = [metadata_batch_edit]


admin.site.register(Video, VideoAdmin)
