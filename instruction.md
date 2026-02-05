# Cài đặt trang Web

Cài đặt trang web trên hệ điều hành Ubuntu 22.04 LTS.

## Cài đặt các gói cần thiết

### Chung

```bash
$ sudo apt update
$ sudo apt install -y ca-certificates curl gnupg gcc g++ make git gettext pkg-config
$ sudo mkdir -p /etc/apt/keyrings
```

### Python

```bash
$ sudo apt install python3 python3-dev python3-venv
```

### MariaDB

```bash
$ sudo apt install mariadb-server libmysqlclient-dev
```

### Node.js

```bash
$ curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | sudo gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg

$ NODE_MAJOR=20
$ echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_$NODE_MAJOR.x nodistro main" | sudo tee /etc/apt/sources.list.d/nodesource.list

$ sudo apt update
$ sudo apt install -y nodejs
```

### Redis

```bash
$ sudo apt install redis-server
```

### Nginx

```bash
$ sudo apt install nginx
```

### Supervisor

```bash
$ sudo apt install supervisor
```

## Khởi tạo cơ sở dữ liệu

### Cài đặt timezone

```bash 
$ mysql_tzinfo_to_sql /usr/share/zoneinfo | mysql -u root -p mysql
```

### Tạo cơ sở dữ liệu

```bash
$ mysql -u root -p
```

```sql
MariaDB [(none)]> CREATE DATABASE dmoj DEFAULT CHARACTER SET utf8mb4 DEFAULT COLLATE utf8mb4_general_ci;

MariaDB [(none)]> GRANT ALL PRIVILEGES ON dmoj.* to 'tmath'@'localhost' IDENTIFIED BY 'tmath123@';

MariaDB [(none)]> exit;
```

## Cài đặt trang web

### Tạo thư mục

```bash
$ git clone https://github.com/nguyenductoandhv/tmath.git
$ cd tmath
```

### Cài đặt môi trường ảo Python

```bash
$ python3 -m venv venv
$ source venv/bin/activate
(venv) $ pip3 install --upgrade pip
(venv) $ pip3 install -r requirements.txt
(venv) $ pip3 install mysqlclient
```

### Cài đặt submodule

```bash
$ git submodule update --init --recursive
```

### Tạo local_settings.py

```bash
$ cp tmath/local_settings.py.example tmath/local_settings.py
```

### Biên dịch assets

```bash
$ npm install -D tailwindcss@latest
$ npm install -D @tailwindcss/typography@latest @tailwindcss/forms@latest
$ npx tailwindcss -i resources/main.css -o resources/full_style.css
```

```bash
(venv) $ python3 manage.py collectstatic
(venv) $ python3 manage.py compilemessages
(venv) $ python3 manage.py compilejsi18n
```

### Migrate cơ sở dữ liệu

```bash
(venv) $ python3 manage.py migrate
```

## Deploy

### Cài đặt UWSGI

```bash
(venv) $ pip3 install uwsgi
```

### Cài đặt Supervisor

Tạo 4 file cấu hình chạy:

- `site.conf`: Cấu hình chạy UWSGI
- `celery.conf`: Cấu hình chạy Celery
- `bridge.conf`: Cấu hình chạy Bridge

```bash
$ sudo cp deploy/site.conf /etc/supervisor/conf.d/site.conf
$ sudo cp deploy/celery.conf /etc/supervisor/conf.d/celery.conf
$ sudo cp deploy/bridge.conf /etc/supervisor/conf.d/bridge.conf
```

```bash
$ sudo supervisorctl reread
$ sudo supervisorctl update
$ sudo supervisorctl restart all
```

### Cài đặt Nginx

Chú ý: Kiểm tra quyền đọc file của thư mục /home/ubuntu

```bash
$ sudo cp deploy/nginx.conf /etc/nginx/sites-available/tmath
$ sudo ln -s /etc/nginx/sites-available/tmath /etc/nginx/sites-enabled/tmath
$ nginx -t
$ sudo systemctl restart nginx
```

## Cài đặt Socket

### Cài đặt Daphne

```bash
(venv) $ pip3 install daphne
```

### Cấu hình Supervisor

```bash
$ sudo cp deploy/socket.conf /etc/supervisor/conf.d/socket.conf
```

```bash
$ sudo supervisorctl reread
$ sudo supervisorctl update
$ sudo supervisorctl restart all
```


# Cài đặt máy chấm

Sử dụng máy chấm của VNOJ.