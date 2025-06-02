from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CustomUserViewSet,
    IngredientViewSet,
    RecipeViewSet,
    RecipeShortLinkView
)

app_name = 'api'

router = DefaultRouter()
router.register('users', CustomUserViewSet, basename='users')
router.register('ingredients', IngredientViewSet, basename='ingredients')
router.register('recipes', RecipeViewSet, basename='recipes')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/', include('djoser.urls.authtoken')),
    path('users/me/avatar/', CustomUserViewSet.as_view({'put': 'avatar', 'delete': 'avatar'}), name='user-avatar'),
    path('recipes/short/<str:short_link>/', RecipeShortLinkView.as_view(), name='recipe-short-link'),
] 