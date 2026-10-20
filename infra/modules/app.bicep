// Container Apps environment + the `api` gateway, and the Static Web App for the frontend.
param location string
param swaLocation string
@minLength(13)
@description('Unique suffix from main.bicep, always 13 characters.')
param token string
param tags object
param logAnalyticsWorkspaceName string
param identityId string
param identityClientId string
param registryLoginServer string
param appInsightsSecretUri string
param apiImage string
param apiMinReplicas int
@description('Plain (non-secret) environment variables for the api container.')
param env object

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: logAnalyticsWorkspaceName
}

// Static Web App (free) for the React frontend. azd deploys the build to it.
resource web 'Microsoft.Web/staticSites@2023-12-01' = {
  name: 'swa-${token}'
  location: swaLocation
  tags: union(tags, { 'azd-service-name': 'web' })
  sku: { name: 'Free', tier: 'Free' }
  properties: {}
}

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'cae-${token}'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: workspace.properties.customerId
        sharedKey: workspace.listKeys().primarySharedKey
      }
    }
  }
}

var envList = [for item in items(env): { name: item.key, value: string(item.value) }]

resource api 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-api-${token}'
  location: location
  tags: union(tags, { 'azd-service-name': 'api' })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identityId}': {} }
  }
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        allowInsecure: false
      }
      registries: [
        { server: registryLoginServer, identity: identityId }
      ]
      secrets: [
        { name: 'appinsights-connection-string', keyVaultUrl: appInsightsSecretUri, identity: identityId }
      ]
    }
    template: {
      containers: [
        {
          name: 'api'
          image: apiImage
          resources: { cpu: json('1.0'), memory: '2Gi' }
          env: concat(envList, [
            { name: 'AZURE_CLIENT_ID', value: identityClientId }
            { name: 'CORS_ORIGINS', value: 'https://${web.properties.defaultHostname}' }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', secretRef: 'appinsights-connection-string' }
          ])
          probes: [
            {
              type: 'Liveness'
              httpGet: { path: '/health', port: 8000 }
              initialDelaySeconds: 20
              periodSeconds: 30
            }
          ]
        }
      ]
      scale: {
        minReplicas: apiMinReplicas
        maxReplicas: 3
        rules: [
          { name: 'http', http: { metadata: { concurrentRequests: '30' } } }
        ]
      }
    }
  }
}

output apiUri string = 'https://${api.properties.configuration.ingress.fqdn}'
output webUri string = 'https://${web.properties.defaultHostname}'
