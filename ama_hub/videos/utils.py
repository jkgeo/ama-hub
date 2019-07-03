# -*- coding: utf-8 -*-

"""
Utilities for managing AMA GeoNode videos
"""

# Standard Modules
import os

# Django functionality
from django.conf import settings

# Geonode functionality

from .models import Video


def delete_orphaned_video_files():
    """
    Deletes orphaned files of deleted videos.
    """

    videos_path = os.path.join(settings.MEDIA_ROOT, 'videos')
    for filename in os.listdir(videos_path):
        fn = os.path.join(videos_path, filename)
        if Video.objects.filter(video_file__contains=filename).count() == 0:
            print 'Removing orphan video %s' % fn
            try:
                os.remove(fn)
            except OSError:
                print 'Could not delete file %s' % fn
