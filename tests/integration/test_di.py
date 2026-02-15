def test_get_client_returns_aws_impl():
    import cloud_storage_client_aws_impl  # triggers DI

    from cloud_storage_client_api.client import get_client
    from cloud_storage_client_aws_impl.client import S3CloudStorageClient

    client = get_client()

    assert isinstance(client, S3CloudStorageClient)
