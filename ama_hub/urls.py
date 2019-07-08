# -*- coding: utf-8 -*-

from django.conf.urls import url, include
from django.views.generic import TemplateView

from geonode.urls import urlpatterns
from .views import favorite
# get_favorites, delete_favorite,

from geonode.api.urls import api
from .videos.api import VideoResource

api.register(VideoResource())

urlpatterns += [
	url(r'', include(api.urls)),
	url(r'^videos/', include('ama_hub.videos.urls')),
    ###
    # favorites app
    ###
    url(
        r'^video/(?P<id>\d+)$',
        favorite, {'subject': 'video'},
        name='add_favorite_video'
    ),
]

urlpatterns = [
   url(r'^/?$',
       TemplateView.as_view(template_name='site_index.html'),
       name='home'),
 ] + urlpatterns
