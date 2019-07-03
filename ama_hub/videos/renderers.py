# -*- coding: utf-8 -*-

import subprocess
import traceback

from django.conf import settings
from threading import Timer
from mimetypes import guess_type
from urllib import pathname2url
from tempfile import NamedTemporaryFile


class ConversionError(Exception):
    """Raise when conversion was unsuccessful."""
    pass


class MissingPILError(Exception):
    """Raise when could not import PIL package."""
    pass


def guess_mimetype(video_path):
    """Guess mime type for a file in local filesystem.

    Return string containing valid mime type.
    """
    video_url = pathname2url(video_path)
    return guess_type(video_url)[0]

def render_video(video_path, extension="png"):
    """Render video using `unconv` converter.

    Package `unoconv` has to be installed and available on system
    path. Return `NamedTemporaryFile` instance.
    """

    ### NEED TO REVISIT
    
    # workaround: https://github.com/dagwieers/unoconv/issues/167
    # first convert a document to PDF and continue
    if extension == "pdf":
        temp_path = video_path
    elif guess_mimetype(video_path) == 'application/pdf':
        temp_path = video_path
    else:
        temp = render_video(video_path, extension="pdf")
        temp_path = temp.name

    # spawn subprocess and render the document
    output = NamedTemporaryFile(suffix='.{}'.format(extension))
    if settings.UNOCONV_ENABLE:
        timeout = None
        try:
            def kill(process):
                return process.kill()

            unoconv = subprocess.Popen(
                [settings.UNOCONV_EXECUTABLE, "-v", "-e", "PageRange=1-2",
                    "-f", extension, "-o", output.name, temp_path],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            timeout = Timer(settings.UNOCONV_TIMEOUT, kill, [unoconv])
            timeout.start()
            stdout, stderr = unoconv.communicate()
        except Exception as e:
            traceback.print_exc()
            raise ConversionError(str(e))
        finally:
            if timeout:
                timeout.cancel()

    return output


def generate_thumbnail_content(image_path, size=(200, 150)):
    """Generate thumbnail content from an image file.

    Return the entire content of the image file.
    """
    from cStringIO import StringIO

    try:
        from PIL import Image, ImageOps
    except ImportError:
        raise MissingPILError()

    try:
        image = Image.open(image_path)
        source_width, source_height = image.size
        target_width, target_height = size

        if source_width != target_width or source_width != target_height:
            image = ImageOps.fit(image, size, Image.ANTIALIAS)

        output = StringIO()
        image.save(output, format='PNG')
        content = output.getvalue()
        output.close()
        return content
    except BaseException:
        return None
