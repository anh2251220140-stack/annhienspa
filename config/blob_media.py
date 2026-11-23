"""Private Vercel Blob images. No local filesystem fallback or public Blob URLs."""
from io import BytesIO
import logging
from pathlib import PurePosixPath
from urllib.parse import quote
from uuid import uuid4
import warnings

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.http import Http404, HttpResponse, JsonResponse
from django.utils.deconstruct import deconstructible
from django.utils.deprecation import MiddlewareMixin
from django.views.decorators.http import require_safe
from PIL import Image

from .local_media import IMAGE_DIRECTORIES, can_view_avatar

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_READ_BYTES = 20 * 1024 * 1024
FORMATS = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}
ERROR_MESSAGE = "Không thể lưu hoặc tải ảnh lúc này. Vui lòng thử lại sau; nếu vẫn lỗi, liên hệ quản trị viên."
logger = logging.getLogger(__name__)


class MediaStorageUnavailable(OSError):
    """Sanitized storage failure; never includes tokens, names or SDK responses."""


def image_name(name):
    name = str(name)
    parts = name.split("/")
    if (len(parts) < 2 or parts[0] not in IMAGE_DIRECTORIES
            or any(not part or part.startswith(".") for part in parts)
            or "avatars" in parts[1:]
            or any(ord(c) < 32 or ord(c) == 127 or c in "\\:%?#" for c in name)
            or PurePosixPath(name).suffix.lower() not in FORMATS):
        raise SuspiciousFileOperation("Invalid media image path.")
    return name


def validate_image(content, name, limit):
    if len(content) > limit:
        raise ValueError("Image exceeds storage size limit.")
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(BytesIO(content)) as picture:
            expected = FORMATS[PurePosixPath(name).suffix.lower()]
            if picture.format != expected:
                raise ValueError("Image format does not match extension.")
            picture.verify()
    return Image.MIME[expected]


def blob_sdk():
    # Lazy import keeps the Windows environment independent of this dependency.
    from vercel.blob import sync
    return sync


@deconstructible
class PrivateBlobStorage(Storage):
    def generate_filename(self, filename):
        # Django's base implementation uses os.path.join, which emits backslashes
        # on Windows. Blob keys always use POSIX separators after validation.
        return super().generate_filename(filename).replace("\\", "/")

    def get_available_name(self, name, max_length=None):
        # Immutable unique keys: replacing an image never overwrites another
        # record's file or breaks an old image when a DB transaction rolls back.
        name = image_name(name)
        path = PurePosixPath(name)
        suffix = path.suffix.lower()
        result = str(path.parent / (uuid4().hex + suffix))
        if max_length is not None and len(result) > max_length:
            raise SuspiciousFileOperation("Media path is too long.")
        return result

    def _save(self, name, content):
        name = image_name(name)
        try:
            raw = content.read(MAX_UPLOAD_BYTES + 1)
            mime = validate_image(raw, name, MAX_UPLOAD_BYTES)
            result = blob_sdk().put_blob(name, raw, access="private",
                                         content_type=mime, add_random_suffix=False,
                                         allow_overwrite=False)
            if result.pathname != name:
                raise ValueError("Unexpected Blob pathname.")
            return name
        except Exception:
            raise MediaStorageUnavailable(ERROR_MESSAGE) from None

    def _open(self, name, mode="rb"):
        name = image_name(name)
        if mode not in {"r", "rb"}:
            raise ValueError("Blob images can only be opened for reading.")
        try:
            sdk = blob_sdk()
            try:
                with sdk.stream_blob(name, access="private") as download:
                    if download.metadata.size is not None and download.metadata.size > MAX_READ_BYTES:
                        raise ValueError("Image too large.")
                    body = bytearray()
                    for chunk in download:
                        body.extend(chunk)
                        if len(body) > MAX_READ_BYTES:
                            raise ValueError("Image too large.")
                validate_image(body, name, MAX_READ_BYTES)
                return ContentFile(bytes(body), name=name)
            except sdk.BlobNotFoundError:
                raise FileNotFoundError("Media image not found.") from None
        except FileNotFoundError:
            raise
        except Exception:
            raise MediaStorageUnavailable(ERROR_MESSAGE) from None

    def exists(self, name):
        name = image_name(name)
        try:
            sdk = blob_sdk()
            try:
                sdk.head_blob(name)
                return True
            except sdk.BlobNotFoundError:
                return False
        except Exception:
            raise MediaStorageUnavailable(ERROR_MESSAGE) from None

    def size(self, name):
        name = image_name(name)
        try:
            return blob_sdk().head_blob(name).size
        except Exception:
            raise MediaStorageUnavailable(ERROR_MESSAGE) from None

    def delete(self, name):
        name = image_name(name)
        try:
            blob_sdk().delete_blob(name)
        except Exception:
            raise MediaStorageUnavailable(ERROR_MESSAGE) from None

    def url(self, name):
        # Preserve existing DB paths and keep avatar requests behind Django auth.
        return "/media/" + quote(image_name(name), safe="/")


@require_safe
def blob_image(request, path):
    if not getattr(settings, "BLOB_MEDIA_ENABLED", False):
        raise Http404
    try:
        name = image_name(path)
    except SuspiciousFileOperation:
        raise Http404 from None
    if name.startswith("avatars/") and not can_view_avatar(request.user, name):
        raise Http404
    try:
        with PrivateBlobStorage().open(name) as source:
            response = HttpResponse(source.read(), content_type=Image.MIME[FORMATS[PurePosixPath(name).suffix.lower()]])
    except FileNotFoundError:
        raise Http404 from None
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "default-src 'none'; sandbox"
    return response


class BlobFailureMiddleware(MiddlewareMixin):
    def process_exception(self, request, exception):
        if not isinstance(exception, MediaStorageUnavailable):
            return None
        # The exception leaves the view's atomic block first, rolling back changes.
        logger.warning("MEDIA_STORAGE_UNAVAILABLE")
        response = JsonResponse({"error": ERROR_MESSAGE, "code": "MEDIA_STORAGE_UNAVAILABLE"}, status=503)
        response["Cache-Control"] = "private, no-store"
        return response
