from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="DeleteResult")


@_attrs_define
class DeleteResult:
    """Canonical response metadata for a delete operation.

    This type intentionally exposes only provider-neutral keys so consumers do
    not need to reason about provider-specific response shapes.

        Attributes:
            deleted (bool):
            version_id (None | str):
            request_charged (bool | None):
    """

    deleted: bool
    version_id: None | str
    request_charged: bool | None
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        deleted = self.deleted

        version_id: None | str
        version_id = self.version_id

        request_charged: bool | None
        request_charged = self.request_charged

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "deleted": deleted,
                "version_id": version_id,
                "request_charged": request_charged,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        deleted = d.pop("deleted")

        def _parse_version_id(data: object) -> None | str:
            if data is None:
                return data
            return cast(None | str, data)

        version_id = _parse_version_id(d.pop("version_id"))

        def _parse_request_charged(data: object) -> bool | None:
            if data is None:
                return data
            return cast(bool | None, data)

        request_charged = _parse_request_charged(d.pop("request_charged"))

        delete_result = cls(
            deleted=deleted,
            version_id=version_id,
            request_charged=request_charged,
        )

        delete_result.additional_properties = d
        return delete_result

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
