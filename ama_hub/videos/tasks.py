# -*- coding: utf-8 -*-

import os
from os import access, R_OK
from os.path import isfile

from celery.app import shared_task
from celery.utils.log import get_task_logger

from .models import Video
from .renderers import render_video
from .renderers import generate_thumbnail_content
from .renderers import ConversionError
from .renderers import MissingPILError

logger = get_task_logger(__name__)


@shared_task(bind=True, queue='update')
def create_video_thumbnail(self, object_id):
    """
    Create thumbnail for a video.
    """

    logger.debug("Generating thumbnail for video #{}.".format(object_id))

    try:
        video = Video.objects.get(id=object_id)
    except Video.DoesNotExist:
        logger.error("Video #{} does not exist.".format(object_id))
        return

    image_path = None

    if video.is_image():
        image_path = video.video_file.path
    elif video.is_file():
        try:
            image_file = render_video(video.video_file.path)
            image_path = image_file.name
        except ConversionError as e:
            logger.debug("Could not convert video #{}: {}."
                         .format(object_id, e))

    try:
        if image_path:
            assert isfile(image_path) and access(image_path, R_OK) and os.stat(image_path).st_size > 0
    except (AssertionError, TypeError):
        image_path = None

    if not image_path:
        image_path = video.find_placeholder()

    if not image_path or not os.path.exists(image_path):
        logger.debug("Could not find placeholder for video #{}"
                     .format(object_id))
        return

    thumbnail_content = None
    try:
        thumbnail_content = generate_thumbnail_content(image_path)
    except MissingPILError:
        logger.error('Pillow not installed, could not generate thumbnail.')
        return

    if not thumbnail_content:
        logger.warning("Thumbnail for video #{} empty.".format(object_id))
    filename = 'video-{}-thumb.png'.format(video.uuid)
    video.save_thumbnail(filename, thumbnail_content)
    logger.debug("Thumbnail for video #{} created.".format(object_id))


@shared_task(bind=True, queue='cleanup')
def delete_orphaned_video_files(self):
    from ama_hub.videos.utils import delete_orphaned_video_files
    delete_orphaned_video_files()

# @shared_task(bind=True, queue='cleanup')
# def delete_orphaned_thumbnails(self):
#     from geonode.documents.utils import delete_orphaned_thumbs
#     delete_orphaned_thumbs()
