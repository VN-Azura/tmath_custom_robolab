#!/bin/bash
# =============================================================================
# TMATH Azure Container Apps Deployment Script
# =============================================================================
# Script này sẽ triển khai TMATH lên Azure Container Apps với:
# - Azure Container Registry (ACR) để lưu Docker images
# - Azure Database for PostgreSQL Flexible Server
# - Azure Cache for Redis
# - Azure Container Apps cho web và celery worker
# =============================================================================

set -e

# Màu sắc cho output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# =============================================================================
# CẤU HÌNH - Thay đổi các giá trị này theo nhu cầu
# =============================================================================
RESOURCE_GROUP="tmath-rg"
LOCATION="southeastasia"  # Đông Nam Á - gần Việt Nam nhất
APP_NAME="tmath"
ACR_NAME="tmathacr$(date +%s | tail -c 5)"  # Unique name for ACR

# Database
DB_SERVER_NAME="tmath-db-server"
DB_NAME="tmath"
DB_ADMIN_USER="tmathdbadmin"
DB_ADMIN_PASSWORD=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 24)

# Redis
REDIS_NAME="tmath-redis"

# Container Apps
CONTAINER_APP_ENV="tmath-env"
CONTAINER_APP_WEB="tmath-web"
CONTAINER_APP_CELERY="tmath-celery"

# Django
DJANGO_SECRET_KEY=$(openssl rand -base64 50 | tr -dc 'a-zA-Z0-9!@#$%^&*()' | head -c 50)

# =============================================================================
# FUNCTIONS
# =============================================================================

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "Kiểm tra các công cụ cần thiết..."
    
    if ! command -v az &> /dev/null; then
        log_error "Azure CLI chưa được cài đặt. Vui lòng cài đặt từ: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
        exit 1
    fi
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker chưa được cài đặt."
        exit 1
    fi
    
    log_info "Tất cả công cụ đã được cài đặt ✓"
}

login_azure() {
    log_info "Đăng nhập Azure..."
    az login --use-device-code
    
    log_info "Chọn subscription..."
    az account list --output table
    read -p "Nhập Subscription ID: " SUBSCRIPTION_ID
    az account set --subscription "$SUBSCRIPTION_ID"
    log_info "Đã chọn subscription: $SUBSCRIPTION_ID ✓"
}

create_resource_group() {
    log_info "Tạo Resource Group: $RESOURCE_GROUP..."
    az group create --name "$RESOURCE_GROUP" --location "$LOCATION"
    log_info "Resource Group đã được tạo ✓"
}

create_container_registry() {
    log_info "Tạo Azure Container Registry: $ACR_NAME..."
    az acr create \
        --resource-group "$RESOURCE_GROUP" \
        --name "$ACR_NAME" \
        --sku Basic \
        --admin-enabled true
    
    # Lấy credentials
    ACR_LOGIN_SERVER=$(az acr show --name "$ACR_NAME" --query loginServer --output tsv)
    ACR_USERNAME=$(az acr credential show --name "$ACR_NAME" --query username --output tsv)
    ACR_PASSWORD=$(az acr credential show --name "$ACR_NAME" --query "passwords[0].value" --output tsv)
    
    log_info "ACR đã được tạo: $ACR_LOGIN_SERVER ✓"
}

build_and_push_image() {
    log_info "Build và push Docker image..."
    
    # Login to ACR
    az acr login --name "$ACR_NAME"
    
    # Build image
    docker build -t "$ACR_LOGIN_SERVER/$APP_NAME:latest" -f azure/Dockerfile.prod .
    
    # Push image
    docker push "$ACR_LOGIN_SERVER/$APP_NAME:latest"
    
    log_info "Docker image đã được push lên ACR ✓"
}

create_postgresql() {
    log_info "Tạo Azure Database for PostgreSQL..."
    
    # Create PostgreSQL Flexible Server
    az postgres flexible-server create \
        --resource-group "$RESOURCE_GROUP" \
        --name "$DB_SERVER_NAME" \
        --location "$LOCATION" \
        --admin-user "$DB_ADMIN_USER" \
        --admin-password "$DB_ADMIN_PASSWORD" \
        --sku-name Standard_B1ms \
        --tier Burstable \
        --storage-size 32 \
        --version 15 \
        --public-access 0.0.0.0-255.255.255.255  # Sẽ được hạn chế sau khi Container Apps được tạo
    
    # Create database
    az postgres flexible-server db create \
        --resource-group "$RESOURCE_GROUP" \
        --server-name "$DB_SERVER_NAME" \
        --database-name "$DB_NAME"
    
    DB_HOST="$DB_SERVER_NAME.postgres.database.azure.com"
    DATABASE_URL="postgres://$DB_ADMIN_USER:$DB_ADMIN_PASSWORD@$DB_HOST:5432/$DB_NAME?sslmode=require"
    
    log_info "PostgreSQL đã được tạo: $DB_HOST ✓"
}

create_redis() {
    log_info "Tạo Azure Cache for Redis..."
    
    az redis create \
        --resource-group "$RESOURCE_GROUP" \
        --name "$REDIS_NAME" \
        --location "$LOCATION" \
        --sku Basic \
        --vm-size c0 \
        --enable-non-ssl-port
    
    # Wait for Redis to be ready
    log_info "Đang chờ Redis khởi động (có thể mất 15-20 phút)..."
    az redis show --resource-group "$RESOURCE_GROUP" --name "$REDIS_NAME" --query "provisioningState" --output tsv
    
    REDIS_HOST=$(az redis show --resource-group "$RESOURCE_GROUP" --name "$REDIS_NAME" --query "hostName" --output tsv)
    REDIS_KEY=$(az redis list-keys --resource-group "$RESOURCE_GROUP" --name "$REDIS_NAME" --query "primaryKey" --output tsv)
    REDIS_URL="redis://:$REDIS_KEY@$REDIS_HOST:6379/0"
    CELERY_BROKER_URL="redis://:$REDIS_KEY@$REDIS_HOST:6379/1"
    
    log_info "Redis đã được tạo: $REDIS_HOST ✓"
}

create_container_apps_environment() {
    log_info "Tạo Container Apps Environment..."
    
    az containerapp env create \
        --resource-group "$RESOURCE_GROUP" \
        --name "$CONTAINER_APP_ENV" \
        --location "$LOCATION"
    
    log_info "Container Apps Environment đã được tạo ✓"
}

deploy_web_container() {
    log_info "Deploy Web Container App..."
    
    az containerapp create \
        --resource-group "$RESOURCE_GROUP" \
        --name "$CONTAINER_APP_WEB" \
        --environment "$CONTAINER_APP_ENV" \
        --image "$ACR_LOGIN_SERVER/$APP_NAME:latest" \
        --registry-server "$ACR_LOGIN_SERVER" \
        --registry-username "$ACR_USERNAME" \
        --registry-password "$ACR_PASSWORD" \
        --target-port 8000 \
        --ingress external \
        --min-replicas 1 \
        --max-replicas 5 \
        --cpu 0.5 \
        --memory 1.0Gi \
        --env-vars \
            "DEBUG=False" \
            "SECRET_KEY=$DJANGO_SECRET_KEY" \
            "DATABASE_URL=$DATABASE_URL" \
            "REDIS_URL=$REDIS_URL" \
            "CELERY_BROKER_URL=$CELERY_BROKER_URL" \
            "ALLOWED_HOSTS=*" \
        --command "sh" "-c" "python manage.py migrate --noinput && gunicorn --bind 0.0.0.0:8000 --workers 2 --threads 4 --worker-class gthread --timeout 120 tmath.wsgi:application"
    
    WEB_URL=$(az containerapp show --resource-group "$RESOURCE_GROUP" --name "$CONTAINER_APP_WEB" --query "properties.configuration.ingress.fqdn" --output tsv)
    
    log_info "Web Container App đã được deploy: https://$WEB_URL ✓"
}

deploy_celery_container() {
    log_info "Deploy Celery Worker Container App..."
    
    az containerapp create \
        --resource-group "$RESOURCE_GROUP" \
        --name "$CONTAINER_APP_CELERY" \
        --environment "$CONTAINER_APP_ENV" \
        --image "$ACR_LOGIN_SERVER/$APP_NAME:latest" \
        --registry-server "$ACR_LOGIN_SERVER" \
        --registry-username "$ACR_USERNAME" \
        --registry-password "$ACR_PASSWORD" \
        --min-replicas 1 \
        --max-replicas 3 \
        --cpu 0.5 \
        --memory 1.0Gi \
        --env-vars \
            "DEBUG=False" \
            "SECRET_KEY=$DJANGO_SECRET_KEY" \
            "DATABASE_URL=$DATABASE_URL" \
            "REDIS_URL=$REDIS_URL" \
            "CELERY_BROKER_URL=$CELERY_BROKER_URL" \
        --command "celery" "-A" "tmath" "worker" "-l" "info"
    
    log_info "Celery Worker đã được deploy ✓"
}

save_configuration() {
    log_info "Lưu cấu hình..."
    
    cat > azure/deployment-config.env << EOF
# =============================================================================
# TMATH Azure Deployment Configuration
# Generated: $(date)
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
EOF
    
    chmod 600 azure/deployment-config.env
    log_info "Cấu hình đã được lưu tại: azure/deployment-config.env ✓"
}

print_summary() {
    echo ""
    echo "============================================================================="
    echo -e "${GREEN}TRIỂN KHAI HOÀN TẤT!${NC}"
    echo "============================================================================="
    echo ""
    echo "🌐 Web URL: https://$WEB_URL"
    echo "📦 Container Registry: $ACR_LOGIN_SERVER"
    echo "🗄️  Database: $DB_HOST"
    echo "🔴 Redis: $REDIS_HOST"
    echo ""
    echo "📝 Cấu hình đã được lưu tại: azure/deployment-config.env"
    echo ""
    echo "⚠️  QUAN TRỌNG: Hãy sao lưu file deployment-config.env vì chứa các thông tin bí mật!"
    echo ""
    echo "============================================================================="
    echo "CÁC LỆNH QUẢN LÝ:"
    echo "============================================================================="
    echo ""
    echo "# Xem logs:"
    echo "az containerapp logs show -n $CONTAINER_APP_WEB -g $RESOURCE_GROUP"
    echo ""
    echo "# Restart app:"
    echo "az containerapp revision restart -n $CONTAINER_APP_WEB -g $RESOURCE_GROUP"
    echo ""
    echo "# Update image:"
    echo "docker build -t $ACR_LOGIN_SERVER/$APP_NAME:latest -f azure/Dockerfile.prod ."
    echo "docker push $ACR_LOGIN_SERVER/$APP_NAME:latest"
    echo "az containerapp update -n $CONTAINER_APP_WEB -g $RESOURCE_GROUP --image $ACR_LOGIN_SERVER/$APP_NAME:latest"
    echo ""
    echo "# Xóa tất cả resources:"
    echo "az group delete --name $RESOURCE_GROUP --yes --no-wait"
    echo ""
}

# =============================================================================
# MAIN
# =============================================================================

main() {
    echo ""
    echo "============================================================================="
    echo "     TMATH - Triển khai lên Azure Container Apps"
    echo "============================================================================="
    echo ""
    
    check_prerequisites
    login_azure
    create_resource_group
    create_container_registry
    build_and_push_image
    create_postgresql
    create_redis
    create_container_apps_environment
    deploy_web_container
    deploy_celery_container
    save_configuration
    print_summary
}

# Run main function
main "$@"
