from unittest.mock import MagicMock

from cloud_storage_adapter.adapter import CloudStorageServiceAdapter


def test_adapter_delegates_upload() -> None:
    storage_api = MagicMock()
    adapter = CloudStorageServiceAdapter(storage_api=storage_api)

    adapter.upload_object("bucket", "file.txt", b"abc")

    storage_api.upload_object.assert_called_once_with("bucket", "file.txt", b"abc")


def test_adapter_delegates_download() -> None:
    storage_api = MagicMock()
    storage_api.download_object.return_value = b"content"
    adapter = CloudStorageServiceAdapter(storage_api=storage_api)

    result = adapter.download_object("bucket", "file.txt")

    assert result == b"content"
    storage_api.download_object.assert_called_once_with("bucket", "file.txt")


def test_adapter_delegates_delete() -> None:
    storage_api = MagicMock()
    storage_api.delete_object.return_value = True
    adapter = CloudStorageServiceAdapter(storage_api=storage_api)

    result = adapter.delete_object("bucket", "file.txt")

    assert result is True
    storage_api.delete_object.assert_called_once_with("bucket", "file.txt")


def test_adapter_delegates_list() -> None:
    storage_api = MagicMock()
    storage_api.list_objects.return_value = ["a", "b"]
    adapter = CloudStorageServiceAdapter(storage_api=storage_api)

    result = list(adapter.list_objects("bucket"))

    assert result == ["a", "b"]
    storage_api.list_objects.assert_called_once_with("bucket")
