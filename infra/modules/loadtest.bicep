// Azure Load Testing resource (docs/LOAD_TEST.md). Billed by virtual-user hour, so it costs
// nothing while idle. The test itself is in loadtest/.
param location string
@minLength(13)
@description('Unique suffix from main.bicep, always 13 characters.')
param token string
param tags object

resource loadTest 'Microsoft.LoadTestService/loadTests@2022-12-01' = {
  name: 'lt-${token}'
  location: location
  tags: tags
  identity: { type: 'SystemAssigned' }
  properties: {}
}

output loadTestName string = loadTest.name
output dataPlaneUri string = loadTest.properties.dataPlaneURI
