#!/bin/bash
# =============================================================================
# TMATH Deployment Script for Azure VM (Ubuntu 22.04)
# =============================================================================
# Script này sẽ cài đặt và cấu hình TMATH trên Azure Ubuntu VM
# =============================================================================

set -e

# Màu sắc
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# =============================================================================
# CẤU HÌNH
# =============================================================================
APP_DIR="/opt/tmath"
DB_NAME="tmath"
DB_USER="tmath"
DB_PASSWORD=$(openssl rand -base64 24 | tr -dc 'a-zA-Z0-9' | head -c 20)
DJANGO_SECRET=$(openssl rand -base64 50 | tr -dc 'a-zA-Z0-9' | head -c 50)
DOMAIN="${1:-$(hostname -I | awk '{print $1}')}"

# =============================================================================
# 1. CẬP NHẬT HỆ THỐNG
# =============================================================================
log_info "Cập nhật hệ thống..."
sudo apt update && sudo apt upgrade -y

# =============================================================================
# 2. CÀI ĐẶT CÁC GÓI CẦN THIẾT
# =============================================================================
log_info "Cài đặt các gói cần thiết..."
sudo apt install -y \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    python3-pip \
    postgresql \
    postgresql-contrib \
    redis-server \
    nginx \
    supervisor \
    git \
    curl \
    wget \
    build-essential \
    libpq-dev \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    libffi-dev \
    libssl-dev \
    nodejs \
    npm \
    exiftool \
    certbot \
    python3-certbot-nginx

# =============================================================================
# 3. CẤU HÌNH POSTGRESQL
# =============================================================================
log_info "Cấu hình PostgreSQL..."
sudo systemctl start postgresql
sudo systemctl enable postgresql

sudo -u postgres psql -c "CREATE DATABASE $DB_NAME;" 2>/dev/null || log_warn "Database đã tồn tại"
sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';" 2>/dev/null || log_warn "User đã tồn tại"
sudo -u postgres psql -c "ALTER ROLE $DB_USER SET client_encoding TO 'utf8';"
sudo -u postgres psql -c "ALTER ROLE $DB_USER SET default_transaction_isolation TO 'read committed';"
sudo -u postgres psql -c "ALTER ROLE $DB_USER SET timezone TO 'UTC';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;"
sudo -u postgres psql -c "ALTER DATABASE $DB_NAME OWNER TO $DB_USER;"

log_info "PostgreSQL đã được cấu hình ✓"

# =============================================================================
# 4. CẤU HÌNH REDIS
# =============================================================================
log_info "Cấu hình Redis..."
sudo systemctl start redis-server
sudo systemctl enable redis-server
log_info "Redis đã được cấu hình ✓"

# =============================================================================
# 5. TẠO THƯ MỤC ỨNG DỤNG
# =============================================================================
log_info "Tạo thư mục ứng dụng..."
sudo mkdir -p $APP_DIR
sudo chown -R $USER:$USER $APP_DIR

# =============================================================================
# 6. CLONE SOURCE CODE (hoặc copy từ local)
# =============================================================================
log_info "Source code sẽ được upload riêng..."
# cd $APP_DIR
# git clone https://github.com/your-repo/tmath.git .

# =============================================================================
# 7. TẠO VIRTUAL ENVIRONMENT
# =============================================================================
log_info "Tạo Python virtual environment..."
python3.11 -m venv $APP_DIR/venv
source $APP_DIR/venv/bin/activate

# =============================================================================
# 8. TẠO FILE CẤU HÌNH
# =============================================================================
log_info "Tạo file cấu hình..."

cat > $APP_DIR/.env << EOF
# Django Settings
DEBUG=False
SECRET_KEY=$DJANGO_SECRET
ALLOWED_HOSTS=$DOMAIN,localhost,127.0.0.1

# Database
DATABASE_URL=postgres://$DB_USER:$DB_PASSWORD@localhost:5432/$DB_NAME

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1

# Site
SITE_NAME=TMATH
SITE_LONG_NAME=TMATH: ROBOLAB Online Judge
EOF

chmod 600 $APP_DIR/.env

# =============================================================================
# 9. CẤU HÌNH GUNICORN
# =============================================================================
log_info "Cấu hình Gunicorn..."

cat | sudo tee /etc/supervisor/conf.d/tmath-gunicorn.conf << EOF
[program:tmath-gunicorn]
command=$APP_DIR/venv/bin/gunicorn --workers 4 --threads 2 --worker-class gthread --bind unix:/run/tmath/gunicorn.sock --timeout 120 tmath.wsgi:application
directory=$APP_DIR
user=$USER
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/tmath/gunicorn.log
environment=DJANGO_SETTINGS_MODULE="tmath.settings_production"
EOF

# =============================================================================
# 10. CẤU HÌNH CELERY
# =============================================================================
log_info "Cấu hình Celery..."

cat | sudo tee /etc/supervisor/conf.d/tmath-celery.conf << EOF
[program:tmath-celery]
command=$APP_DIR/venv/bin/celery -A tmath worker -l info
directory=$APP_DIR
user=$USER
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/tmath/celery.log
environment=DJANGO_SETTINGS_MODULE="tmath.settings_production"
EOF

# =============================================================================
# 11. CẤU HÌNH NGINX
# =============================================================================
log_info "Cấu hình Nginx..."

cat | sudo tee /etc/nginx/sites-available/tmath << EOF
server {
    listen 80;
    server_name $DOMAIN;
    
    client_max_body_size 100M;

    location /static/ {
        alias $APP_DIR/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias $APP_DIR/media/;
    }

    location / {
        proxy_pass http://unix:/run/tmath/gunicorn.sock;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 300;
        proxy_send_timeout 300;
        proxy_read_timeout 300;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/tmath /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# =============================================================================
# 12. TẠO THƯ MỤC CẦN THIẾT
# =============================================================================
log_info "Tạo các thư mục cần thiết..."
sudo mkdir -p /run/tmath
sudo chown -R $USER:$USER /run/tmath
sudo mkdir -p /var/log/tmath
sudo chown -R $USER:$USER /var/log/tmath
mkdir -p $APP_DIR/staticfiles
mkdir -p $APP_DIR/media

# =============================================================================
# 13. CẤU HÌNH FIREWALL
# =============================================================================
log_info "Cấu hình firewall..."
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable

# =============================================================================
# LƯU THÔNG TIN
# =============================================================================
cat > $APP_DIR/deployment-info.txt << EOF
=============================================================================
TMATH DEPLOYMENT INFORMATION
=============================================================================
Generated: $(date)

Server IP: $DOMAIN
App Directory: $APP_DIR

PostgreSQL:
  Database: $DB_NAME
  User: $DB_USER
  Password: $DB_PASSWORD

Django Secret Key: $DJANGO_SECRET

Redis: localhost:6379

IMPORTANT FILES:
  - Environment: $APP_DIR/.env
  - Nginx config: /etc/nginx/sites-available/tmath
  - Gunicorn config: /etc/supervisor/conf.d/tmath-gunicorn.conf
  - Celery config: /etc/supervisor/conf.d/tmath-celery.conf

MANAGEMENT COMMANDS:
  # Restart all services
  sudo supervisorctl restart all
  sudo systemctl restart nginx

  # View logs
  sudo tail -f /var/log/tmath/gunicorn.log
  sudo tail -f /var/log/tmath/celery.log

  # Django management
  cd $APP_DIR && source venv/bin/activate
  python manage.py migrate
  python manage.py createsuperuser
  python manage.py collectstatic

  # SSL Certificate (after DNS configured)
  sudo certbot --nginx -d yourdomain.com

=============================================================================
EOF

chmod 600 $APP_DIR/deployment-info.txt

echo ""
echo "============================================================================="
echo -e "${GREEN}CÀI ĐẶT CƠ SỞ HOÀN TẤT!${NC}"
echo "============================================================================="
echo ""
echo "Thông tin đã được lưu tại: $APP_DIR/deployment-info.txt"
echo ""
echo "BƯỚC TIẾP THEO:"
echo "1. Upload source code vào: $APP_DIR"
echo "2. Chạy: source $APP_DIR/venv/bin/activate"
echo "3. Chạy: pip install -r requirements.txt"
echo "4. Chạy: python manage.py migrate"
echo "5. Chạy: python manage.py collectstatic"
echo "6. Chạy: python manage.py createsuperuser"
echo "7. Chạy: sudo supervisorctl reread && sudo supervisorctl update"
echo "8. Chạy: sudo systemctl restart nginx"
echo ""
echo "============================================================================="
