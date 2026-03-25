# cloud_storage_adapter

Adapter package for HW2 that implements `cloud_storage_client_api.Client` while delegating to the remote service through `cloud_storage_service_api_client`.

Purpose: keep consumer code unchanged whether using local implementation (`s3_client_impl`) or remote service (`cloud_storage_adapter`).
