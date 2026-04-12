from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.body_upload_file_storage_files_upload_post import BodyUploadFileStorageFilesUploadPost
from ...models.http_validation_error import HTTPValidationError
from ...models.object_info import ObjectInfo
from ...types import UNSET, Response


def _get_kwargs(
    *,
    body: BodyUploadFileStorageFilesUploadPost,
    container: str,
    remote_path: str,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}

    params: dict[str, Any] = {}

    params["container"] = container

    params["remote_path"] = remote_path

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/storage/files/upload",
        "params": params,
    }

    _kwargs["files"] = body.to_multipart()

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | ObjectInfo | None:
    if response.status_code == 201:
        response_201 = ObjectInfo.from_dict(response.json())

        return response_201

    if response.status_code == 422:
        response_422 = HTTPValidationError.from_dict(response.json())

        return response_422

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[HTTPValidationError | ObjectInfo]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: BodyUploadFileStorageFilesUploadPost,
    container: str,
    remote_path: str,
) -> Response[HTTPValidationError | ObjectInfo]:
    """Upload File

     Upload a file to cloud storage (maps to CloudStorageClient.upload_obj).

    Args:
        container (str):
        remote_path (str):
        body (BodyUploadFileStorageFilesUploadPost):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ObjectInfo]
    """

    kwargs = _get_kwargs(
        body=body,
        container=container,
        remote_path=remote_path,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    body: BodyUploadFileStorageFilesUploadPost,
    container: str,
    remote_path: str,
) -> HTTPValidationError | ObjectInfo | None:
    """Upload File

     Upload a file to cloud storage (maps to CloudStorageClient.upload_obj).

    Args:
        container (str):
        remote_path (str):
        body (BodyUploadFileStorageFilesUploadPost):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ObjectInfo
    """

    return sync_detailed(
        client=client,
        body=body,
        container=container,
        remote_path=remote_path,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: BodyUploadFileStorageFilesUploadPost,
    container: str,
    remote_path: str,
) -> Response[HTTPValidationError | ObjectInfo]:
    """Upload File

     Upload a file to cloud storage (maps to CloudStorageClient.upload_obj).

    Args:
        container (str):
        remote_path (str):
        body (BodyUploadFileStorageFilesUploadPost):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ObjectInfo]
    """

    kwargs = _get_kwargs(
        body=body,
        container=container,
        remote_path=remote_path,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: BodyUploadFileStorageFilesUploadPost,
    container: str,
    remote_path: str,
) -> HTTPValidationError | ObjectInfo | None:
    """Upload File

     Upload a file to cloud storage (maps to CloudStorageClient.upload_obj).

    Args:
        container (str):
        remote_path (str):
        body (BodyUploadFileStorageFilesUploadPost):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ObjectInfo
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
            container=container,
            remote_path=remote_path,
        )
    ).parsed
