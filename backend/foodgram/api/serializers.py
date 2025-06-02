from django.contrib.auth import get_user_model
from djoser.serializers import UserCreateSerializer, UserSerializer
from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator
import base64
from django.core.files.base import ContentFile

from recipes.models import (
    Ingredient,
    Recipe,
    RecipeIngredient,
    Favorite,
    ShoppingCart,
    Follow
)

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
        user = self.context.get('request').user
        if user.is_anonymous:
            return False
        return Follow.objects.filter(user=user, author=obj).exists()

    def to_representation(self, instance):
        """Преобразование объекта в JSON."""
        representation = super().to_representation(instance)
        if instance.avatar:
            request = self.context.get('request')
            if request is not None:
                scheme = request.scheme
                host = request.get_host()
                if host.startswith('localhost:3000'):
                    host = 'localhost'
                representation['avatar'] = (
                    f'{scheme}://{host}{instance.avatar.url}'
                )
            else:
                representation['avatar'] = instance.avatar.url
        return representation


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
    amount = serializers.IntegerField(min_value=1)

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
        user = self.context.get('request').user
        if user.is_anonymous:
            return False
        return user.favorites.filter(recipe=obj).exists()

    def get_is_in_shopping_cart(self, obj):
        """Проверка нахождения рецепта в списке покупок."""
        user = self.context.get('request').user
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
                if host.startswith('localhost:3000'):
                    host = 'localhost'
                representation['image'] = (
                    f'{scheme}://{host}{instance.image.url}'
                )
            else:
                representation['image'] = instance.image.url

        # Добавляем информацию о подписке для автора
        if instance.author:
            user = self.context.get('request').user
            if not user.is_anonymous:
                representation['author']['is_subscribed'] = (
                    Follow.objects.filter(
                        user=user,
                        author=instance.author
                    ).exists()
                )
            else:
                representation['author']['is_subscribed'] = False

        return representation


class RecipeCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания рецепта."""
    ingredients = RecipeIngredientSerializer(many=True)
    image = Base64ImageField()

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
        for ingredient_data in ingredients_data:
            RecipeIngredient.objects.create(
                recipe=recipe,
                ingredient=ingredient_data['id'],
                amount=ingredient_data['amount']
            )
        return recipe

    def update(self, instance, validated_data):
        """Обновление рецепта."""
        ingredients_data = validated_data.pop('ingredients')
        instance = super().update(instance, validated_data)
        instance.ingredients.clear()
        for ingredient_data in ingredients_data:
            RecipeIngredient.objects.create(
                recipe=instance,
                ingredient=ingredient_data['id'],
                amount=ingredient_data['amount']
            )
        return instance

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
                if host.startswith('localhost:3000'):
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
        if host.startswith('localhost:3000'):
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
                if host.startswith('localhost:3000'):
                    host = 'localhost:3000'
                representation['avatar'] = (
                    f'{scheme}://{host}{instance.avatar.url}'
                )
            else:
                representation['avatar'] = instance.avatar.url
        return representation
