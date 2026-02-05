# =============================================================================
# TMATH Azure Container Apps Deployment Script (PowerShell)
# =============================================================================
# Script này sẽ triển khai TMATH lên Azure Container Apps với:
# - Azure Container Registry (ACR) để lưu Docker images
# - Azure Database for PostgreSQL Flexible Server
# - Azure Cache for Redis
# - Azure Container Apps cho web và celery worker
# =============================================================================

$ErrorActionPreference = "Stop"

# =============================================================================
# CẤU HÌNH - Thay đổi các giá trị này theo nhu cầu
# =============================================================================
$RESOURCE_GROUP = "tmath-rg"
$LOCATION = "southeastasia"  # Đông Nam Á - gần Việt Nam nhất
$APP_NAME = "tmath"
$ACR_NAME = "tmathacr" + (Get-Date -Format "HHmmss")  # Unique name for ACR

# Database
$DB_SERVER_NAME = "tmath-db-server"
$DB_NAME = "tmath"
$DB_ADMIN_USER = "tmathdbadmin"
$DB_ADMIN_PASSWORD = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 24 | ForEach-Object {[char]$_})

# Redis
$REDIS_NAME = "tmath-redis-" + (Get-Date -Format "HHmm")

# Container Apps
$CONTAINER_APP_ENV = "tmath-env"
$CONTAINER_APP_WEB = "tmath-web"
$CONTAINER_APP_CELERY = "tmath-celery"

# Django
$DJANGO_SECRET_KEY = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 50 | ForEach-Object {[char]$_})

# =============================================================================
# FUNCTIONS
# =============================================================================

function Write-Info($message) {
    Write-Host "[INFO] $message" -ForegroundColor Green
}

function Write-Warn($message) {
    Write-Host "[WARN] $message" -ForegroundColor Yellow
}

function Write-Err($message) {
    Write-Host "[ERROR] $message" -ForegroundColor Red
}

function Check-Prerequisites {
    Write-Info "Kiểm tra các công cụ cần thiết..."
    
    if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
        Write-Err "Azure CLI chưa được cài đặt. Vui lòng cài đặt từ: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
        exit 1
    }
    
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Err "Docker chưa được cài đặt."
        exit 1
    }
    
    Write-Info "Tất cả công cụ đã được cài đặt ✓"
}

function Login-Azure {
    Write-Info "Đăng nhập Azure..."
    az login --use-device-code
    
    Write-Info "Danh sách Subscription:"
    az account list --output table
    
    $SUBSCRIPTION_ID = Read-Host "Nhập Subscription ID"
    az account set --subscription $SUBSCRIPTION_ID
    Write-Info "Đã chọn subscription: $SUBSCRIPTION_ID ✓"
}

function Create-ResourceGroup {
    Write-Info "Tạo Resource Group: $RESOURCE_GROUP..."
    az group create --name $RESOURCE_GROUP --location $LOCATION
    Write-Info "Resource Group đã được tạo ✓"
}

function Create-ContainerRegistry {
    Write-Info "Tạo Azure Container Registry: $ACR_NAME..."
    az acr create `
        --resource-group $RESOURCE_GROUP `
        --name $ACR_NAME `
        --sku Basic `
        --admin-enabled true
    
    # Lấy credentials
    $script:ACR_LOGIN_SERVER = az acr show --name $ACR_NAME --query loginServer --output tsv
    $script:ACR_USERNAME = az acr credential show --name $ACR_NAME --query username --output tsv
    $script:ACR_PASSWORD = az acr credential show --name $ACR_NAME --query "passwords[0].value" --output tsv
    
    Write-Info "ACR đã được tạo: $ACR_LOGIN_SERVER ✓"
}

function Build-And-Push-Image {
    Write-Info "Build và push Docker image..."
    
    # Login to ACR
    az acr login --name $ACR_NAME
    
    # Build image
    docker build -t "$ACR_LOGIN_SERVER/${APP_NAME}:latest" -f azure/Dockerfile.prod .
    
    # Push image
    docker push "$ACR_LOGIN_SERVER/${APP_NAME}:latest"
    
    Write-Info "Docker image đã được push lên ACR ✓"
}

function Create-PostgreSQL {
    Write-Info "Tạo Azure Database for PostgreSQL..."
    
    # Create PostgreSQL Flexible Server
    az postgres flexible-server create `
        --resource-group $RESOURCE_GROUP `
        --name $DB_SERVER_NAME `
        --location $LOCATION `
        --admin-user $DB_ADMIN_USER `
        --admin-password $DB_ADMIN_PASSWORD `
        --sku-name Standard_B1ms `
        --tier Burstable `
        --storage-size 32 `
        --version 15 `
        --public-access 0.0.0.0-255.255.255.255
    
    # Create database
    az postgres flexible-server db create `
        --resource-group $RESOURCE_GROUP `
        --server-name $DB_SERVER_NAME `
        --database-name $DB_NAME
    
    $script:DB_HOST = "$DB_SERVER_NAME.postgres.database.azure.com"
    $script:DATABASE_URL = "postgres://${DB_ADMIN_USER}:${DB_ADMIN_PASSWORD}@${DB_HOST}:5432/${DB_NAME}?sslmode=require"
    
    Write-Info "PostgreSQL đã được tạo: $DB_HOST ✓"
}

function Create-Redis {
    Write-Info "Tạo Azure Cache for Redis..."
    
    az redis create `
        --resource-group $RESOURCE_GROUP `
        --name $REDIS_NAME `
        --location $LOCATION `
        --sku Basic `
        --vm-size c0 `
        --enable-non-ssl-port
    
    # Wait for Redis to be ready
    Write-Info "Đang chờ Redis khởi động (có thể mất 15-20 phút)..."
    
    do {
        Start-Sleep -Seconds 30
        $state = az redis show --resource-group $RESOURCE_GROUP --name $REDIS_NAME --query "provisioningState" --output tsv
        Write-Info "Redis status: $state"
    } while ($state -ne "Succeeded")
    
    $script:REDIS_HOST = az redis show --resource-group $RESOURCE_GROUP --name $REDIS_NAME --query "hostName" --output tsv
    $REDIS_KEY = az redis list-keys --resource-group $RESOURCE_GROUP --name $REDIS_NAME --query "primaryKey" --output tsv
    $script:REDIS_URL = "redis://:${REDIS_KEY}@${REDIS_HOST}:6379/0"
    $script:CELERY_BROKER_URL = "redis://:${REDIS_KEY}@${REDIS_HOST}:6379/1"
    
    Write-Info "Redis đã được tạo: $REDIS_HOST ✓"
}

function Create-ContainerAppsEnvironment {
    Write-Info "Tạo Container Apps Environment..."
    
    az containerapp env create `
        --resource-group $RESOURCE_GROUP `
        --name $CONTAINER_APP_ENV `
        --location $LOCATION
    
    Write-Info "Container Apps Environment đã được tạo ✓"
}

function Deploy-WebContainer {
    Write-Info "Deploy Web Container App..."
    
    az containerapp create `
        --resource-group $RESOURCE_GROUP `
        --name $CONTAINER_APP_WEB `
        --environment $CONTAINER_APP_ENV `
        --image "$ACR_LOGIN_SERVER/${APP_NAME}:latest" `
        --registry-server $ACR_LOGIN_SERVER `
        --registry-username $ACR_USERNAME `
        --registry-password $ACR_PASSWORD `
        --target-port 8000 `
        --ingress external `
        --min-replicas 1 `
        --max-replicas 5 `
        --cpu 0.5 `
        --memory 1.0Gi `
        --env-vars "DEBUG=False" "SECRET_KEY=$DJANGO_SECRET_KEY" "DATABASE_URL=$DATABASE_URL" "REDIS_URL=$REDIS_URL" "CELERY_BROKER_URL=$CELERY_BROKER_URL" "ALLOWED_HOSTS=*" `
        --command "sh" "-c" "python manage.py migrate --noinput && gunicorn --bind 0.0.0.0:8000 --workers 2 --threads 4 --worker-class gthread --timeout 120 tmath.wsgi:application"
    
    $script:WEB_URL = az containerapp show --resource-group $RESOURCE_GROUP --name $CONTAINER_APP_WEB --query "properties.configuration.ingress.fqdn" --output tsv
    
    Write-Info "Web Container App đã được deploy: https://$WEB_URL ✓"
}

function Deploy-CeleryContainer {
    Write-Info "Deploy Celery Worker Container App..."
    
    az containerapp create `
        --resource-group $RESOURCE_GROUP `
        --name $CONTAINER_APP_CELERY `
        --environment $CONTAINER_APP_ENV `
        --image "$ACR_LOGIN_SERVER/${APP_NAME}:latest" `
        --registry-server $ACR_LOGIN_SERVER `
        --registry-username $ACR_USERNAME `
        --registry-password $ACR_PASSWORD `
        --min-replicas 1 `
        --max-replicas 3 `
        --cpu 0.5 `
        --memory 1.0Gi `
        --env-vars "DEBUG=False" "SECRET_KEY=$DJANGO_SECRET_KEY" "DATABASE_URL=$DATABASE_URL" "REDIS_URL=$REDIS_URL" "CELERY_BROKER_URL=$CELERY_BROKER_URL" `
        --command "celery" "-A" "tmath" "worker" "-l" "info"
    
    Write-Info "Celery Worker đã được deploy ✓"
}

function Save-Configuration {
    Write-Info "Lưu cấu hình..."
    
    $config = @"
# =============================================================================
# TMATH Azure Deployment Configuration
# Generated: $(Get-Date)
# =============================================================================

# Resource Group
RESOURCE_GROUP=$RESOURCE_GROUP
LOCATION=$LOCATION

# Container Registry
ACR_NAME=$ACR_NAME
ACR_LOGIN_SERVER=$ACR_LOGIN_SERVER

# Database
DB_SERVER_NAME=$DB_SERVER_NAME
DB_HOST=$DB_HOST
DB_NAME=$DB_NAME
DB_ADMIN_USER=$DB_ADMIN_USER
DB_ADMIN_PASSWORD=$DB_ADMIN_PASSWORD
DATABASE_URL=$DATABASE_URL

# Redis
REDIS_NAME=$REDIS_NAME
REDIS_HOST=$REDIS_HOST
REDIS_URL=$REDIS_URL
CELERY_BROKER_URL=$CELERY_BROKER_URL

# Container Apps
CONTAINER_APP_ENV=$CONTAINER_APP_ENV
CONTAINER_APP_WEB=$CONTAINER_APP_WEB
CONTAINER_APP_CELERY=$CONTAINER_APP_CELERY

# Application
WEB_URL=https://$WEB_URL
DJANGO_SECRET_KEY=$DJANGO_SECRET_KEY
"@
    
    $config | Out-File -FilePath "azure/deployment-config.env" -Encoding UTF8
    Write-Info "Cấu hình đã được lưu tại: azure/deployment-config.env ✓"
}

function Print-Summary {
    Write-Host ""
    Write-Host "=============================================================================" -ForegroundColor Cyan
    Write-Host "TRIỂN KHAI HOÀN TẤT!" -ForegroundColor Green
    Write-Host "=============================================================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "🌐 Web URL: https://$WEB_URL" -ForegroundColor White
    Write-Host "📦 Container Registry: $ACR_LOGIN_SERVER" -ForegroundColor White
    Write-Host "🗄️  Database: $DB_HOST" -ForegroundColor White
    Write-Host "🔴 Redis: $REDIS_HOST" -ForegroundColor White
    Write-Host ""
    Write-Host "📝 Cấu hình đã được lưu tại: azure/deployment-config.env" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "⚠️  QUAN TRỌNG: Hãy sao lưu file deployment-config.env vì chứa các thông tin bí mật!" -ForegroundColor Red
    Write-Host ""
    Write-Host "=============================================================================" -ForegroundColor Cyan
    Write-Host "CÁC LỆNH QUẢN LÝ:" -ForegroundColor Cyan
    Write-Host "=============================================================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "# Xem logs:" -ForegroundColor Gray
    Write-Host "az containerapp logs show -n $CONTAINER_APP_WEB -g $RESOURCE_GROUP"
    Write-Host ""
    Write-Host "# Restart app:" -ForegroundColor Gray
    Write-Host "az containerapp revision restart -n $CONTAINER_APP_WEB -g $RESOURCE_GROUP"
    Write-Host ""
    Write-Host "# Update image:" -ForegroundColor Gray
    Write-Host "docker build -t $ACR_LOGIN_SERVER/${APP_NAME}:latest -f azure/Dockerfile.prod ."
    Write-Host "docker push $ACR_LOGIN_SERVER/${APP_NAME}:latest"
    Write-Host "az containerapp update -n $CONTAINER_APP_WEB -g $RESOURCE_GROUP --image $ACR_LOGIN_SERVER/${APP_NAME}:latest"
    Write-Host ""
    Write-Host "# Xóa tất cả resources:" -ForegroundColor Gray
    Write-Host "az group delete --name $RESOURCE_GROUP --yes --no-wait"
    Write-Host ""
}

# =============================================================================
# MAIN
# =============================================================================

function Main {
    Write-Host ""
    Write-Host "=============================================================================" -ForegroundColor Cyan
    Write-Host "     TMATH - Triển khai lên Azure Container Apps" -ForegroundColor Cyan
    Write-Host "=============================================================================" -ForegroundColor Cyan
    Write-Host ""
    
    Check-Prerequisites
    Login-Azure
    Create-ResourceGroup
    Create-ContainerRegistry
    Build-And-Push-Image
    Create-PostgreSQL
    Create-Redis
    Create-ContainerAppsEnvironment
    Deploy-WebContainer
    Deploy-CeleryContainer
    Save-Configuration
    Print-Summary
}

# Run main function
Main
