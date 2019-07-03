# -*- coding: utf-8 -*-

from modeltranslation.translator import translator, TranslationOptions
from .models import Video


class VideoTranslationOptions(TranslationOptions):
    fields = (
        'title',
        'abstract',
        'purpose',
        'constraints_other',
        'supplemental_information',
        'data_quality_statement',
    )


translator.register(Video, VideoTranslationOptions)