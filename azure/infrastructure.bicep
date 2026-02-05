// =============================================================================
// TMATH Azure Infrastructure - Bicep Template
// =============================================================================
// Deploy với: az deployment group create --resource-group tmath-rg --template-file infrastructure.bicep
// =============================================================================

@description('Location for all resources')
param location string = resourceGroup().location

@description('Base name for all resources')
param baseName string = 'tmath'

@description('PostgreSQL admin username')
param dbAdminUsername string = 'tmathdbadmin'

@secure()
@description('PostgreSQL admin password')
param dbAdminPassword string

@secure()
@description('Django secret key')
param djangoSecretKey string

@description('Container image to deploy')
param containerImage string

@secure()
@description('ACR password')
param acrPassword string

@description('ACR username')
param acrUsername string

@description('ACR login server')
param acrLoginServer string

// =============================================================================
// VARIABLES
// =============================================================================

var containerAppEnvName = '${baseName}-env'
var containerAppWebName = '${baseName}-web'
var containerAppCeleryName = '${baseName}-celery'
var postgresServerName = '${baseName}-db-${uniqueString(resourceGroup().id)}'
var redisName = '${baseName}-redis-${uniqueString(resourceGroup().id)}'
var logAnalyticsName = '${baseName}-logs'

// =============================================================================
// LOG ANALYTICS WORKSPACE
// =============================================================================

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: logAnalyticsName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// =============================================================================
// POSTGRESQL FLEXIBLE SERVER
// =============================================================================

resource postgresServer 'Microsoft.DBforPostgreSQL/flexibleServers@2022-12-01' = {
  name: postgresServerName
  location: location
  sku: {
    name: 'Standard_B1ms'
    tier: 'Burstable'
  }
  properties: {
    version: '15'
    administratorLogin: dbAdminUsername
    administratorLoginPassword: dbAdminPassword
    storage: {
      storageSizeGB: 32
    }
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: {
      mode: 'Disabled'
    }
  }
}

resource postgresDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2022-12-01' = {
  parent: postgresServer
  name: baseName
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

resource postgresFirewallRule 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2022-12-01' = {
  parent: postgresServer
  name: 'AllowAllAzureServicesAndResourcesWithinAzureIps'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

// =============================================================================
// REDIS CACHE
// =============================================================================

resource redis 'Microsoft.Cache/redis@2023-08-01' = {
  name: redisName
  location: location
  properties: {
    sku: {
      name: 'Basic'
      family: 'C'
      capacity: 0
    }
    enableNonSslPort: true
    minimumTlsVersion: '1.2'
  }
}

// =============================================================================
// CONTAINER APPS ENVIRONMENT
// =============================================================================

resource containerAppEnv 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: containerAppEnvName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

// =============================================================================
// CONTAINER APP - WEB
// =============================================================================

var databaseUrl = 'postgres://${dbAdminUsername}:${dbAdminPassword}@${postgresServer.properties.fullyQualifiedDomainName}:5432/${baseName}?sslmode=require'
var redisUrl = 'redis://:${redis.listKeys().primaryKey}@${redis.properties.hostName}:6379/0'
var celeryBrokerUrl = 'redis://:${redis.listKeys().primaryKey}@${redis.properties.hostName}:6379/1'

resource containerAppWeb 'Microsoft.App/containerApps@2023-05-01' = {
  name: containerAppWebName
  location: location
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'http'
        allowInsecure: false
      }
      registries: [
        {
          server: acrLoginServer
          username: acrUsername
          passwordSecretRef: 'acr-password'
        }
      ]
      secrets: [
        {
          name: 'acr-password'
          value: acrPassword
        }
        {
          name: 'django-secret-key'
          value: djangoSecretKey
        }
        {
          name: 'database-url'
          value: databaseUrl
        }
        {
          name: 'redis-url'
          value: redisUrl
        }
        {
          name: 'celery-broker-url'
          value: celeryBrokerUrl
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'tmath-web'
          image: containerImage
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            { name: 'DEBUG', value: 'False' }
            { name: 'SECRET_KEY', secretRef: 'django-secret-key' }
            { name: 'DATABASE_URL', secretRef: 'database-url' }
            { name: 'REDIS_URL', secretRef: 'redis-url' }
            { name: 'CELERY_BROKER_URL', secretRef: 'celery-broker-url' }
            { name: 'ALLOWED_HOSTS', value: '*' }
          ]
          command: [
            'sh'
            '-c'
            'python manage.py migrate --noinput && gunicorn --bind 0.0.0.0:8000 --workers 2 --threads 4 --worker-class gthread --timeout 120 tmath.wsgi:application'
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/health/'
                port: 8000
              }
              initialDelaySeconds: 30
              periodSeconds: 30
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/health/'
                port: 8000
              }
              initialDelaySeconds: 10
              periodSeconds: 10
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 5
        rules: [
          {
            name: 'http-rule'
            http: {
              metadata: {
                concurrentRequests: '100'
              }
            }
          }
        ]
      }
    }
  }
}

// =============================================================================
// CONTAINER APP - CELERY WORKER
// =============================================================================

resource containerAppCelery 'Microsoft.App/containerApps@2023-05-01' = {
  name: containerAppCeleryName
  location: location
  properties: {
    managedEnvironmentId: containerAppEnv.id
    configuration: {
      registries: [
        {
          server: acrLoginServer
          username: acrUsername
          passwordSecretRef: 'acr-password'
        }
      ]
      secrets: [
        {
          name: 'acr-password'
          value: acrPassword
        }
        {
          name: 'django-secret-key'
          value: djangoSecretKey
        }
        {
          name: 'database-url'
          value: databaseUrl
        }
        {
          name: 'redis-url'
          value: redisUrl
        }
        {
          name: 'celery-broker-url'
          value: celeryBrokerUrl
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'tmath-celery'
          image: containerImage
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            { name: 'DEBUG', value: 'False' }
            { name: 'SECRET_KEY', secretRef: 'django-secret-key' }
            { name: 'DATABASE_URL', secretRef: 'database-url' }
            { name: 'REDIS_URL', secretRef: 'redis-url' }
            { name: 'CELERY_BROKER_URL', secretRef: 'celery-broker-url' }
          ]
          command: [
            'celery'
            '-A'
            'tmath'
            'worker'
            '-l'
            'info'
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 3
      }
    }
  }
}

// =============================================================================
// OUTPUTS
// =============================================================================

output webUrl string = 'https://${containerAppWeb.properties.configuration.ingress.fqdn}'
output postgresHost string = postgresServer.properties.fullyQualifiedDomainName
output redisHost string = redis.properties.hostName
