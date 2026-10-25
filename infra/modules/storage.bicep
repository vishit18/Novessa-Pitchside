// Blob storage for the real-footage clip (docs/06). The clip is the redacted, openly licensed
// SoccerTrack v2 excerpt (CC BY 4.0), so the `footage` container allows anonymous read. Nothing
// else goes in this account. Uploads use Entra (shared keys are off).
param location string
@minLength(13)
@description('Unique suffix from main.bicep, always 13 characters.')
param token string
param tags object
@description('Origins allowed to fetch the clip from a browser, e.g. the static web app.')
param corsOrigins array = []

resource account 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: 'st${token}'
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: true
    allowSharedKeyAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

resource blobs 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: account
  name: 'default'
  properties: {
    // Without this the account answers anonymous requests as the 2009 API: no Accept-Ranges
    // header, so browsers refuse to seek in the clip.
    defaultServiceVersion: '2022-11-02'
    cors: {
      corsRules: [
        {
          allowedOrigins: empty(corsOrigins) ? ['*'] : corsOrigins
          allowedMethods: ['GET', 'HEAD']
          allowedHeaders: ['*']
          exposedHeaders: ['Content-Length', 'Content-Range', 'Accept-Ranges']
          maxAgeInSeconds: 3600
        }
      ]
    }
  }
}

resource footage 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobs
  name: 'footage'
  properties: { publicAccess: 'Blob' }
}

output storageAccountName string = account.name
output footageBaseUrl string = '${account.properties.primaryEndpoints.blob}footage'
