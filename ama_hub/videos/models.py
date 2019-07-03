# -*- coding: utf-8 -*-

from __future__ import unicode_literals
import logging
import os
import uuid
from urlparse import urlparse

from django.db import models
from django.db.models import signals
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.core.urlresolvers import reverse
from django.contrib.staticfiles import finders
from django.utils.translation import ugettext_lazy as _

from geonode.layers.models import Layer
from geonode.base.models import ResourceBase, resourcebase_post_save, Link
from geonode.maps.signals import map_changed_signal
from geonode.maps.models import Map
from geonode.security.utils import remove_object_permissions

from .enumerations import VIDEO_TYPE_MAP, VIDEO_MIMETYPE_MAP

IMGTYPES = ['jpg', 'jpeg', 'tif', 'tiff', 'png', 'gif']

logger = logging.getLogger(__name__)


class Video(ResourceBase):

    """
    
    """
    #
    video_file = models.FileField(upload_to='videos',
                                null=True,
                                blank=True,
                                max_length=255,
                                verbose_name=_('Video File'))

    extension = models.CharField(max_length=128, blank=True, null=True)

    video_type = models.CharField(max_length=128, blank=True, null=True)

    video_url = models.URLField(
        blank=True,
        null=True,
        max_length=255,
        help_text=_('The URL of the video.'),
        verbose_name=_('URL'))

    def __unicode__(self):
        return self.title

        # video detail view/template
    def get_absolute_url(self):
        return reverse('video_detail', args=(self.id,))

    @property
    def name_long(self):
        if not self.title:
            return str(self.id)
        else:
            return '%s (%s)' % (self.title, self.id)

    def find_placeholder(self):
        placeholder = 'videos/{0}-placeholder.png'
        return finders.find(placeholder.format(self.extension), False) or \
            finders.find(placeholder.format('generic'), False)

    def is_file(self):
        return self.video_file and self.extension

    def is_image(self):
        return self.is_file() and self.extension.lower() in IMGTYPES

    @property
    def class_name(self):
        return self.__class__.__name__

    class Meta(ResourceBase.Meta):
        pass


class VideoResourceLink(models.Model):

    # relation to the video model
    video = models.ForeignKey(Video, related_name='links')

    # relation to the resource model
    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    resource = GenericForeignKey('content_type', 'object_id')

# leaving this the same
def get_related_videos(resource):
    if isinstance(resource, Layer) or isinstance(resource, Map):
        content_type = ContentType.objects.get_for_model(resource)
        return Video.objects.filter(links__content_type=content_type,
                                       links__object_id=resource.pk)
    else:
        return None

# leaving this the same
def get_related_resources(video):
    if video.links:
        try:
            return [
                link.content_type.get_object_for_this_type(id=link.object_id)
                for link in video.links.all()
            ]
        except BaseException:
            return []
    else:
        return []


def pre_save_video(instance, sender, **kwargs):
    base_name, extension, video_type = None, None, None

    if instance.video_file:
        base_name, extension = os.path.splitext(instance.video_file.name)
        instance.extension = extension[1:]
        video_type_map = VIDEO_TYPE_MAP
        video_type_map.update(getattr(settings, 'VIDEO_TYPE_MAP', {}))
        if video_type_map is None:
            video_type = 'other'
        else:
            video_type = video_type_map.get(instance.extension, 'other')
        instance.video_type = video_type

    elif instance.video_url:
        if '.' in urlparse(instance.video_url).path:
            instance.extension = urlparse(instance.video_url).path.rsplit('.')[-1]

    if not instance.uuid:
        instance.uuid = str(uuid.uuid1())
    # see if this works
    instance.csw_type = 'video'

    if instance.abstract == '' or instance.abstract is None:
        instance.abstract = 'No abstract provided'

    if instance.title == '' or instance.title is None:
        instance.title = instance.video_file.name

    resources = get_related_resources(instance)

    if resources:
        instance.bbox_x0 = min([r.bbox_x0 for r in resources])
        instance.bbox_x1 = max([r.bbox_x1 for r in resources])
        instance.bbox_y0 = min([r.bbox_y0 for r in resources])
        instance.bbox_y1 = max([r.bbox_y1 for r in resources])
    else:
        instance.bbox_x0 = -180
        instance.bbox_x1 = 180
        instance.bbox_y0 = -90
        instance.bbox_y1 = 90


def post_save_video(instance, *args, **kwargs):

    name = None
    ext = instance.extension
    mime_type_map = VIDEO_MIMETYPE_MAP
    mime_type_map.update(getattr(settings, 'VIDEO_MIMETYPE_MAP', {}))
    mime = mime_type_map.get(ext, 'text/plain')
    url = None

    if instance.video_file:
        name = "Hosted Video"
        site_url = settings.SITEURL.rstrip('/') if settings.SITEURL.startswith('http') else settings.SITEURL
        url = '%s%s' % (
            site_url,
            reverse('video_download', args=(instance.id,))) #video_download view/template
    elif instance.video_url:
        name = "Video"
        url = instance.video_url

    if name and url and ext:
        Link.objects.get_or_create(
            resource=instance.resourcebase_ptr,
            url=url,
            defaults=dict(
                extension=ext,
                name=name,
                mime=mime,
                url=url,
                link_type='data',))

# change in .tasks !
def create_thumbnail(sender, instance, created, **kwargs):
    # change in tasks !
    from .tasks import create_video_thumbnail

    create_video_thumbnail.delay(object_id=instance.id)

# leaving this the same
def update_video_extent(sender, **kwargs):
    videos = get_related_videos(sender)
    if videos:
        for video in videos:
            video.save()


def pre_delete_video(instance, sender, **kwargs):
    remove_object_permissions(instance.get_self_resource())


signals.pre_save.connect(pre_save_video, sender=Video)
signals.post_save.connect(create_thumbnail, sender=Video)
signals.post_save.connect(post_save_video, sender=Video)
signals.post_save.connect(resourcebase_post_save, sender=Video)
signals.pre_delete.connect(pre_delete_video, sender=Video)
map_changed_signal.connect(update_video_extent)
