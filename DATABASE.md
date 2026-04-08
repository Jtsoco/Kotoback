## Dev database (Postgres) setup

This repo uses Postgres for the Django dev database via Docker Compose.

### Prereqs

- Docker Desktop installed and running
- Python venv with backend deps installed:

```bash
cd Kotoback
pip install -r requirements.txt
```

### 1) Start Postgres

From the repo root (same folder as `docker-compose.yml`):

```bash
docker compose up -d
```

If you get an error about not being able to connect to the Docker daemon, start Docker Desktop first, wait until it says it’s running, then re-run the command above.

Confirm it’s healthy:

```bash
docker compose ps
```

### 2) Configure Django env

Copy the example env file:

```bash
cp Kotoback/.env.example Kotoback/.env
```

Defaults are set to match the Docker Compose container:

- **DB name**: `kotoback_dev`
- **DB user**: `kotoback`
- **DB password**: `kotoback`
- **DB host/port**: `127.0.0.1:5432`

### 3) Run migrations

```bash
cd Kotoback
python manage.py makemigrations
python manage.py migrate
```

### 4) (Optional) Create an admin user

```bash
cd Kotoback
python manage.py createsuperuser
```

### 5) Start Django

```bash
cd Kotoback
python manage.py runserver
```

### Stop / restart / wipe the database

- **Stop** (keeps data):

```bash
docker compose stop
```

- **Start again**:

```bash
docker compose start
```

- **Shut down** (keeps data):

```bash
docker compose down
```

- **Wipe all Postgres data** (irreversible):

```bash
docker compose down -v
```

### Connecting with a GUI (TablePlus / DBeaver / DataGrip)

- **Host**: `127.0.0.1`
- **Port**: `5432`
- **Database**: `kotoback_dev`
- **User**: `kotoback`
- **Password**: `kotoback`

