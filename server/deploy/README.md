# Deployment Guide

## Prerequisites

- Server with nginx installed
- Domain DNS configured: manga.smoreg.dev -> server IP

## Setup Steps

### 1. Create directories

```bash
sudo mkdir -p /opt/mangaoff/{bin,data/chapters,data/covers}
sudo chown -R www-data:www-data /opt/mangaoff
```

### 2. Deploy binary

```bash
# From local machine
make deploy
```

### 3. Setup nginx

```bash
sudo cp nginx-manga.smoreg.dev.conf /etc/nginx/sites-available/manga.smoreg.dev
sudo ln -s /etc/nginx/sites-available/manga.smoreg.dev /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 4. Setup SSL

```bash
sudo certbot --nginx -d manga.smoreg.dev
```

### 5. Setup systemd service

```bash
sudo cp mangaoff.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable mangaoff
sudo systemctl start mangaoff
```

### 6. Upload data

```bash
# From parser output directory
rsync -avz --progress output/ user@smoreg.dev:/opt/mangaoff/data/
```

## Verify

```bash
curl https://manga.smoreg.dev/health
curl https://manga.smoreg.dev/api/v1/manga
```
