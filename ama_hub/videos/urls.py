# -*- coding: utf-8 -*-


from django.conf.urls import url
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView


from .views import VideoUploadView, VideoUpdateView
from . import views


js_info_dict = {
    'packages': ('ama_hub.videos',),
}

urlpatterns = [  # 'ama_videos.videos.views',
    url(r'^$',
        TemplateView.as_view(
        template_name='videos/video_list.html'),
        {'facet_type': 'videos'},
        name='video_browse'),
    url(r'^(?P<vidid>\d+)/?$',
        views.video_detail, name='video_detail'),
    url(r'^(?P<vidid>\d+)/download/?$',
        views.video_download, name='video_download'),
    url(r'^(?P<vidid>\d+)/replace$', login_required(VideoUpdateView.as_view()),
        name="video_replace"),
    url(r'^(?P<vidid>\d+)/remove$',
        views.video_remove, name="video_remove"),
    url(r'^upload/?$', login_required(
        VideoUploadView.as_view()), name='video_upload'),
    url(r'^search/?$', views.video_search_page,
        name='video_search_page'),
    url(r'^(?P<vidid>[^/]*)/metadata_detail$', views.video_metadata_detail,
        name='video_metadata_detail'),
    url(r'^(?P<vidid>\d+)/metadata$',
        views.video_metadata, name='video_metadata'),
#    url(
#        r'^metadata/batch/(?P<ids>[^/]*)/$',
#        views.video_batch_metadata,
#        name='video_batch_metadata'),
    url(r'^(?P<vidid>\d+)/metadata_advanced$', views.video_metadata_advanced,
        name='video_metadata_advanced'),
    url(r'^(?P<vidid>[^/]*)/thumb_upload$',
        views.video_thumb_upload, name='video_thumb_upload'),
]
