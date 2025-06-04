from django.contrib.auth import get_user_model
from djoser.serializers import UserCreateSerializer, UserSerializer
from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator
import base64
import os
from django.core.files.base import ContentFile

from recipes.models import (
    Ingredient,
    Recipe,
    RecipeIngredient,
    Favorite,
    ShoppingCart,
    Follow
)


# Константы для валидации
MIN_COOKING_TIME = 1
MAX_COOKING_TIME = 32000
MIN_AMOUNT = 1
MAX_AMOUNT = 32000


User = get_user_model()


class Base64ImageField(serializers.ImageField):
    """Кастомное поле для загрузки изображений в формате base64."""
    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith('data:image'):
            format, imgstr = data.split(';base64,')
            ext = format.split('/')[-1]
            data = ContentFile(base64.b64decode(imgstr), name=f'temp.{ext}')
        return super().to_internal_value(data)


class CustomUserCreateSerializer(UserCreateSerializer):
    """Сериализатор для создания пользователя."""
    class Meta:
        model = User
        fields = (
            'email',
            'id',
            'username',
            'first_name',
            'last_name',
            'password'
        )


class CustomUserSerializer(UserSerializer):
    """Сериализатор для пользователя."""
    is_subscribed = serializers.SerializerMethodField()
    avatar = Base64ImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = (
            'email',
            'id',
            'username',
            'first_name',
            'last_name',
            'is_subscribed',
            'avatar'
        )

    def get_is_subscribed(self, obj):
        """Проверка подписки на пользователя."""
        user = self.context['request'].user
        if user.is_anonymous:
            return False
        return obj.followers.filter(user=user).exists()

    def to_representation(self, instance):
        """Преобразование объекта в JSON."""
        representation = super().to_representation(instance)
        if instance.avatar:
            request = self.context.get('request')
            if request is not None:
                scheme = request.scheme
                host = request.get_host()
                if host.startswith(os.getenv('HOST')):
                    host = 'localhost'
                representation['avatar'] = (
                    f'{scheme}://{host}{instance.avatar.url}'
                )
            else:
                representation['avatar'] = instance.avatar.url
        return representation


class AvatarSerializer(serializers.ModelSerializer):
    """Сериализатор для операций с аватаром пользователя."""
    avatar = Base64ImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = ('avatar',)

    def validate_avatar(self, value):
        """Валидация аватара."""
        if not value and 'avatar' not in self.initial_data:
            raise serializers.ValidationError('Файл не найден')
        return value

    def update(self, instance, validated_data):
        """Обновление аватара."""
        if 'avatar' in validated_data:
            instance.avatar = validated_data['avatar']
            instance.save()
        return instance

    def to_representation(self, instance):
        """Преобразование объекта в JSON."""
        return CustomUserSerializer(instance, context=self.context).data


class IngredientSerializer(serializers.ModelSerializer):
    """Сериализатор для ингредиентов."""
    class Meta:
        model = Ingredient
        fields = ('id', 'name', 'measurement_unit')


class RecipeIngredientSerializer(serializers.ModelSerializer):
    """Сериализатор для ингредиентов в рецепте."""
    id = serializers.PrimaryKeyRelatedField(
        queryset=Ingredient.objects.all()
    )
    name = serializers.ReadOnlyField(source='ingredient.name')
    measurement_unit = serializers.ReadOnlyField(
        source='ingredient.measurement_unit'
    )
    amount = serializers.IntegerField(
        min_value=MIN_AMOUNT,
        max_value=MAX_AMOUNT
    )

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'name', 'measurement_unit', 'amount')

    def to_representation(self, instance):
        """Преобразование объекта в JSON."""
        representation = super().to_representation(instance)
        representation['id'] = instance.ingredient.id
        return representation


class RecipeSerializer(serializers.ModelSerializer):
    """Сериализатор для рецептов."""
    author = CustomUserSerializer(read_only=True)
    ingredients = RecipeIngredientSerializer(
        source='recipe_ingredients',
        many=True,
        read_only=True
    )
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = (
            'id',
            'author',
            'ingredients',
            'is_favorited',
            'is_in_shopping_cart',
            'name',
            'image',
            'text',
            'cooking_time'
        )

    def get_is_favorited(self, obj):
        """Проверка нахождения рецепта в избранном."""
        user = self.context['request'].user
        if user.is_anonymous:
            return False
        return user.favorites.filter(recipe=obj).exists()

    def get_is_in_shopping_cart(self, obj):
        """Проверка нахождения рецепта в списке покупок."""
        user = self.context['request'].user
        if user.is_anonymous:
            return False
        return user.shopping_cart.filter(recipe=obj).exists()

    def to_representation(self, instance):
        """Преобразование объекта в JSON."""
        representation = super().to_representation(instance)
        if instance.image:
            request = self.context.get('request')
            if request is not None:
                scheme = request.scheme
                host = request.get_host()
                if host.startswith(os.getenv('HOST')):
                    host = 'localhost'
                representation['image'] = (
                    f'{scheme}://{host}{instance.image.url}'
                )
            else:
                representation['image'] = instance.image.url

        # Добавляем информацию о подписке для автора
        if instance.author:
            user = self.context['request'].user
            if not user.is_anonymous:
                representation['author']['is_subscribed'] = (
                    instance.author.followers.filter(
                        user=user
                    ).exists()
                )
            else:
                representation['author']['is_subscribed'] = False

        return representation


class RecipeCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания рецепта."""
    ingredients = RecipeIngredientSerializer(many=True)
    image = Base64ImageField()
    cooking_time = serializers.IntegerField(
        min_value=MIN_COOKING_TIME,
        max_value=MAX_COOKING_TIME
    )

    class Meta:
        model = Recipe
        fields = (
            'ingredients',
            'image',
            'name',
            'text',
            'cooking_time'
        )

    def create(self, validated_data):
        """Создание рецепта."""
        ingredients_data = validated_data.pop('ingredients')
        recipe = Recipe.objects.create(**validated_data)
        self._create_ingredients(recipe, ingredients_data)
        return recipe

    def update(self, instance, validated_data):
        """Обновление рецепта."""
        ingredients_data = validated_data.pop('ingredients')
        instance = super().update(instance, validated_data)
        instance.ingredients.clear()
        self._create_ingredients(instance, ingredients_data)
        return instance

    def _create_ingredients(self, recipe, ingredients_data):
        """Создание связей рецепта с ингредиентами."""
        ingredients = [
            RecipeIngredient(
                recipe=recipe,
                ingredient=ingredient_data['id'],
                amount=ingredient_data['amount']
            )
            for ingredient_data in ingredients_data
        ]
        RecipeIngredient.objects.bulk_create(ingredients)

    def to_representation(self, instance):
        """Преобразование объекта в JSON."""
        return RecipeSerializer(instance, context=self.context).data


class RecipeMinifiedSerializer(serializers.ModelSerializer):
    """Сериализатор для краткого отображения рецепта."""
    class Meta:
        model = Recipe
        fields = ('id', 'name', 'image', 'cooking_time')

    def to_representation(self, instance):
        """Преобразование объекта в JSON."""
        representation = super().to_representation(instance)
        if instance.image:
            request = self.context.get('request')
            if request is not None:
                # Формируем полный URL с учетом прокси
                scheme = request.scheme
                host = request.get_host()
                if host.startswith(os.getenv('HOST')):
                    host = 'localhost'
                representation['image'] = (
                    f'{scheme}://{host}{instance.image.url}'
                )
            else:
                representation['image'] = instance.image.url
        return representation


class FavoriteSerializer(serializers.ModelSerializer):
    """Сериализатор для избранного."""
    class Meta:
        model = Favorite
        fields = ('user', 'recipe')
        validators = [
            UniqueTogetherValidator(
                queryset=Favorite.objects.all(),
                fields=('user', 'recipe'),
                message='Рецепт уже в избранном'
            )
        ]


class ShoppingCartSerializer(serializers.ModelSerializer):
    """Сериализатор для списка покупок."""
    class Meta:
        model = ShoppingCart
        fields = ('user', 'recipe')
        validators = [
            UniqueTogetherValidator(
                queryset=ShoppingCart.objects.all(),
                fields=('user', 'recipe'),
                message='Рецепт уже в списке покупок'
            )
        ]


class RecipeShortLinkSerializer(serializers.ModelSerializer):
    """Сериализатор для короткой ссылки рецепта."""
    short_link = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = ('short_link',)

    def get_short_link(self, obj):
        """Получение или генерация короткой ссылки."""
        if not obj.short_link:
            obj.generate_short_link()

        request = self.context.get('request')
        scheme = request.scheme
        host = request.get_host()
        if host.startswith(os.getenv("HOST")):
            host = 'localhost:3000'
        return f'{scheme}://{host}/api/recipes/short/{obj.short_link}/'

    def to_representation(self, instance):
        """Преобразование объекта в JSON."""
        representation = super().to_representation(instance)
        return {'short-link': representation['short_link']}


class SubscriptionSerializer(serializers.ModelSerializer):
    """Сериализатор для подписок."""
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.SerializerMethodField()
    is_subscribed = serializers.SerializerMethodField()
    avatar = Base64ImageField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = (
            'email',
            'id',
            'username',
            'first_name',
            'last_name',
            'is_subscribed',
            'recipes',
            'recipes_count',
            'avatar'
        )

    def get_recipes(self, obj):
        """Получение рецептов автора."""
        request = self.context.get('request')
        recipes_limit = request.query_params.get('recipes_limit', 3)
        recipes = obj.recipes.all()[:int(recipes_limit)]
        return RecipeMinifiedSerializer(
            recipes,
            many=True,
            context=self.context
        ).data

    def get_recipes_count(self, obj):
        """Получение количества рецептов автора."""
        return obj.recipes.count()

    def get_is_subscribed(self, obj):
        """Проверка подписки на пользователя."""
        return True

    def to_representation(self, instance):
        """Преобразование объекта в JSON."""
        representation = super().to_representation(instance)
        if instance.avatar:
            request = self.context.get('request')
            if request is not None:
                scheme = request.scheme
                host = request.get_host()
                if host.startswith(os.getenv("HOST")):
                    host = 'localhost:3000'
                representation['avatar'] = (
                    f'{scheme}://{host}{instance.avatar.url}'
                )
            else:
                representation['avatar'] = instance.avatar.url
        return representation


class SubscriptionCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания подписки."""
    class Meta:
        model = Follow
        fields = ('user', 'author')

    def validate(self, data):
        """Валидация данных подписки."""
        user = data['user']
        author = data['author']

        if user == author:
            raise serializers.ValidationError(
                'Нельзя подписаться на самого себя'
            )
        if user.following.filter(id=author.id).exists():
            raise serializers.ValidationError(
                'Вы уже подписаны на этого пользователя'
            )
        return data


class SubscriptionDeleteSerializer(serializers.ModelSerializer):
    """Сериализатор для удаления подписки."""
    class Meta:
        model = Follow
        fields = ('user', 'author')

    def validate(self, data):
        """Валидация данных подписки."""
        user = data['user']
        author = data['author']

        if not author.followers.filter(user=user).exists():
            raise serializers.ValidationError(
                'Вы не подписаны на этого пользователя'
            )
        return data
