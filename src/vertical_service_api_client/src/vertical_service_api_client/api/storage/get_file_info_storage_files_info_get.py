from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.http_validation_error import HTTPValidationError
from ...models.object_info import ObjectInfo
from ...types import UNSET, Response


def _get_kwargs(
    *,
    container: str,
    object_name: str,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["container"] = container

    params["object_name"] = object_name

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/storage/files/info",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HTTPValidationError | ObjectInfo | None:
    if response.status_code == 200:
        response_200 = ObjectInfo.from_dict(response.json())

        return response_200

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
    container: str,
    object_name: str,
) -> Response[HTTPValidationError | ObjectInfo]:
    """Get File Info

     Get metadata for a stored object (maps to CloudStorageClient.get_file_info).

    Args:
        container (str):
        object_name (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ObjectInfo]
    """

    kwargs = _get_kwargs(
        container=container,
        object_name=object_name,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    container: str,
    object_name: str,
) -> HTTPValidationError | ObjectInfo | None:
    """Get File Info

     Get metadata for a stored object (maps to CloudStorageClient.get_file_info).

    Args:
        container (str):
        object_name (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ObjectInfo
    """

    return sync_detailed(
        client=client,
        container=container,
        object_name=object_name,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    container: str,
    object_name: str,
) -> Response[HTTPValidationError | ObjectInfo]:
    """Get File Info

     Get metadata for a stored object (maps to CloudStorageClient.get_file_info).

    Args:
        container (str):
        object_name (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HTTPValidationError | ObjectInfo]
    """

    kwargs = _get_kwargs(
        container=container,
        object_name=object_name,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    container: str,
    object_name: str,
) -> HTTPValidationError | ObjectInfo | None:
    """Get File Info

     Get metadata for a stored object (maps to CloudStorageClient.get_file_info).

    Args:
        container (str):
        object_name (str):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HTTPValidationError | ObjectInfo
    """

    return (
        await asyncio_detailed(
            client=client,
            container=container,
            object_name=object_name,
        )
    ).parsed
