from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.http import HttpResponse
from djoser.views import UserViewSet
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination

from recipes.models import (
    Ingredient,
    Recipe,
    RecipeIngredient,
    Favorite,
    ShoppingCart
)
from .serializers import (
    CustomUserSerializer,
    IngredientSerializer,
    RecipeSerializer,
    RecipeCreateSerializer,
    RecipeMinifiedSerializer,
    FavoriteSerializer,
    ShoppingCartSerializer,
    RecipeShortLinkSerializer,
    SubscriptionSerializer,
    SubscriptionCreateSerializer,
    SubscriptionDeleteSerializer,
    AvatarSerializer
)
from .permissions import IsAuthorOrReadOnly, IsOwnerOrReadOnly

User = get_user_model()


class CustomPagination(PageNumberPagination):
    """Кастомная пагинация."""
    page_size = 6
    page_size_query_param = 'limit'


class CustomUserViewSet(UserViewSet):
    """Представление для пользователей."""
    queryset = User.objects.all()
    serializer_class = CustomUserSerializer
    permission_classes = [IsOwnerOrReadOnly]
    pagination_class = CustomPagination

    def get_permissions(self):
        """Выбор разрешений в зависимости от действия."""
        if self.action in ('list', 'retrieve', 'create'):
            return []
        return super().get_permissions()

    @action(
        detail=False,
        methods=['put', 'delete'],
        permission_classes=[IsAuthenticated],
        url_path='me/avatar'
    )
    def avatar(self, request):
        """Загрузка/удаление аватара пользователя."""
        user = request.user
        if request.method == 'PUT':
            serializer = AvatarSerializer(user, data=request.data,
                                          context={'request': request})
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)

        if request.method == 'DELETE':
            if not user.avatar:
                return Response(
                    {'error': 'Аватар не найден'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            user.avatar.delete()
            user.save()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=['post', 'delete'],
        permission_classes=[IsAuthenticated]
    )
    def subscribe(self, request, id=None):
        """Подписка/отписка на пользователя."""
        user = request.user
        author = get_object_or_404(User, id=id)

        if request.method == 'POST':
            serializer = SubscriptionCreateSerializer(
                data={'user': user.id, 'author': author.id}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(
                SubscriptionSerializer(
                    author,
                    context={'request': request}
                ).data,
                status=status.HTTP_201_CREATED
            )

        if request.method == 'DELETE':
            serializer = SubscriptionDeleteSerializer(
                data={'user': user.id, 'author': author.id}
            )
            serializer.is_valid(raise_exception=True)
            author.followers.filter(user=user).delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=False,
        permission_classes=[IsAuthenticated]
    )
    def subscriptions(self, request):
        """Получение списка подписок."""
        user = request.user
        # Получаем авторов из подписок
        authors = User.objects.filter(followers__user=user)
        page = self.paginate_queryset(authors)
        if page is not None:
            serializer = SubscriptionSerializer(
                page,
                many=True,
                context={'request': request}
            )
            return self.get_paginated_response(serializer.data)
        serializer = SubscriptionSerializer(
            authors,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data)


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    """Представление для ингредиентов."""
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    pagination_class = None  # Отключаем пагинацию

    def get_queryset(self):
        """Фильтрация ингредиентов по имени."""
        queryset = Ingredient.objects.all()
        name = self.request.query_params.get('name')
        if name:
            queryset = queryset.filter(name__istartswith=name)
        return queryset


class RecipeViewSet(viewsets.ModelViewSet):
    """Представление для рецептов."""
    queryset = Recipe.objects.all()
    permission_classes = [IsAuthorOrReadOnly]

    def get_permissions(self):
        """Выбор разрешений в зависимости от действия."""
        if self.action in ('list', 'retrieve'):
            return []
        return super().get_permissions()

    def get_serializer_class(self):
        """Выбор сериализатора в зависимости от действия."""
        if self.action in ('create', 'partial_update'):
            return RecipeCreateSerializer
        if self.action == 'get_link':
            return RecipeShortLinkSerializer
        return RecipeSerializer

    def get_queryset(self):
        """Фильтрация рецептов."""
        queryset = Recipe.objects.all()
        author = self.request.query_params.get('author')
        is_favorited = self.request.query_params.get('is_favorited')
        is_in_shopping_cart = (self.request.
                               query_params.get('is_in_shopping_cart'))
        tags = self.request.query_params.getlist('tags')

        if author:
            queryset = queryset.filter(author_id=author)
        if is_favorited:
            queryset = queryset.filter(favorites__user=self.request.user)
        if is_in_shopping_cart:
            queryset = queryset.filter(shopping_cart__user=self.request.user)
        if tags:
            queryset = queryset.filter(tags__slug__in=tags).distinct()

        return queryset

    def perform_create(self, serializer):
        """Создание рецепта."""
        serializer.save(author=self.request.user)

    @action(
        detail=True,
        methods=['get'],
        url_path='get-link'
    )
    def get_link(self, request, pk=None):
        """Получение короткой ссылки на рецепт."""
        recipe = self.get_object()
        serializer = self.get_serializer(recipe)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=['post', 'delete'],
        permission_classes=[IsAuthenticated]
    )
    def favorite(self, request, pk=None):
        """Добавление/удаление рецепта из избранного."""
        return self._handle_recipe_action(
            request, pk, Favorite, FavoriteSerializer
        )

    @action(
        detail=True,
        methods=['post', 'delete'],
        permission_classes=[IsAuthenticated]
    )
    def shopping_cart(self, request, pk=None):
        """Добавление/удаление рецепта из списка покупок."""
        return self._handle_recipe_action(
            request, pk, ShoppingCart, ShoppingCartSerializer
        )

    def _handle_recipe_action(self, request, pk, model, serializer_class):
        """Обработка действий с рецептом."""
        user = request.user
        recipe = get_object_or_404(Recipe, pk=pk)

        if request.method == 'POST':
            if model.objects.filter(user=user, recipe=recipe).exists():
                return Response(
                    {'error': 'Рецепт уже добавлен'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            serializer = serializer_class(
                data={'user': user.id, 'recipe': recipe.id}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(
                RecipeMinifiedSerializer(recipe).data,
                status=status.HTTP_201_CREATED
            )

        if request.method == 'DELETE':
            if not model.objects.filter(user=user, recipe=recipe).exists():
                return Response(
                    {'error': 'Рецепт не найден'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            model.objects.filter(user=user, recipe=recipe).delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=False,
        permission_classes=[IsAuthenticated]
    )
    def download_shopping_cart(self, request):
        """Скачивание списка покупок."""
        user = request.user
        ingredients = RecipeIngredient.objects.filter(
            recipe__shopping_cart__user=user
        ).values(
            'ingredient__name',
            'ingredient__measurement_unit'
        ).annotate(amount=Sum('amount'))

        shopping_list = ['Список покупок:\n']
        for ingredient in ingredients:
            shopping_list.append(
                f'{ingredient["ingredient__name"]} - '
                f'{ingredient["amount"]} '
                f'{ingredient["ingredient__measurement_unit"]}\n'
            )

        response = HttpResponse(
            ''.join(shopping_list),
            content_type='text/plain'
        )
        response['Content-Disposition'] = (
            'attachment; filename="shopping_list.txt"'
        )
        return response


class RecipeShortLinkView(APIView):
    """Представление для обработки коротких ссылок на рецепты."""
    def get(self, request, short_link):
        """Перенаправление на страницу рецепта по короткой ссылке."""
        recipe = get_object_or_404(Recipe, short_link=short_link)
        return redirect(f'/recipes/{recipe.id}/')
