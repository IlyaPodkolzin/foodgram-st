# ДИПЛОМНЫЙ ПРОЕКТ FOODGRAM по дисциплине "Бекэнд-разработка" от Яндекс.Практикума

## Подготовка приложения:

### 1. Переменные окружения

Создайте файл backend/.env

```
DEBUG=False
SECRET_KEY='your-secret-key-here'
ALLOWED_HOSTS=localhost,127.0.0.1
DB_ENGINE=django.db.backends.postgresql
POSTGRES_DB=foodgram_db
POSTGRES_USER='your_user'
POSTGRES_PASSWORD='your_password'
DB_HOST=db
DB_PORT=5432
HOST=localhost:3000
```

Создайте файл backend/foodgram/.env

```
POSTGRES_DB=foodgram_db
POSTGRES_USER='your_user'
POSTGRES_PASSWORD='your_password'
DB_HOST=localhost
DB_PORT=5432
```

### 2. Сборка проекта

Перейдя в директорию /infra, выполните команду docker-compose up

### 3. Применение миграций

Оставаясь в той же директории, выполните применение миграций в базе данных:

```
docker-compose exec backend python manage.py makemigrations
docker-compose exec backend python manage.py migrate
```

### 4. Загрузка статических файлов

Оставаясь в той же директории, загрузите статические файлы с помощью комманды:

```
docker-compose exec backend python manage.py collectstatic --noinput
```

Очистите кэш, чтобы статические файлы отобразились.

### 5. Загрузка ингредиентов

Для загрузки ингредиентов из файла data/ingredients.csv, воспользуйтесь командой:

```
docker-compose exec backend python manage.py import_ingredients
```

### По адресу http://localhost изучите фронтенд веб-приложения, а по адресу http://localhost/api/docs/ — спецификацию API.

