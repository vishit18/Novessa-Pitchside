// Operational monitoring (docs/02 step 4): availability tests on the site and the API, alerts that
// email when something is wrong, and a workbook that shows how the system is doing.
//   - standard availability tests: the web app, the api /health, and a real read (/matches)
//   - an alert when a test fails from two or more locations
//   - an alert on a burst of 5xx from the api
//   - an alert when model calls start failing (not the chaos switch, which is "killed")
//   - a workbook: availability, latency, status codes, agent calls, model calls, rate limiting
param location string
@minLength(13)
@description('Unique suffix from main.bicep, always 13 characters.')
param token string
param tags object
param appInsightsName string
param workspaceName string
param apiAppName string
@description('Public URLs to probe, with no trailing slash.')
param webUrl string
param apiUrl string
@description('Where alert emails go.')
param alertEmail string

resource appInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: appInsightsName
}
resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: workspaceName
}
resource api 'Microsoft.App/containerApps@2024-03-01' existing = {
  name: apiAppName
}

resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: 'ag-pitchside-${token}'
  location: 'global'
  tags: tags
  properties: {
    groupShortName: 'pitchside'
    enabled: true
    emailReceivers: [
      { name: 'owner', emailAddress: alertEmail, useCommonAlertSchema: true }
    ]
  }
}

// Every 15 minutes from three regions. The api scales to zero, so allow a cold start.
var probes = [
  { key: 'web', name: 'Web app', url: '${webUrl}/' }
  { key: 'api', name: 'API health', url: '${apiUrl}/health' }
  { key: 'matches', name: 'API matches', url: '${apiUrl}/matches' }
]
var testLocations = [
  { Id: 'emea-nl-ams-azr' }
  { Id: 'emea-gb-db3-azr' }
  { Id: 'us-va-ash-azr' }
]

resource tests 'Microsoft.Insights/webtests@2022-06-15' = [
  for p in probes: {
    name: 'wt-${p.key}-${token}'
    location: location
    tags: union(tags, { 'hidden-link:${appInsights.id}': 'Resource' })
    kind: 'standard'
    properties: {
      Kind: 'standard'
      SyntheticMonitorId: 'wt-${p.key}-${token}'
      Name: 'Pitchside: ${p.name}'
      Enabled: true
      Frequency: 900
      Timeout: 120
      RetryEnabled: true
      Locations: testLocations
      Request: { RequestUrl: p.url, HttpVerb: 'GET', ParseDependentRequests: false }
      ValidationRules: { ExpectedHttpStatusCode: 200, SSLCheck: true, SSLCertRemainingLifetimeCheck: 7 }
    }
  }
]

resource availabilityAlerts 'Microsoft.Insights/metricAlerts@2018-03-01' = [
  for (p, i) in probes: {
    name: 'alert-down-${p.key}-${token}'
    location: 'global'
    tags: union(tags, {
      'hidden-link:${appInsights.id}': 'Resource'
      'hidden-link:${tests[i].id}': 'Resource'
    })
    properties: {
      description: '${p.name} failed from two or more locations.'
      severity: 1
      enabled: true
      scopes: [tests[i].id, appInsights.id]
      evaluationFrequency: 'PT5M'
      windowSize: 'PT15M'
      criteria: {
        'odata.type': 'Microsoft.Azure.Monitor.WebtestLocationAvailabilityCriteria'
        webTestId: tests[i].id
        componentId: appInsights.id
        failedLocationCount: 2
      }
      actions: [{ actionGroupId: actionGroup.id }]
    }
  }
]

resource errors5xx 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'alert-5xx-${token}'
  location: 'global'
  tags: tags
  properties: {
    description: 'The api returned more than 5 server errors in 5 minutes.'
    severity: 2
    enabled: true
    scopes: [api.id]
    evaluationFrequency: 'PT1M'
    windowSize: 'PT5M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'errors'
          metricName: 'Requests'
          metricNamespace: 'microsoft.app/containerapps'
          dimensions: [{ name: 'statusCodeCategory', operator: 'Include', values: ['5xx'] }]
          operator: 'GreaterThan'
          threshold: 5
          timeAggregation: 'Total'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: [{ actionGroupId: actionGroup.id }]
  }
}

resource modelFailures 'Microsoft.Insights/scheduledQueryRules@2023-03-15-preview' = {
  name: 'alert-model-failures-${token}'
  location: location
  tags: tags
  properties: {
    displayName: 'Pitchside: model calls failing'
    description: 'More than 10 agent model calls failed in 15 minutes (the chaos switch is not counted).'
    severity: 2
    enabled: true
    scopes: [workspace.id]
    evaluationFrequency: 'PT15M'
    windowSize: 'PT15M'
    criteria: {
      allOf: [
        {
          query: 'AppDependencies | where Name startswith "agent." | where tostring(Properties["agent.outcome"]) == "failed"'
          timeAggregation: 'Count'
          operator: 'GreaterThan'
          threshold: 10
          failingPeriods: { numberOfEvaluationPeriods: 1, minFailingPeriodsToAlert: 1 }
        }
      ]
    }
    actions: { actionGroups: [actionGroup.id] }
  }
}

// Workbook. Each tile is a log query over the workspace behind Application Insights.
var tile = {
  version: 'KqlItem/1.0'
  queryType: 0
  resourceType: 'microsoft.operationalinsights/workspaces'
  crossComponentResources: [workspace.id]
  timeContext: { durationMs: 86400000 }
  size: 1
}
var workbookItems = [
  {
    type: 1
    name: 'intro'
    content: {
      json: '## Pitchside operations\nIs it up, how fast is it, what are the agents doing, and is anyone leaning on it. Last 24 hours by default.'
    }
  }
  {
    type: 3
    name: 'availability'
    content: union(tile, {
      title: 'Availability by probe (%)'
      query: 'AppAvailabilityResults | summarize availability = round(100.0 * avg(todouble(Success)), 1) by Name, bin(TimeGenerated, 1h) | order by TimeGenerated asc'
      visualization: 'timechart'
    })
  }
  {
    type: 3
    name: 'latency'
    content: union(tile, {
      title: 'API latency, ms (p50 and p95)'
      query: 'AppRequests | where Name !has "health" | summarize p50 = percentile(DurationMs, 50), p95 = percentile(DurationMs, 95) by bin(TimeGenerated, 30m) | order by TimeGenerated asc'
      visualization: 'timechart'
    })
  }
  {
    type: 3
    name: 'status'
    content: union(tile, {
      title: 'Requests by status code'
      query: 'AppRequests | summarize requests = count() by ResultCode | order by requests desc'
      visualization: 'barchart'
    })
  }
  {
    type: 3
    name: 'agents'
    content: union(tile, {
      title: 'Agent model calls: count, outcome, p95 latency (ms)'
      query: 'AppDependencies | where Name startswith "agent." | extend agent = tostring(Properties["agent.name"]), outcome = tostring(Properties["agent.outcome"]) | summarize calls = count(), p95_ms = round(percentile(DurationMs, 95)) by agent, outcome | order by calls desc'
      visualization: 'table'
    })
  }
  {
    type: 3
    name: 'models'
    content: union(tile, {
      title: 'Calls to each model deployment, per hour'
      query: 'AppDependencies | where Name has "/chat/completions" | summarize calls = count() by Name, bin(TimeGenerated, 1h) | order by TimeGenerated asc'
      visualization: 'timechart'
    })
  }
  {
    type: 3
    name: 'throttled'
    content: union(tile, {
      title: 'Requests turned away by the rate limit (429)'
      query: 'AppRequests | where ResultCode == "429" | summarize throttled = count() by Name, bin(TimeGenerated, 1h) | order by TimeGenerated asc'
      visualization: 'table'
    })
  }
]

resource workbook 'Microsoft.Insights/workbooks@2023-06-01' = {
  name: guid(resourceGroup().id, 'pitchside-operations')
  location: location
  tags: tags
  kind: 'shared'
  properties: {
    displayName: 'Pitchside operations'
    category: 'workbook'
    sourceId: appInsights.id
    serializedData: string({
      version: 'Notebook/1.0'
      items: workbookItems
      fallbackResourceIds: [workspace.id]
    })
  }
}

output actionGroupName string = actionGroup.name
output workbookId string = workbook.id
