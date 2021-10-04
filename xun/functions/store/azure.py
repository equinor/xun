from .store import Store


class Azure(Store):
    def __init__(self,
                 account_name,
                 container_name,
                 account_url=None,
                 credentials=None):
        self.account_name = account_name
        self.account_url = (account_url if account_url is not None else
                            f'https://{account_name}.blob.core.windows.net/')
        self.container_name = container_name

        if credentials is not None:
            raise NotImplementedError('Credentials not implemented')
        self.credentials = azure.identity.AzureCliCredential()

    @property
    def blob_service(self):
        if not hasattr(self, '_blob_service'):
            self._blob_service = azure.storage.blob.BlobServiceClient(
                self.account_url, self.credentials)
        return self._blob_service

    @property
    def container(self):
        if not hasattr(self, '_container'):
            self._container = self.blob_service.get_container_client(
                self.container_name)
        return self._container

    def __contains__(self, key):
        raise NotImplementedError

    def load(self, key):
        b64 = key_hash_str(key)
        key_str = serialization.dumps(key)

        value_str = self.container.download_blob(b64).content_as_text()

        return serialization.loads(value_str)


    def tags(self, key):
        raise NotImplementedError

    def store(self, key, value, **tags):
        b64 = key_hash_str(key)

        key_str = serialization.dumps(key)
        value_str = serialization.dumps(value)

        self.container.upload_blob(b64 + '.key', key_str, tags=tags)
        self.container.upload_blob(b64 + '.value', value_str, tags=tags)

    def __getstate__(self):
        return self.account_name, self.container_name

    def __setstate__(self, state):
        self.account_name = state[0]
        self.container_name = state[1]
