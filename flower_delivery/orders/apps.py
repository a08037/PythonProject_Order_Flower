from django.apps import AppConfig


class OrdersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'orders111'

class MyAppConfig(AppConfig):
    name = 'orders111'  # Укажите имя вашего приложения

    def ready(self):
        import myapp.signals  # Подключаем сигналы