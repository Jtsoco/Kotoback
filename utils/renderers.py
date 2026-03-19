from collections.abc import Mapping
from typing import Any

from rest_framework.renderers import JSONRenderer


def _snake_to_camel(s: str) -> str:
    parts = s.split("_")
    if not parts:
        return s
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def _transform_keys(obj: Any) -> Any:
    if isinstance(obj, Mapping):
        return {
            _snake_to_camel(str(k)): _transform_keys(v)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_transform_keys(item) for item in obj]
    return obj


class CamelCaseJSONRenderer(JSONRenderer):
    """
    Renders responses with camelCase keys for JSON payloads.
    """

    def render(
        self,
        data: Any,
        accepted_media_type=None,
        renderer_context=None,
    ) -> bytes:
        data = _transform_keys(data)
        return super().render(data, accepted_media_type, renderer_context)
