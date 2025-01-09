from django.contrib import admin
from .models import Order, Flower, CartItem, Report, Review
from django.utils.timezone import now


# Регистрируем модель Order
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'get_flowers', 'get_total_quantity', 'delivery_date', 'status')
    list_filter = ('status', 'delivery_date', 'user')  # Фильтры по статусу, дате и пользователю
    actions = ['repeat_order']  # Добавляем действие для повторного заказа

    def get_flowers(self, obj):
        if obj.cart:
            return ", ".join([f"{item.flower.name} ({item.quantity} шт.)" for item in obj.cart.items.all()])
        return "Нет товаров"

    def get_total_quantity(self, obj):
        if obj.cart:
            return sum(item.quantity for item in obj.cart.items.all())
        return 0

    def repeat_order(self, request, queryset):
        """Повторить заказ для выбранных заказов"""
        for order in queryset:
            # Создаем новый заказ на основе старого
            new_order = Order.objects.create(
                user=order.user,
                cart=order.cart,
                delivery_date=order.delivery_date,
                delivery_time=order.delivery_time,
                address=order.address,
                status='pending',  # Статус нового заказа
                comment=order.comment
            )
            self.message_user(request, f"Order {order.id} successfully repeated as Order {new_order.id}.")

    repeat_order.short_description = "Повторить заказ"


# Регистрируем модель Review
@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('flower', 'user', 'rating', 'comment', 'created_at')  # Поля, которые будут отображаться в списке
    list_filter = ('rating', 'created_at', 'flower')  # Фильтры для сортировки
    search_fields = ('user__username', 'flower__name', 'comment')  # Поиск по имени пользователя, продукту и комментарию
    ordering = ('-created_at',)  # Сортировка по дате создания (по убыванию)

    # Добавляем кастомное действие для удаления всех отзывов
    actions = ['delete_all_reviews']

    def delete_all_reviews(self, request, queryset):
        """Удалить все выбранные отзывы"""
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f"{count} review(s) were successfully deleted.")

    delete_all_reviews.short_description = "Удалить все выбранные отзывы"


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('date', 'total_orders', 'total_sales', 'total_revenue', 'total_expenses', 'profit')
    actions = ['generate_report']

    def generate_report(self, request, queryset):
        """Генерация отчетов за выбранные даты"""
        for report in queryset:
            # Генерация отчета за выбранный период
            report.calculate_report()
            self.message_user(request, f"Report for {report.date} generated successfully.")

    generate_report.short_description = "Генерировать отчет за период"


admin.site.register(Flower)
admin.site.register(CartItem)
