# -*- coding: utf-8 -*-

from tastypie.authentication import MultiAuthentication, SessionAuthentication
from tastypie.constants import ALL, ALL_WITH_RELATIONS

from ama_hub.resourcebase_api import ModCommonModelApi
from geonode.api.resourcebase_api import CommonMetaApi
from geonode.api.paginator import CrossSiteXHRPaginator
from geonode.api.authorization import GeoNodeAuthorization, GeonodeApiKeyAuthentication

from django.forms.models import model_to_dict

from geonode.groups.models import GroupProfile
from .models import Video

import settings

class VideoResource(ModCommonModelApi):

    """Video API"""

    def format_objects(self, objects):
        """
        Formats the objects and provides reference to list of layers in map
        resources.

        :param objects: Map objects
        """
        formatted_objects = []
        for obj in objects:
            # convert the object to a dict using the standard values.
            formatted_obj = model_to_dict(obj, fields=self.VALUES)
            username = obj.owner.get_username()
            full_name = (obj.owner.get_full_name() or username)
            formatted_obj['owner__username'] = username
            formatted_obj['owner_name'] = full_name
            if obj.category:
                formatted_obj['category__gn_description'] = obj.category.gn_description
            if obj.group:
                formatted_obj['group'] = obj.group
                try:
                    formatted_obj['group_name'] = GroupProfile.objects.get(slug=obj.group.name)
                except GroupProfile.DoesNotExist:
                    formatted_obj['group_name'] = obj.group

            formatted_obj['keywords'] = [k.name for k in obj.keywords.all()] if obj.keywords else []
            formatted_obj['regions'] = [r.name for r in obj.regions.all()] if obj.regions else []

            if 'site_url' not in formatted_obj or len(formatted_obj['site_url']) == 0:
                formatted_obj['site_url'] = settings.SITEURL

            # Probe Remote Services
            formatted_obj['store_type'] = 'dataset'
            formatted_obj['online'] = True

            formatted_objects.append(formatted_obj)
        return formatted_objects

    class Meta(CommonMetaApi):
        paginator_class = CrossSiteXHRPaginator
        filtering = CommonMetaApi.filtering
        filtering.update({'video_type': ALL})
        queryset = Video.objects.distinct().order_by('-date')
        resource_name = 'videos'
        authentication = MultiAuthentication(SessionAuthentication(), GeonodeApiKeyAuthentication())