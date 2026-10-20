// Event Hubs (the event bus) and Cosmos DB for NoSQL (matches, moments, profiles, cache).
param location string
@description('Region for the Cosmos DB account.')
param cosmosLocation string = location
@minLength(13)
@description('Unique suffix from main.bicep, always 13 characters.')
param token string
param tags object

@description('Cosmos DB free tier gives 1000 RU/s and 25 GB, one account per subscription.')
param cosmosFreeTier bool = true

resource eventHubs 'Microsoft.EventHub/namespaces@2024-01-01' = {
  name: 'evhns-${token}'
  location: location
  tags: tags
  sku: { name: 'Basic', tier: 'Basic', capacity: 1 }
  properties: {
    disableLocalAuth: true
    minimumTlsVersion: '1.2'
  }
}

resource matchEvents 'Microsoft.EventHub/namespaces/eventhubs@2024-01-01' = {
  parent: eventHubs
  name: 'match-events'
  properties: {
    partitionCount: 2
    messageRetentionInDays: 1
  }
}

resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = {
  name: 'cosmos-${token}'
  location: cosmosLocation
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    enableFreeTier: cosmosFreeTier
    disableLocalAuth: true
    consistencyPolicy: { defaultConsistencyLevel: 'Session' }
    locations: [
      { locationName: cosmosLocation, failoverPriority: 0, isZoneRedundant: false }
    ]
  }
}

resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-05-15' = {
  parent: cosmos
  name: 'pitchside'
  properties: {
    resource: { id: 'pitchside' }
    // One shared 1000 RU/s for all containers, which is exactly the free allowance.
    options: { throughput: 1000 }
  }
}

var containers = [
  { name: 'matches', key: '/match_id' }
  { name: 'events', key: '/match_id' }
  { name: 'moments', key: '/match_id' }
  { name: 'profiles', key: '/viewer_id' }
  { name: 'agent_cache', key: '/cache_key' }
]

resource containerResources 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = [
  for c in containers: {
    parent: database
    name: c.name
    properties: {
      resource: {
        id: c.name
        partitionKey: { paths: [c.key], kind: 'Hash' }
      }
    }
  }
]

output eventHubNamespaceName string = eventHubs.name
output eventHubName string = matchEvents.name
output cosmosAccountName string = cosmos.name
output cosmosEndpoint string = cosmos.properties.documentEndpoint
output cosmosDatabase string = database.name
