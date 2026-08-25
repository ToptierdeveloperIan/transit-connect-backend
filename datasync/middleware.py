from django.utils.cache import patch_vary_headers

from .utils import generate_etag


class ETagMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if request.method != "GET" or response.status_code != 200:
            return response

        if getattr(response, "streaming", False) or not hasattr(response, "content"):
            return response

        etag = response.get("ETag") or generate_etag(response.content)
        response["ETag"] = etag
        patch_vary_headers(response, ["Authorization"])

        client_etag = request.META.get("HTTP_IF_NONE_MATCH")
        if client_etag and client_etag == etag:
            response.status_code = 304
            response.content = b""
            if "Content-Type" in response:
                del response["Content-Type"]
            if "Content-Length" in response:
                del response["Content-Length"]

        return response
