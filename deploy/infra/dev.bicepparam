// Personal-Azure simulation parameters (Phase 1a — see docs/project_spec.md § 5.3.1)
using './main.bicep'

param env = 'dev'
param location = 'northeurope'
param containerImage = 'YOUR_ACR.azurecr.io/tender-intelligence:latest'
param alertEmail = 'YOUR_EMAIL@example.com'
