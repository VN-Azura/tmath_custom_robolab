# 🚀 Hướng dẫn Triển khai TMATH lên Microsoft Azure

## Tổng quan

Hướng dẫn này sẽ giúp bạn triển khai hệ thống TMATH lên **Azure Container Apps** với kiến trúc sau:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Azure Container Apps                          │
│  ┌─────────────────┐     ┌─────────────────┐                   │
│  │   TMATH Web     │     │  Celery Worker  │                   │
│  │   (Auto-scale)  │     │  (Background)   │                   │
│  └────────┬────────┘     └────────┬────────┘                   │
└───────────┼───────────────────────┼─────────────────────────────┘
            │                       │
     ┌──────┴───────┬───────────────┴──────┐
     │              │                      │
     ▼              ▼                      ▼
┌─────────┐  ┌────────────┐         ┌───────────┐
│PostgreSQL│  │   Redis    │         │    ACR    │
│ (Azure)  │  │  (Azure)   │         │  (Docker) │
└─────────┘  └────────────┘         └───────────┘
```

## Yêu cầu trước khi bắt đầu

### 1. Cài đặt công cụ

**Azure CLI:**

```powershell
# Windows (winget)
winget install Microsoft.AzureCLI

# Hoặc tải từ: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli-windows
```

**Docker Desktop:**

- Tải từ: https://www.docker.com/products/docker-desktop/
- Đảm bảo Docker đang chạy

### 2. Tài khoản Azure

- Đăng ký tại: https://azure.microsoft.com/free/
- Azure cung cấp $200 credit miễn phí cho 30 ngày đầu

---

## Phương pháp 1: Triển khai tự động (Khuyến nghị)

### Bước 1: Chạy script triển khai

```powershell
# Di chuyển vào thư mục dự án
cd E:\ROBOLAB\Tinhoctre\TMATH

# Chạy script PowerShell
.\azure\deploy.ps1
```

Script sẽ tự động:

1. ✅ Đăng nhập Azure
2. ✅ Tạo Resource Group
3. ✅ Tạo Azure Container Registry
4. ✅ Build và push Docker image
5. ✅ Tạo PostgreSQL database
6. ✅ Tạo Redis cache
7. ✅ Deploy Container Apps
8. ✅ Lưu cấu hình

### Bước 2: Tạo Super User

Sau khi deploy xong, tạo admin user:

```powershell
# Kết nối vào container và chạy lệnh
az containerapp exec -n tmath-web -g tmath-rg --command "python manage.py createsuperuser"
```

---

## Phương pháp 2: Triển khai thủ công (Từng bước)

### Bước 1: Đăng nhập Azure

```powershell
az login --use-device-code
```

### Bước 2: Tạo Resource Group

```powershell
$RESOURCE_GROUP = "tmath-rg"
$LOCATION = "southeastasia"

az group create --name $RESOURCE_GROUP --location $LOCATION
```

### Bước 3: Tạo Container Registry

```powershell
$ACR_NAME = "tmathacr$(Get-Date -Format 'HHmmss')"

az acr create `
    --resource-group $RESOURCE_GROUP `
    --name $ACR_NAME `
    --sku Basic `
    --admin-enabled true
```

### Bước 4: Build và Push Docker Image

```powershell
# Login to ACR
az acr login --name $ACR_NAME

# Lấy ACR login server
$ACR_SERVER = az acr show --name $ACR_NAME --query loginServer --output tsv

# Build image
docker build -t "${ACR_SERVER}/tmath:latest" -f azure/Dockerfile.prod .

# Push image
docker push "${ACR_SERVER}/tmath:latest"
```

### Bước 5: Tạo PostgreSQL

```powershell
$DB_PASSWORD = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 24 | ForEach-Object {[char]$_})

az postgres flexible-server create `
    --resource-group $RESOURCE_GROUP `
    --name "tmath-db-server" `
    --location $LOCATION `
    --admin-user "tmathdbadmin" `
    --admin-password $DB_PASSWORD `
    --sku-name Standard_B1ms `
    --tier Burstable `
    --storage-size 32 `
    --version 15

az postgres flexible-server db create `
    --resource-group $RESOURCE_GROUP `
    --server-name "tmath-db-server" `
    --database-name "tmath"
```

### Bước 6: Tạo Redis

```powershell
az redis create `
    --resource-group $RESOURCE_GROUP `
    --name "tmath-redis" `
    --location $LOCATION `
    --sku Basic `
    --vm-size c0 `
    --enable-non-ssl-port
```

> ⚠️ Redis mất khoảng 15-20 phút để khởi tạo

### Bước 7: Tạo Container Apps Environment

```powershell
az containerapp env create `
    --resource-group $RESOURCE_GROUP `
    --name "tmath-env" `
    --location $LOCATION
```

### Bước 8: Deploy Web Container

```powershell
# Lấy thông tin credentials
$ACR_USERNAME = az acr credential show --name $ACR_NAME --query username --output tsv
$ACR_PASSWORD = az acr credential show --name $ACR_NAME --query "passwords[0].value" --output tsv
$REDIS_KEY = az redis list-keys --resource-group $RESOURCE_GROUP --name "tmath-redis" --query "primaryKey" --output tsv

# Deploy
az containerapp create `
    --resource-group $RESOURCE_GROUP `
    --name "tmath-web" `
    --environment "tmath-env" `
    --image "${ACR_SERVER}/tmath:latest" `
    --registry-server $ACR_SERVER `
    --registry-username $ACR_USERNAME `
    --registry-password $ACR_PASSWORD `
    --target-port 8000 `
    --ingress external `
    --min-replicas 1 `
    --max-replicas 5 `
    --cpu 0.5 `
    --memory 1.0Gi
```

---

## Phương pháp 3: Infrastructure as Code (Bicep)

Sử dụng Bicep template cho deployment có thể lặp lại:

```powershell
# Tạo Resource Group trước
az group create --name tmath-rg --location southeastasia

# Deploy infrastructure
az deployment group create `
    --resource-group tmath-rg `
    --template-file azure/infrastructure.bicep `
    --parameters `
        dbAdminPassword="YourSecurePassword123!" `
        djangoSecretKey="your-50-char-secret-key-here" `
        containerImage="youracr.azurecr.io/tmath:latest" `
        acrLoginServer="youracr.azurecr.io" `
        acrUsername="yourusername" `
        acrPassword="youracrpassword"
```

---

## Quản lý và Vận hành

### Xem Logs

```powershell
# Logs của web app
az containerapp logs show -n tmath-web -g tmath-rg --follow

# Logs của celery worker
az containerapp logs show -n tmath-celery -g tmath-rg --follow
```

### Restart Application

```powershell
az containerapp revision restart -n tmath-web -g tmath-rg
```

### Update Image (CI/CD)

```powershell
# Build new image
docker build -t ${ACR_SERVER}/tmath:v2 -f azure/Dockerfile.prod .
docker push ${ACR_SERVER}/tmath:v2

# Update container app
az containerapp update -n tmath-web -g tmath-rg --image ${ACR_SERVER}/tmath:v2
az containerapp update -n tmath-celery -g tmath-rg --image ${ACR_SERVER}/tmath:v2
```

### Chạy Django Management Commands

```powershell
# Chạy migrations
az containerapp exec -n tmath-web -g tmath-rg --command "python manage.py migrate"

# Tạo superuser
az containerapp exec -n tmath-web -g tmath-rg --command "python manage.py createsuperuser"

# Collect static files
az containerapp exec -n tmath-web -g tmath-rg --command "python manage.py collectstatic --noinput"
```

### Scale Application

```powershell
# Scale thủ công
az containerapp update -n tmath-web -g tmath-rg --min-replicas 2 --max-replicas 10

# Xem số replicas hiện tại
az containerapp show -n tmath-web -g tmath-rg --query "properties.template.scale"
```

---

## Chi phí ước tính

| Dịch vụ                 | SKU              | Chi phí/tháng (USD) |
| ----------------------- | ---------------- | ------------------- |
| Container Apps (Web)    | 0.5 vCPU, 1GB    | ~$15-30             |
| Container Apps (Celery) | 0.5 vCPU, 1GB    | ~$15-30             |
| PostgreSQL              | B1ms (Burstable) | ~$12                |
| Redis                   | Basic C0         | ~$16                |
| Container Registry      | Basic            | ~$5                 |
| **Tổng**                |                  | **~$63-93/tháng**   |

> 💡 **Tiết kiệm chi phí:**
>
> - Sử dụng Azure Reserved Instances
> - Giảm min replicas về 0 (cold start khi có request)
> - Sử dụng Azure SQL với Serverless tier

---

## Custom Domain và SSL

### Thêm Custom Domain

```powershell
# Thêm domain
az containerapp hostname add `
    --resource-group tmath-rg `
    --name tmath-web `
    --hostname tmath.yourdomain.com

# Cấu hình SSL (Azure tự động cấp certificate)
az containerapp hostname bind `
    --resource-group tmath-rg `
    --name tmath-web `
    --hostname tmath.yourdomain.com `
    --environment tmath-env `
    --validation-method CNAME
```

### Cấu hình DNS

Thêm CNAME record trong DNS của domain:

```
tmath.yourdomain.com -> tmath-web.xxxxx.southeastasia.azurecontainerapps.io
```

---

## Backup và Recovery

### Backup PostgreSQL

```powershell
# Azure tự động backup hàng ngày
# Xem retention policy
az postgres flexible-server show -g tmath-rg -n tmath-db-server --query "backup"

# Point-in-time restore
az postgres flexible-server restore `
    --resource-group tmath-rg `
    --name tmath-db-restored `
    --source-server tmath-db-server `
    --restore-time "2024-01-15T10:00:00Z"
```

---

## Troubleshooting

### Lỗi kết nối Database

```powershell
# Kiểm tra firewall rules
az postgres flexible-server firewall-rule list -g tmath-rg -n tmath-db-server

# Thêm IP của Container Apps
az postgres flexible-server firewall-rule create `
    -g tmath-rg -n tmath-db-server `
    --rule-name "AllowAzure" `
    --start-ip-address 0.0.0.0 `
    --end-ip-address 0.0.0.0
```

### Container không khởi động

```powershell
# Xem chi tiết lỗi
az containerapp show -n tmath-web -g tmath-rg --query "properties.latestRevisionFqdn"

# Xem events
az containerapp revision show -n tmath-web -g tmath-rg --revision <revision-name>
```

### Redis connection refused

```powershell
# Kiểm tra Redis status
az redis show -g tmath-rg -n tmath-redis --query "provisioningState"

# Lấy connection string mới
az redis list-keys -g tmath-rg -n tmath-redis
```

---

## Xóa toàn bộ Resources

⚠️ **Cảnh báo: Lệnh này sẽ xóa tất cả dữ liệu!**

```powershell
az group delete --name tmath-rg --yes --no-wait
```

---

## Hỗ trợ

Nếu gặp vấn đề, vui lòng:

1. Xem logs: `az containerapp logs show -n tmath-web -g tmath-rg`
2. Kiểm tra Azure Portal: https://portal.azure.com
3. Tham khảo tài liệu Azure Container Apps: https://learn.microsoft.com/en-us/azure/container-apps/
