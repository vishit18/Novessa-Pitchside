// The other deployable pieces of the system, beside the `api` gateway (docs/01):
//   mcp  - the Match Intelligence MCP server (streamable HTTP on /mcp)
//   a2a  - the Recap Editor as its own A2A agent (agent card at /.well-known/agent-card.json)
//   job  - a manual Container Apps Job that warms the overlay-text cache into Cosmos
// All three run the same image as the gateway with a different start command, so there is one
// build and nothing here changes what the gateway does. Scale to zero when idle.
param location string
@minLength(13)
@description('Unique suffix from main.bicep, always 13 characters.')
param token string
param tags object
param environmentId string
param environmentDomain string
param identityId string
param identityClientId string
param registryLoginServer string
param appInsightsSecretUri string
param mcpImage string
param a2aImage string
@description('Image for the cache-warming job (the gateway image).')
param jobImage string
@description('Plain environment variables, the same object the api gets.')
param env object

var envList = [for item in items(env): { name: item.key, value: string(item.value) }]
var jobEnvList = [for item in items(union(env, { STORE: 'cosmos' })): { name: item.key, value: string(item.value) }]
var identity = {
  type: 'UserAssigned'
  userAssignedIdentities: { '${identityId}': {} }
}
var registries = [{ server: registryLoginServer, identity: identityId }]
var secrets = [
  { name: 'appinsights-connection-string', keyVaultUrl: appInsightsSecretUri, identity: identityId }
]
var commonEnv = [
  { name: 'AZURE_CLIENT_ID', value: identityClientId }
  { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', secretRef: 'appinsights-connection-string' }
]

resource mcp 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-mcp-${token}'
  location: location
  tags: union(tags, { 'azd-service-name': 'mcp' })
  identity: identity
  properties: {
    managedEnvironmentId: environmentId
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: { external: true, targetPort: 8001, transport: 'auto', allowInsecure: false }
      registries: registries
      secrets: secrets
    }
    template: {
      containers: [
        {
          name: 'mcp'
          image: mcpImage
          command: ['python', '-m', 'backend.mcp_server.server']
          args: ['--http', '--port', '8001']
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: commonEnv
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 2
        rules: [{ name: 'http', http: { metadata: { concurrentRequests: '20' } } }]
      }
    }
  }
}

resource a2a 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-a2a-${token}'
  location: location
  tags: union(tags, { 'azd-service-name': 'a2a' })
  identity: identity
  properties: {
    managedEnvironmentId: environmentId
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: { external: true, targetPort: 8002, transport: 'auto', allowInsecure: false }
      registries: registries
      secrets: secrets
    }
    template: {
      containers: [
        {
          name: 'a2a'
          image: a2aImage
          command: ['uvicorn']
          args: ['backend.a2a.app:app', '--host', '0.0.0.0', '--port', '8002']
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: concat(envList, commonEnv, [
            { name: 'PUBLIC_BASE_URL', value: 'https://ca-a2a-${token}.${environmentDomain}' }
          ])
          probes: [
            {
              type: 'Liveness'
              httpGet: { path: '/health', port: 8002 }
              initialDelaySeconds: 20
              periodSeconds: 30
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 2
        rules: [{ name: 'http', http: { metadata: { concurrentRequests: '10' } } }]
      }
    }
  }
}

// Run by hand: az containerapp job start -g <rg> -n job-warm-<token>
resource warm 'Microsoft.App/jobs@2024-03-01' = {
  name: 'job-warm-${token}'
  location: location
  tags: tags
  identity: identity
  properties: {
    environmentId: environmentId
    configuration: {
      triggerType: 'Manual'
      replicaTimeout: 1800
      replicaRetryLimit: 0
      manualTriggerConfig: { parallelism: 1, replicaCompletionCount: 1 }
      registries: registries
      secrets: secrets
    }
    template: {
      containers: [
        {
          name: 'warm'
          image: jobImage
          command: ['python', '-m', 'scripts.warm_overlay_text']
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: concat(jobEnvList, commonEnv)
        }
      ]
    }
  }
}

output mcpUri string = 'https://${mcp.properties.configuration.ingress.fqdn}/mcp'
output a2aUri string = 'https://${a2a.properties.configuration.ingress.fqdn}'
output warmJobName string = warm.name
