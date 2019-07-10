# -*- coding: utf-8 -*-

import os
import json
import logging
from itertools import chain

from guardian.shortcuts import get_perms

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.template import loader
from django.utils.translation import ugettext as _
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.core.urlresolvers import reverse
from django.core.exceptions import PermissionDenied
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django_downloadview.response import DownloadResponse
from django.views.generic.edit import UpdateView, CreateView
from django.db.models import F
from django.forms.utils import ErrorList

from geonode.utils import resolve_object
from geonode.security.views import _perms_info_json
from geonode.people.forms import ProfileForm
from geonode.base.forms import CategoryForm
from geonode.base.models import TopicCategory
from ama_hub.videos.models import Video, get_related_resources
from ama_hub.videos.forms import VideoForm, VideoCreateForm, VideoReplaceForm
from ama_hub.videos.models import IMGTYPES
from ama_hub.videos.renderers import generate_thumbnail_content, MissingPILError
from geonode.utils import build_social_links
from geonode.groups.models import GroupProfile
from geonode.base.views import batch_modify


logger = logging.getLogger("ama_hub.videos.views")

ALLOWED_DOC_TYPES = settings.ALLOWED_DOCUMENT_TYPES

_PERMISSION_MSG_DELETE = _("You are not permitted to delete this video")
_PERMISSION_MSG_GENERIC = _("You do not have permissions for this video.")
_PERMISSION_MSG_MODIFY = _("You are not permitted to modify this video")
_PERMISSION_MSG_METADATA = _(
    "You are not permitted to modify this video's metadata")
_PERMISSION_MSG_VIEW = _("You are not permitted to view this video")


def _resolve_video(request, vidid, permission='base.change_resourcebase',
                      msg=_PERMISSION_MSG_GENERIC, **kwargs):
    '''
    Resolve the video by the provided primary key and check the optional permission.
    '''
    return resolve_object(request, Video, {'pk': vidid},
                          permission=permission, permission_msg=msg, **kwargs)


def video_detail(request, vidid):
    """
    The view that show details of each video
    """
    video = None
    try:
        video = _resolve_video(
            request,
            vidid,
            'base.view_resourcebase',
            _PERMISSION_MSG_VIEW)

    except Http404:
        return HttpResponse(
            loader.render_to_string(
                '404.html', context={
                }, request=request), status=404)

    except PermissionDenied:
        return HttpResponse(
            loader.render_to_string(
                '401.html', context={
                    'error_message': _("You are not allowed to view this video.")}, request=request), status=403)

    if video is None:
        return HttpResponse(
            'An unknown error has occured.',
            content_type="text/plain",
            status=401
        )

    else:
        related = get_related_resources(video)

        # Update count for popularity ranking,
        # but do not includes admins or resource owners
        if request.user != video.owner and not request.user.is_superuser:
            Video.objects.filter(
                id=video.id).update(
                popular_count=F('popular_count') + 1)

        metadata = video.link_set.metadata().filter(
            name__in=settings.DOWNLOAD_FORMATS_METADATA)

        group = None
        if video.group:
            try:
                group = GroupProfile.objects.get(slug=video.group.name)
            except GroupProfile.DoesNotExist:
                group = None
        context_dict = {
            'perms_list': get_perms(
                request.user,
                video.get_self_resource()) + get_perms(request.user, video),
            'permissions_json': _perms_info_json(video),
            'resource': video,
            'group': group,
            'metadata': metadata,
            'imgtypes': IMGTYPES,
            'related': related}

        if settings.SOCIAL_ORIGINS:
            context_dict["social_links"] = build_social_links(
                request, video)

        # if getattr(settings, 'EXIF_ENABLED', False):
        #     try:
        #         from ama_hub.videos.exif.utils import exif_extract_dict
        #         exif = exif_extract_dict(video)
        #         if exif:
        #             context_dict['exif_data'] = exif
        #     except BaseException:
        #         print "Exif extraction failed."

        if request.user.is_authenticated():
            if getattr(settings, 'FAVORITE_ENABLED', False):
                from geonode.favorite.utils import get_favorite_info
                context_dict["favorite_info"] = get_favorite_info(request.user, video)

        return render(
            request,
            "videos/video_detail.html",
            context=context_dict)


def video_download(request, vidid):
    video = get_object_or_404(Video, pk=vidid)

    if settings.MONITORING_ENABLED and video:
        if hasattr(video, 'alternate'):
            request.add_resource('video', video.alternate)

    if not request.user.has_perm(
            'base.download_resourcebase',
            obj=video.get_self_resource()):
        return HttpResponse(
            loader.render_to_string(
                '401.html', context={
                    'error_message': _("You are not allowed to view this video.")}, request=request), status=401)
    return DownloadResponse(video.vid_file)


class VideoUploadView(CreateView):
    template_name = 'videos/video_upload.html'
    form_class = VideoCreateForm

    def get_context_data(self, **kwargs):
        context = super(VideoUploadView, self).get_context_data(**kwargs)
        context['ALLOWED_DOC_TYPES'] = ALLOWED_DOC_TYPES
        return context

    def form_invalid(self, form):
        if self.request.GET.get('no__redirect', False):
            out = {'success': False}
            out['message'] = ""
            status_code = 400
            return HttpResponse(
                json.dumps(out),
                content_type='application/json',
                status=status_code)
        else:
            form.name = None
            form.title = None
            form.vid_file = None
            form.vid_url = None
            return self.render_to_response(self.get_context_data(form=form))

    def form_valid(self, form):
        """
        If the form is valid, save the associated model.
        """
        self.object = form.save(commit=False)
        self.object.owner = self.request.user
        # by default, if RESOURCE_PUBLISHING=True then video.is_published
        # must be set to False
        # RESOURCE_PUBLISHING works in similar way as ADMIN_MODERATE_UPLOADS,
        # but is applied to videos only. ADMIN_MODERATE_UPLOADS has wider
        # usage
        is_published = not (
            settings.RESOURCE_PUBLISHING or settings.ADMIN_MODERATE_UPLOADS)
        self.object.is_published = is_published
        self.object.save()
        form.save_many2many()
        self.object.set_permissions(form.cleaned_data['permissions'])

        abstract = None
        date = None
        regions = []
        keywords = []
        bbox = None

        out = {'success': False}

        if getattr(settings, 'EXIF_ENABLED', False):
            try:
                from ama_hub.videos.exif.utils import exif_extract_metadata_doc
                exif_metadata = exif_extract_metadata_doc(self.object)
                if exif_metadata:
                    date = exif_metadata.get('date', None)
                    keywords.extend(exif_metadata.get('keywords', []))
                    bbox = exif_metadata.get('bbox', None)
                    abstract = exif_metadata.get('abstract', None)
            except BaseException:
                print "Exif extraction failed."

        if abstract:
            self.object.abstract = abstract
            self.object.save()

        if date:
            self.object.date = date
            self.object.date_type = "Creation"
            self.object.save()

        if len(regions) > 0:
            self.object.regions.add(*regions)

        if len(keywords) > 0:
            self.object.keywords.add(*keywords)

        if bbox:
            bbox_x0, bbox_x1, bbox_y0, bbox_y1 = bbox
            Video.objects.filter(id=self.object.pk).update(
                bbox_x0=bbox_x0,
                bbox_x1=bbox_x1,
                bbox_y0=bbox_y0,
                bbox_y1=bbox_y1)

        if getattr(settings, 'MONITORING_ENABLED', False) and self.object:
            if hasattr(self.object, 'alternate'):
                self.request.add_resource('video', self.object.alternate)

        if self.request.GET.get('no__redirect', False):
            out['success'] = True
            out['url'] = reverse(
                'video_detail',
                args=(
                    self.object.id,
                ))
            if out['success']:
                status_code = 200
            else:
                status_code = 400
            return HttpResponse(
                json.dumps(out),
                content_type='application/json',
                status=status_code)
        else:
            return HttpResponseRedirect(
                reverse(
                    'video_metadata',
                    args=(
                        self.object.id,
                    )))


class VideoUpdateView(UpdateView):
    template_name = 'videos/video_replace.html'
    pk_url_kwarg = 'vidid'
    form_class = VideoReplaceForm
    queryset = Video.objects.all()
    context_object_name = 'video'

    def get_context_data(self, **kwargs):
        context = super(VideoUpdateView, self).get_context_data(**kwargs)
        context['ALLOWED_DOC_TYPES'] = ALLOWED_DOC_TYPES
        return context

    def form_valid(self, form):
        """
        If the form is valid, save the associated model.
        """
        self.object = form.save()
        if settings.MONITORING_ENABLED and self.object:
            if hasattr(self.object, 'alternate'):
                self.request.add_resource('video', self.object.alternate)
        return HttpResponseRedirect(
            reverse(
                'video_metadata',
                args=(
                    self.object.id,
                )))


@login_required
def video_metadata(
        request,
        vidid,
        template='videos/video_metadata.html',
        ajax=True):

    video = None
    try:
        video = _resolve_video(
            request,
            vidid,
            'base.change_resourcebase_metadata',
            _PERMISSION_MSG_METADATA)

    except Http404:
        return HttpResponse(
            loader.render_to_string(
                '404.html', context={
                }, request=request), status=404)

    except PermissionDenied:
        return HttpResponse(
            loader.render_to_string(
                '401.html', context={
                    'error_message': _("You are not allowed to edit this video.")}, request=request), status=403)

    if video is None:
        return HttpResponse(
            'An unknown error has occured.',
            content_type="text/plain",
            status=401
        )

    else:
        poc = video.poc
        metadata_author = video.metadata_author
        topic_category = video.category

        if request.method == "POST":
            video_form = VideoForm(
                request.POST,
                instance=video,
                prefix="resource")
            category_form = CategoryForm(request.POST, prefix="category_choice_field", initial=int(
                request.POST["category_choice_field"]) if "category_choice_field" in request.POST and
                request.POST["category_choice_field"] else None)
        else:
            video_form = VideoForm(instance=video, prefix="resource")
            category_form = CategoryForm(
                prefix="category_choice_field",
                initial=topic_category.id if topic_category else None)

        if request.method == "POST" and video_form.is_valid(
        ) and category_form.is_valid():
            new_poc = video_form.cleaned_data['poc']
            new_author = video_form.cleaned_data['metadata_author']
            new_keywords = video_form.cleaned_data['keywords']
            new_regions = video_form.cleaned_data['regions']

            new_category = None
            if category_form and 'category_choice_field' in category_form.cleaned_data and\
            category_form.cleaned_data['category_choice_field']:
                new_category = TopicCategory.objects.get(
                    id=int(category_form.cleaned_data['category_choice_field']))

            if new_poc is None:
                if poc is None:
                    poc_form = ProfileForm(
                        request.POST,
                        prefix="poc",
                        instance=poc)
                else:
                    poc_form = ProfileForm(request.POST, prefix="poc")
                if poc_form.is_valid():
                    if len(poc_form.cleaned_data['profile']) == 0:
                        # FIXME use form.add_error in django > 1.7
                        errors = poc_form._errors.setdefault(
                            'profile', ErrorList())
                        errors.append(
                            _('You must set a point of contact for this resource'))
                        poc = None
                if poc_form.has_changed and poc_form.is_valid():
                    new_poc = poc_form.save()

            if new_author is None:
                if metadata_author is None:
                    author_form = ProfileForm(request.POST, prefix="author",
                                              instance=metadata_author)
                else:
                    author_form = ProfileForm(request.POST, prefix="author")
                if author_form.is_valid():
                    if len(author_form.cleaned_data['profile']) == 0:
                        # FIXME use form.add_error in django > 1.7
                        errors = author_form._errors.setdefault(
                            'profile', ErrorList())
                        errors.append(
                            _('You must set an author for this resource'))
                        metadata_author = None
                if author_form.has_changed and author_form.is_valid():
                    new_author = author_form.save()

            the_video = video_form.instance
            if new_poc is not None and new_author is not None:
                the_video.poc = new_poc
                the_video.metadata_author = new_author
            if new_keywords:
                the_video.keywords.clear()
                the_video.keywords.add(*new_keywords)
            if new_regions:
                the_video.regions.clear()
                the_video.regions.add(*new_regions)
            the_video.save()
            video_form.save_many2many()
            Video.objects.filter(
                id=the_video.id).update(
                category=new_category)

            if not ajax:
                return HttpResponseRedirect(
                    reverse(
                        'video_detail',
                        args=(
                            video.id,
                        )))

            message = video.id

            return HttpResponse(json.dumps({'message': message}))

        # - POST Request Ends here -

        # Request.GET
        if poc is not None:
            video_form.fields['poc'].initial = poc.id
            poc_form = ProfileForm(prefix="poc")
            poc_form.hidden = True

        if metadata_author is not None:
            video_form.fields['metadata_author'].initial = metadata_author.id
            author_form = ProfileForm(prefix="author")
            author_form.hidden = True

        metadata_author_groups = []
        if request.user.is_superuser or request.user.is_staff:
            metadata_author_groups = GroupProfile.objects.all()
        else:
            try:
                all_metadata_author_groups = chain(
                    request.user.group_list_all(),
                    GroupProfile.objects.exclude(
                        access="private").exclude(access="public-invite"))
            except BaseException:
                all_metadata_author_groups = GroupProfile.objects.exclude(
                    access="private").exclude(access="public-invite")
            [metadata_author_groups.append(item) for item in all_metadata_author_groups
                if item not in metadata_author_groups]

        if settings.ADMIN_MODERATE_UPLOADS:
            if not request.user.is_superuser:
                video_form.fields['is_published'].widget.attrs.update(
                    {'disabled': 'true'})

                can_change_metadata = request.user.has_perm(
                    'change_resourcebase_metadata',
                    video.get_self_resource())
                try:
                    is_manager = request.user.groupmember_set.all().filter(role='manager').exists()
                except BaseException:
                    is_manager = False
                if not is_manager or not can_change_metadata:
                    video_form.fields['is_approved'].widget.attrs.update(
                        {'disabled': 'true'})

        return render(request, template, context={
            "resource": video,
            "video": video,
            "video_form": video_form,
            "poc_form": poc_form,
            "author_form": author_form,
            "category_form": category_form,
            "metadata_author_groups": metadata_author_groups,
            "TOPICCATEGORY_MANDATORY": getattr(settings, 'TOPICCATEGORY_MANDATORY', False),
            "GROUP_MANDATORY_RESOURCES": getattr(settings, 'GROUP_MANDATORY_RESOURCES', False),
        })


@login_required
def video_metadata_advanced(request, vidid):
    return video_metadata(
        request,
        vidid,
        template='videos/video_metadata_advanced.html')


@login_required
def video_thumb_upload(
        request,
        vidid,
        template='videos/video_thumb_upload.html'):
    video = None
    try:
        video = _resolve_video(
            request,
            vidid,
            'base.change_resourcebase',
            _PERMISSION_MSG_MODIFY)

    except Http404:
        return HttpResponse(
            loader.render_to_string(
                '404.html', context={
                }, request=request), status=404)

    except PermissionDenied:
        return HttpResponse(
            loader.render_to_string(
                '401.html', context={
                    'error_message': _("You are not allowed to edit this video.")}, request=request), status=403)

    if video is None:
        return HttpResponse(
            'An unknown error has occured.',
            content_type="text/plain",
            status=401
        )

    site_url = settings.SITEURL.rstrip('/') if settings.SITEURL.startswith('http') else settings.SITEURL
    if request.method == 'GET':
        return render(request, template, context={
            "resource": video,
            "vidid": vidid,
            'SITEURL': site_url
        })
    elif request.method == 'POST':
        status_code = 401
        out = {'success': False}
        if vidid and request.FILES:
            data = request.FILES.get('base_file')
            if data:
                filename = 'video-{}-thumb.png'.format(video.uuid)
                path = default_storage.save(
                    'tmp/' + filename, ContentFile(data.read()))
                f = os.path.join(settings.MEDIA_ROOT, path)
                try:
                    image_path = f
                except BaseException:
                    image_path = video.find_placeholder()

                thumbnail_content = None
                try:
                    thumbnail_content = generate_thumbnail_content(image_path)
                except MissingPILError:
                    logger.error(
                        'Pillow not installed, could not generate thumbnail.')

                if not thumbnail_content:
                    logger.warning("Thumbnail for video #{} empty.".format(vidid))
                video.save_thumbnail(filename, thumbnail_content)
                logger.debug(
                    "Thumbnail for video #{} created.".format(vidid))
            status_code = 200
            out['success'] = True
            out['resource'] = vidid
        else:
            out['success'] = False
            out['errors'] = 'An unknown error has occured.'
        out['url'] = reverse(
            'video_detail', args=[
                vidid])
        return HttpResponse(
            json.dumps(out),
            content_type='application/json',
            status=status_code)


def video_search_page(request):
    # for non-ajax requests, render a generic search page

    if request.method == 'GET':
        params = request.GET
    elif request.method == 'POST':
        params = request.POST
    else:
        return HttpResponse(status=405)

    return render(
        request,
        'videos/video_search.html',
        context={'init_search': json.dumps(params or {}), "site": settings.SITEURL})


@login_required
def video_remove(request, vidid, template='videos/video_remove.html'):
    try:
        video = _resolve_video(
            request,
            vidid,
            'base.delete_resourcebase',
            _PERMISSION_MSG_DELETE)

        if request.method == 'GET':
            return render(request, template, context={
                "video": video
            })

        if request.method == 'POST':
            video.delete()

            return HttpResponseRedirect(reverse("video_browse"))
        else:
            return HttpResponse("Not allowed", status=403)

    except PermissionDenied:
        return HttpResponse(
            'You are not allowed to delete this video',
            content_type="text/plain",
            status=401
        )


def video_metadata_detail(
        request,
        vidid,
        template='videos/video_metadata_detail.html'):
    video = _resolve_video(
        request,
        vidid,
        'view_resourcebase',
        _PERMISSION_MSG_METADATA)
    group = None
    if video.group:
        try:
            group = GroupProfile.objects.get(slug=video.group.name)
        except GroupProfile.DoesNotExist:
            group = None
    site_url = settings.SITEURL.rstrip('/') if settings.SITEURL.startswith('http') else settings.SITEURL
    return render(request, template, context={
        "resource": video,
        "group": group,
        'SITEURL': site_url
    })


@login_required
def video_batch_metadata(request, ids):
    return batch_modify(request, ids, 'Video')