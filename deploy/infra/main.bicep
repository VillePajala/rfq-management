// Tender Intelligence — top-level Bicep template
//
// Deploys the full infrastructure for the nightly tender scraper:
//   - Container Apps Environment + Job (scraper)
//   - Container Apps Job (reply-tracker, planned)
//   - Azure Container Registry (Basic)
//   - Key Vault (secrets, MI-accessed)
//   - Blob Storage (ZIP staging container, scanned by Defender)
//   - Azure SQL Database (Serverless GP, auto-pause) — see § 17.4
//   - Log Analytics + Application Insights
//   - Defender for Storage on the staging container
//   - Static Web App (hosts the koontinäkymä)
//
// SKELETON — modules referenced below have TODO markers; fill them in
// during the Azure-team build phase. Spec: docs/project_spec.md § 5.

targetScope = 'resourceGroup'

@description('Short environment name — e.g. dev, staging, prod')
param env string = 'dev'

@description('Azure region — verified working: northeurope (Cloudflare bypass confirmed 2026-04-23)')
param location string = 'northeurope'

@description('Container image reference (ACR or other registry). E.g. acrname.azurecr.io/tender-intelligence:sha-abc123')
param containerImage string

@description('Email address that receives failure alerts')
param alertEmail string

@description('Existing Log Analytics workspace ID (empty = create new)')
param logAnalyticsWorkspaceId string = ''

// -----------------------------------------------------------------------
// TODO modules — to be implemented by the Azure team
// -----------------------------------------------------------------------

// module containerRegistry 'modules/container_registry.bicep' = { ... }
// module keyVault         'modules/key_vault.bicep'           = { ... }
// module storage          'modules/storage.bicep'             = { ... }
// module azureSql         'modules/azure_sql.bicep'           = { ... }   // Serverless GP, auto-pause; tenders/awards/claims/history; see docs/project_spec.md § 17.4
// module logAnalytics     'modules/log_analytics.bicep'       = { ... }
// module appInsights      'modules/app_insights.bicep'        = { ... }
// module containerAppsEnv 'modules/container_apps_env.bicep'  = { ... }
// module scraperJob       'modules/container_app_job.bicep'   = { name: 'scraper-job' ... }
// module replyTrackerJob  'modules/container_app_job.bicep'   = { name: 'reply-tracker-job' ... }
// module dashboard        'modules/static_web_app.bicep'      = { ... }
// module defender         'modules/defender_storage.bicep'    = { ... }
// module alerting         'modules/alerts.bicep'              = { ... }

output todo string = 'Implement modules in deploy/infra/modules/'
