# -*- coding: utf-8 -*-
import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import render

from .videos.models import Video, ModFavorite

from geonode.documents.models import Document
from geonode.layers.models import Layer
from geonode.maps.models import Map
from geonode.favorite.models import Favorite

###

# Extended Favorites App

###

@login_required
def favorite(req, subject, id):
    """
    create favorite and put favorite_info object in response.
    method is idempotent, Favorite's create_favorite method
    only creates if does not already exist.
    """
    if subject == 'video':
        obj = get_object_or_404(Video, pk=id)

    favorite = ModFavorite.objects.create_favorite(obj, req.user)
    delete_url = reverse("delete_favorite", args=[favorite.pk])
    response = {"has_favorite": "true", "delete_url": delete_url}

    return HttpResponse(json.dumps(response), content_type="application/json", status=200)