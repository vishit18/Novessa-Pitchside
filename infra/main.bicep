// Novessa Pitchside infrastructure (docs/02). Deploys into the existing resource group.
// Foundry already exists (NovessaPitchside1); this only references it and grants access.
targetScope = 'resourceGroup'

@minLength(1)
@maxLength(20)
@description('azd environment name. Used to make resource names unique.')
param environmentName string

@description('Region for everything except the static web app.')
param location string = resourceGroup().location

@description('Cosmos DB sometimes refuses new accounts in a busy region; set this to deploy it elsewhere.')
param cosmosLocation string = location

@description('Static Web Apps are only offered in a few regions.')
param swaLocation string = 'westus2'

@description('The existing Foundry (AI Services) resource.')
param foundryAccountName string = 'NovessaPitchside1'

@description('Project endpoint, e.g. https://<resource>.services.ai.azure.com/api/projects/<project>.')
param foundryProjectEndpoint string

param foundryDeploymentFast string = 'chat-fast'
param foundryDeploymentStrong string = 'chat-strong'

@description('Keep at 1 from 26 Oct to 11 Nov so judges never hit a cold start; 0 otherwise.')
@allowed(['0', '1', '2', '3'])
param apiMinReplicas string = '0'

@description('Placeholder until azd deploys the real image.')
param apiImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

var token = toLower(uniqueString(subscription().id, resourceGroup().id, environmentName))
var tags = {
  'azd-env-name': environmentName
  project: 'novessa-pitchside'
}

module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  params: { location: location, token: token, tags: tags }
}

module platform 'modules/platform.bicep' = {
  name: 'platform'
  params: {
    location: location
    token: token
    tags: tags
    appInsightsConnectionString: monitoring.outputs.appInsightsConnectionString
  }
}

module data 'modules/data.bicep' = {
  name: 'data'
  params: { location: location, cosmosLocation: cosmosLocation, token: token, tags: tags }
}

resource foundry 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: foundryAccountName
}

module roles 'modules/roles.bicep' = {
  name: 'roles'
  params: {
    principalId: platform.outputs.identityPrincipalId
    foundryName: foundry.name
    eventHubNamespaceName: data.outputs.eventHubNamespaceName
    keyVaultName: platform.outputs.keyVaultName
    registryName: platform.outputs.registryName
    cosmosAccountName: data.outputs.cosmosAccountName
  }
}

module storage 'modules/storage.bicep' = {
  name: 'storage'
  params: { location: location, token: token, tags: tags }
}

module app 'modules/app.bicep' = {
  name: 'app'
  dependsOn: [roles]
  params: {
    location: location
    swaLocation: swaLocation
    token: token
    tags: tags
    logAnalyticsWorkspaceName: monitoring.outputs.workspaceName
    identityId: platform.outputs.identityId
    identityClientId: platform.outputs.identityClientId
    registryLoginServer: platform.outputs.registryLoginServer
    appInsightsSecretUri: platform.outputs.appInsightsSecretUri
    apiImage: apiImage
    apiMinReplicas: int(apiMinReplicas)
    env: {
      FOUNDRY_PROJECT_ENDPOINT: foundryProjectEndpoint
      // Token (Entra) auth works on the cognitiveservices.azure.com host, not openai.azure.com.
      FOUNDRY_OPENAI_ENDPOINT: foundry.properties.endpoint
      FOUNDRY_DEPLOYMENT_FAST: foundryDeploymentFast
      FOUNDRY_DEPLOYMENT_STRONG: foundryDeploymentStrong
      CONTENT_SAFETY_ENDPOINT: foundry.properties.endpoint
      TRANSLATOR_ENDPOINT: foundry.properties.endpoint
      SPEECH_REGION: foundry.location
      EVENTHUB_FQDN: '${data.outputs.eventHubNamespaceName}.servicebus.windows.net'
      EVENTHUB_NAME: data.outputs.eventHubName
      COSMOS_ENDPOINT: data.outputs.cosmosEndpoint
      COSMOS_DATABASE: data.outputs.cosmosDatabase
      REAL_VIDEO_BASE_URL: storage.outputs.footageBaseUrl
      EVENT_BUS: 'memory'
      STORE: 'local'
      AGENT_CACHE: 'on'
    }
  }
}

output AZURE_LOCATION string = location
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = platform.outputs.registryLoginServer
output AZURE_CONTAINER_REGISTRY_NAME string = platform.outputs.registryName
output API_URI string = app.outputs.apiUri
output WEB_URI string = app.outputs.webUri
output APPLICATIONINSIGHTS_NAME string = monitoring.outputs.appInsightsName
output STORAGE_ACCOUNT_NAME string = storage.outputs.storageAccountName
output REAL_VIDEO_BASE_URL string = storage.outputs.footageBaseUrl
