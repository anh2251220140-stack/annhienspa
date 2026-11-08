"""Opt-in image route for direct loopback development, never a media server."""
from pathlib import Path
from io import BytesIO
from urllib.parse import urlsplit

from django.conf import settings
from django.http import FileResponse, Http404
from django.views.decorators.http import require_safe
from PIL import Image


@require_safe
def local_image(request, path):
    # A local tunnel/proxy also has a loopback peer: reject its host and headers.
    host = urlsplit("//" + request.get_host()).hostname
    forwarded = any(
        key == "HTTP_FORWARDED" or key.startswith("HTTP_X_FORWARDED_")
        or key in {"HTTP_X_REAL_IP", "HTTP_VIA"}
        for key in request.META
    )
    if (not settings.LOCAL_MEDIA_ENABLED or forwarded
            or request.META.get("REMOTE_ADDR") not in {"127.0.0.1", "::1"}
            or host not in {"localhost", "127.0.0.1", "::1"}):
        raise Http404
    parts = path.split("/")
    if (len(parts) < 2 or parts[0] not in {"services", "products", "employees"}
            or any(not part or part.startswith(".") for part in parts)
            or any(char in path for char in ("\\", ":", "%", "\x00"))):
        raise Http404
    formats = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}
    stream = None
    try:
        root = Path(settings.MEDIA_ROOT).resolve(strict=True)
        target = (root / path).resolve(strict=True)
        relative = target.relative_to(root)
        if relative.parts[0] not in {"services", "products", "employees"} or not target.is_file():
            raise Http404
        expected = formats.get(target.suffix.lower())
        if not expected:
            raise Http404
        stream = target.open("rb")
        content = stream.read(20 * 1024 * 1024 + 1)
        if len(content) > 20 * 1024 * 1024:
            raise Http404
        with Image.open(BytesIO(content)) as picture:
            if picture.format != expected:
                raise Http404
            picture.verify()
        stream.close()
        stream = BytesIO(content)
        response = FileResponse(stream, content_type=Image.MIME[expected])
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        response["Content-Security-Policy"] = "default-src 'none'; sandbox"
        return response
    except (OSError, ValueError, Image.DecompressionBombError):
        if stream is not None:
            stream.close()
        raise Http404
    except Http404:
        if stream is not None:
            stream.close()
        raise
