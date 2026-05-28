from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from ingestion.views import (
    ClientViewSet, IngestionBatchViewSet,
    NormalizedActivityViewSet, RawRecordViewSet
)

router = DefaultRouter()
router.register(r'clients', ClientViewSet, basename='client')
router.register(r'batches', IngestionBatchViewSet, basename='batch')
router.register(r'activities', NormalizedActivityViewSet, basename='activity')
router.register(r'raw-records', RawRecordViewSet, basename='rawrecord')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api/auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
