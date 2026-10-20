// Role assignments for the app's managed identity (docs/02). Keyless everywhere.
param principalId string
param foundryName string
param eventHubNamespaceName string
param keyVaultName string
param registryName string
param cosmosAccountName string

// Built-in role definition ids.
var roleOpenAiUser = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
var roleCognitiveServicesUser = 'a97b65f3-24c7-4388-baec-2e87135dc908'
var roleAzureAiUser = '53ca6127-db72-4b80-b1b0-d745d6d5456d'
var roleEventHubsDataOwner = 'f526a384-b230-433a-b45c-95f59c4a2dec'
var roleKeyVaultSecretsUser = '4633458b-17de-408a-b874-0445c86b69e6'
var roleAcrPull = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
// Cosmos data-plane role, not an Azure RBAC role.
var cosmosDataContributor = '00000000-0000-0000-0000-000000000002'

resource foundry 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: foundryName
}
resource eventHubs 'Microsoft.EventHub/namespaces@2024-01-01' existing = {
  name: eventHubNamespaceName
}
resource vault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}
resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: registryName
}
resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' existing = {
  name: cosmosAccountName
}

resource foundryRoles 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for r in [roleOpenAiUser, roleCognitiveServicesUser, roleAzureAiUser]: {
    name: guid(foundry.id, principalId, r)
    scope: foundry
    properties: {
      principalId: principalId
      principalType: 'ServicePrincipal'
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', r)
    }
  }
]

resource eventHubsRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(eventHubs.id, principalId, roleEventHubsDataOwner)
  scope: eventHubs
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleEventHubsDataOwner)
  }
}

resource vaultRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(vault.id, principalId, roleKeyVaultSecretsUser)
  scope: vault
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleKeyVaultSecretsUser)
  }
}

resource registryRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, principalId, roleAcrPull)
  scope: registry
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleAcrPull)
  }
}

resource cosmosRole 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = {
  parent: cosmos
  name: guid(cosmos.id, principalId, cosmosDataContributor)
  properties: {
    principalId: principalId
    roleDefinitionId: '${cosmos.id}/sqlRoleDefinitions/${cosmosDataContributor}'
    scope: cosmos.id
  }
}
