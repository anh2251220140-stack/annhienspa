"""Docker-only image delivery through Django authentication, never an Nginx alias."""
from io import BytesIO
from pathlib import Path
import warnings

from django.conf import settings
from django.http import FileResponse, Http404
from django.views.decorators.http import require_safe
from PIL import Image

from .local_media import IMAGE_DIRECTORIES, can_view_avatar


@require_safe
def docker_image(request, path):
    if not getattr(settings, "DOCKER_MEDIA_ENABLED", False):
        raise Http404
    parts = path.split("/")
    if (len(parts) < 2 or parts[0] not in IMAGE_DIRECTORIES
            or any(not part or part.startswith(".") for part in parts)
            or any(char in path for char in ("\\", ":", "%", "\x00"))):
        raise Http404
    formats = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}
    try:
        source = Path(settings.MEDIA_ROOT)
        if source.is_symlink():
            raise Http404
        root = source.resolve(strict=True)
        target = root
        for part in parts:
            target = target / part
            if target.is_symlink():
                raise Http404
        target = target.resolve(strict=True)
        relative = target.relative_to(root)
        if relative.parts[0] not in IMAGE_DIRECTORIES or not target.is_file():
            raise Http404
        if "avatars" in relative.parts and (
                relative.parts[0] != "avatars"
                or not can_view_avatar(request.user, relative.as_posix())):
            raise Http404
        expected = formats.get(target.suffix.lower())
        if not expected:
            raise Http404
        with target.open("rb") as stream:
            content = stream.read(20 * 1024 * 1024 + 1)
        if len(content) > 20 * 1024 * 1024:
            raise Http404
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as picture:
                if picture.format != expected:
                    raise Http404
                picture.verify()
        response = FileResponse(BytesIO(content), content_type=Image.MIME[expected])
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        response["Content-Security-Policy"] = "default-src 'none'; sandbox"
        return response
    except (OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise Http404 from None
