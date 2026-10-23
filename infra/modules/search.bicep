// Azure AI Search, free tier: the league knowledge index that grounds Ask the Analyst (item 7).
// Keyless only: API keys are switched off, so every caller needs a data-plane role.
// The free tier costs nothing, but a subscription can hold only one free search service.
param location string
@minLength(13)
@description('Unique suffix from main.bicep, always 13 characters.')
param token string
param tags object

@description('The app\'s managed identity. Gets read access to the index.')
param appPrincipalId string

@description('Optional: a person who runs scripts/index_knowledge.py. Gets index admin and upload rights.')
param developerPrincipalId string = ''

// Built-in role definition ids (learn.microsoft.com/azure/search/search-security-rbac).
var roleSearchIndexDataReader = '1407120a-92aa-4202-b7e9-c0e197c71c8f'
var roleSearchIndexDataContributor = '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
var roleSearchServiceContributor = '7ca78c08-252a-4471-8644-bb5ff32d4ba0'

resource search 'Microsoft.Search/searchServices@2025-05-01' = {
  name: 'srch-${token}'
  location: location
  tags: tags
  sku: { name: 'free' }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'Default'
    publicNetworkAccess: 'enabled'
    disableLocalAuth: true
  }
}

resource appReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(search.id, appPrincipalId, roleSearchIndexDataReader)
  scope: search
  properties: {
    principalId: appPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleSearchIndexDataReader)
  }
}

resource developerRoles 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for r in (empty(developerPrincipalId) ? [] : [roleSearchServiceContributor, roleSearchIndexDataContributor]): {
    name: guid(search.id, developerPrincipalId, r)
    scope: search
    properties: {
      principalId: developerPrincipalId
      principalType: 'User'
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', r)
    }
  }
]

output name string = search.name
output endpoint string = 'https://${search.name}.search.windows.net'
