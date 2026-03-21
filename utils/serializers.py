import re
from typing import Any, Dict

def camel_to_snake(name: str) -> str:
    """
    Converts camelCase/PascalCase to snake_case.

    Example: frontLanguage -> front_language
    """

    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    return s2.lower()


class CamelCaseInputMixin:
    """
    Accept camelCase input for serializer top-level keys.

    We intentionally do not rewrite keys inside JSONField payloads, so
    content keys like `studyWord` stay untouched.
    """

    @staticmethod
    def _transform_top_level_keys(data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        out: Dict[str, Any] = {}
        for k, v in data.items():
            if isinstance(k, str):
                out[camel_to_snake(k)] = v
            else:
                out[k] = v
        return out

    def to_internal_value(self, data: Any) -> Any:
        data = self._transform_top_level_keys(data)
        return super().to_internal_value(data)

    def to_representation(self, instance: Any) -> Any:
        data = super().to_representation(instance)
        # Ensure outgoing JSON is camelCase even if renderer negotiation
        # doesn't select the custom renderer in some environments/tests.
        from utils.renderers import _transform_keys

        return _transform_keys(data)

