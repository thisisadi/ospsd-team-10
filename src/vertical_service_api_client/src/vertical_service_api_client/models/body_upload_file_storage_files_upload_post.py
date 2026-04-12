from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from .. import types

T = TypeVar("T", bound="BodyUploadFileStorageFilesUploadPost")


@_attrs_define
class BodyUploadFileStorageFilesUploadPost:
    """
    Attributes:
        file (Any): Binary file-like object or string path.
    """

    file: Any
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        file = self.file

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "file": file,
            }
        )

        return field_dict

    def to_multipart(self) -> types.RequestFiles:
        files: types.RequestFiles = []
        file_val = self.file
        if hasattr(file_val, "read"):
            # binary file-like object — send as-is
            files.append(("file", (None, file_val, "application/octet-stream")))
        else:
            files.append(("file", (None, str(file_val).encode(), "text/plain")))
        for prop_name, prop in self.additional_properties.items():
            prop_val = prop
            if hasattr(prop_val, "read"):
                files.append((prop_name, (None, prop_val, "application/octet-stream")))
            else:
                files.append((prop_name, (None, str(prop_val).encode(), "text/plain")))
        return files

    @classmethod
    def from_dict(cls: type[T], src_dict: Mapping[str, Any]) -> T:
        d = dict(src_dict)
        file = d.pop("file")

        body_upload_file_storage_files_upload_post = cls(
            file=file,
        )

        body_upload_file_storage_files_upload_post.additional_properties = d
        return body_upload_file_storage_files_upload_post

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
