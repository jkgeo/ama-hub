# -*- coding: utf-8 -*-

import json
import os
import re
from autocomplete_light.registry import autodiscover

from django import forms
from django.utils.translation import ugettext as _
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from django.forms import HiddenInput, TextInput
from modeltranslation.forms import TranslationModelForm

from .models import (
    Video,
    VideoResourceLink,
    get_related_resources,
)
from geonode.maps.models import Map
from geonode.layers.models import Layer
from geonode.documents.models import Document
# from ama_hub.links.models import External_Link

autodiscover()  # flake8: noqa

from geonode.base.forms import ResourceBaseForm


class VideoFormMixin(object):

    def generate_link_choices(self, resources=None):

        if resources is None:
            resources = list(Layer.objects.all())
            resources += list(Map.objects.all())
            resources += list(Document.objects.all())
            # resources += list(External_Link.objects.all())
            resources.sort(key=lambda x: x.title)

        choices = []
        for obj in resources:
            type_id = ContentType.objects.get_for_model(obj.__class__).id
            choices.append([
                "type:%s-id:%s" % (type_id, obj.id),
                '%s (%s)' % (obj.title, obj.polymorphic_ctype.model)
            ])

        return choices

    def generate_link_values(self, resources=None):
        choices = self.generate_link_choices(resources=resources)
        return [choice[0] for choice in choices]

    def save_many2many(self, links_field='links'):
        # create and fetch desired links
        instances = []
        for link in self.cleaned_data[links_field]:
            matches = re.match("type:(\d+)-id:(\d+)", link)
            if matches:
                content_type = ContentType.objects.get(id=matches.group(1))
                instance, _ = VideoResourceLink.objects.get_or_create(
                    video=self.instance,
                    content_type=content_type,
                    object_id=matches.group(2),
                )
                instances.append(instance)

        # delete remaining links
        VideoResourceLink.objects\
        .filter(video_id=self.instance.id).exclude(pk__in=[i.pk for i in instances]).delete()


class VideoForm(ResourceBaseForm, VideoFormMixin):

    links = forms.MultipleChoiceField(
        label=_("Link to another resource (optional)"),
        required=False)

    def __init__(self, *args, **kwargs):
        super(VideoForm, self).__init__(*args, **kwargs)
        self.fields['links'].choices = self.generate_link_choices()
        self.fields['links'].initial = self.generate_link_values(
            resources=get_related_resources(self.instance)
        )

    class Meta(ResourceBaseForm.Meta):
        model = Video
        exclude = ResourceBaseForm.Meta.exclude + (
            'content_type',
            'object_id',
            'video_file',
            'extension',
            'video_type',
            'video_url')

class VideoDescriptionForm(forms.Form):
    title = forms.CharField(300)
    abstract = forms.CharField(2000, widget=forms.Textarea, required=False)
    keywords = forms.CharField(500, required=False)


class VideoReplaceForm(forms.ModelForm):

    """
    The form used to replace a video.
    """

    class Meta:
        model = Video
        fields = ['video_file', 'video_url']

    def clean(self):
        """
        Ensures the video_file or the video_url field is populated.
        """
        cleaned_data = super(VideoReplaceForm, self).clean()
        video_file = self.cleaned_data.get('video_file')
        video_url = self.cleaned_data.get('video_url')

        if not video_file and not video_url:
            raise forms.ValidationError(_("Video must be a file or url."))

        if video_file and video_url:
            raise forms.ValidationError(
                _("A video cannot have both a file and a url."))

        return cleaned_data

    def clean_video_file(self):
        """
        Ensures the video_file is valid.
        """
        video_file = self.cleaned_data.get('video_file')

        if video_file and not os.path.splitext(
                video_file.name)[1].lower()[
                1:] in settings.ALLOWED_VIDEO_TYPES:
            raise forms.ValidationError(_("This file type is not allowed"))

        return video_file


class VideoCreateForm(TranslationModelForm, VideoFormMixin):

    """
    The video upload form.
    """
    permissions = forms.CharField(
        widget=HiddenInput(
            attrs={
                'name': 'permissions',
                'id': 'permissions'}),
        required=True)

    links = forms.MultipleChoiceField(
        label=_("Link to another resource (optional)"),
        required=False)

    class Meta:
        model = Video
        fields = ['title', 'video_file', 'video_url']
        widgets = {
            'name': HiddenInput(attrs={'cols': 80, 'rows': 20}),
        }

    def __init__(self, *args, **kwargs):
        super(VideoCreateForm, self).__init__(*args, **kwargs)
        self.fields['links'].choices = self.generate_link_choices()

    def clean_permissions(self):
        """
        Ensures the JSON field is JSON.
        """
        permissions = self.cleaned_data['permissions']

        try:
            return json.loads(permissions)
        except ValueError:
            raise forms.ValidationError(_("Permissions must be valid JSON."))

    def clean(self):
        """
        Ensures the video_file or the video_url field is populated.
        """
        cleaned_data = super(VideoCreateForm, self).clean()
        video_file = self.cleaned_data.get('video_file')
        video_url = self.cleaned_data.get('video_url')


        if not video_file and not video_url:
            raise forms.ValidationError(_("Video must be a file or url."))

        if video_file and video_url:
            raise forms.ValidationError(
                _("A video cannot have both a file and a url."))

        return cleaned_data

    def clean_video_file(self):
        """
        Ensures the video_file is valid.
        """
        video_file = self.cleaned_data.get('video_file')

        if video_file and not os.path.splitext(
                video_file.name)[1].lower()[
                1:] in settings.ALLOWED_VIDEO_TYPES:
            raise forms.ValidationError(_("This file type is not allowed"))

        return video_file
