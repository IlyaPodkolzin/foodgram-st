import hashlib
import time


def generate_short_link(recipe_id: int) -> str:
    """Генерация короткой ссылки для рецепта."""
    # Используем id и timestamp для уникальности
    unique_string = f"{recipe_id}_{time.time()}"
    # Создаем хеш
    hash_object = hashlib.md5(unique_string.encode())
    # Берем первые 8 символов хеша
    short_link = hash_object.hexdigest()[:8]

    # Проверяем уникальность
    from .models import Recipe
    while Recipe.objects.filter(short_link=short_link).exists():
        unique_string = f"{unique_string}_{time.time()}"
        hash_object = hashlib.md5(unique_string.encode())
        short_link = hash_object.hexdigest()[:8]

    return short_link
