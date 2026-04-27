// CGI Public production parameters
using './main.bicep'

param env = 'prod'
param location = 'northeurope'
param containerImage = 'CGI_ACR.azurecr.io/tender-intelligence:latest'
param alertEmail = 'tender-intelligence-alerts@cgi.com'
