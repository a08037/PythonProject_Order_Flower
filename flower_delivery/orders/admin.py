from django.contrib import admin
from django.utils.timezone import now
from .models import Order, Flower, CartItem, Report, Review

# Регистрируем модель Order
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'get_flowers', 'get_total_quantity', 'delivery_date', 'status', 'address')
    list_filter = ('status', 'delivery_date', 'user')  # Фильтры по статусу, дате и пользователю
    search_fields = ('user__username', 'address')  # Поиск по пользователю и адресу
    actions = ['repeat_order', 'mark_as_confirmed', 'mark_as_delivered', 'mark_as_pending']  # Действия для изменения статуса

    def get_flowers(self, obj):
        if obj.cart:
            return ", ".join([f"{item.flower.name} ({item.quantity} шт.)" for item in obj.cart.items.all()])
        return "Нет товаров"

    get_flowers.short_description = "Цветы"

    def get_total_quantity(self, obj):
        if obj.cart:
            return sum(item.quantity for item in obj.cart.items.all())
        return 0

    get_total_quantity.short_description = "Общее количество"

    def repeat_order(self, request, queryset):
        """Повторить заказ для выбранных заказов"""
        for order in queryset:
            if not order.cart.items.exists():
                self.message_user(request, f"Заказ {order.id} не может быть повторен, так как корзина пуста.")
                continue  # Если корзина пуста, пропускаем заказ

            # Проверка, что заказ не был доставлен или отменен
            if order.status in ['delivered', 'canceled']:
                self.message_user(request,
                                  f"Заказ {order.id} не может быть повторен, так как он уже был доставлен или отменен.")
                continue

            # Дополнительная проверка: есть ли товары в корзине
            if order.cart.items.count() == 0:
                self.message_user(request, f"Корзина для заказа {order.id} пуста, повторный заказ невозможен.")
                continue

            # Создаем новый заказ на основе старого
            try:
                new_order = Order.objects.create(
                    user=order.user,
                    cart=order.cart,
                    delivery_date=order.delivery_date,
                    delivery_time=order.delivery_time,
                    address=order.address,
                    status='pending',  # Статус нового заказа
                    comment=order.comment
                )

                # Логирование успешного создания заказа
                self.message_user(request, f"Заказ {order.id} успешно повторен как заказ {new_order.id}.")

            except Exception as e:
                # Логирование ошибки
                self.message_user(request, f"Ошибка при повторе заказа {order.id}: {str(e)}", level='error')
                continue  # Пропускаем заказ, если возникла ошибка

    # Действия для изменения статуса
    def mark_as_confirmed(self, request, queryset):
        updated = queryset.update(status='confirmed')
        self.message_user(request, f'{updated} заказов отмечено как подтвержденные.')

    def mark_as_delivered(self, request, queryset):
        updated = queryset.update(status='delivered')
        self.message_user(request, f'{updated} заказов отмечено как доставленные.')

    def mark_as_pending(self, request, queryset):
        updated = queryset.update(status='pending')
        self.message_user(request, f'{updated} заказов возвращено в статус "в ожидании".')

    repeat_order.short_description = "Повторить заказ"
    mark_as_confirmed.short_description = "Отметить как подтвержденные"
    mark_as_delivered.short_description = "Отметить как доставленные"
    mark_as_pending.short_description = "Отметить как в ожидании"

# Регистрируем модель Review
@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('flower', 'user', 'rating', 'comment', 'created_at')  # Поля, которые будут отображаться в списке
    list_filter = ('rating', 'created_at', 'flower')  # Фильтры для сортировки
    search_fields = ('user__username', 'flower__name', 'comment')  # Поиск по имени пользователя, продукту и комментарию
    ordering = ('-created_at',)  # Сортировка по дате создания (по убыванию)
    actions = ['delete_all_reviews']

    def delete_all_reviews(self, request, queryset):
        """Удалить все выбранные отзывы"""
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f"{count} review(s) were successfully deleted.")

    delete_all_reviews.short_description = "Удалить все выбранные отзывы"

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('start_date', 'end_date', 'total_orders', 'total_sales', 'profit', 'created_at')
    search_fields = ('start_date', 'end_date')
    actions = ['generate_report']

    def generate_report(self, request, queryset):
        """Генерация отчетов за выбранные даты"""
        for report in queryset:
            report.calculate_report()  # Пересчитываем данные отчета
            report.save()  # Сохраняем изменения в отчете
            self.message_user(request, f"Отчет за период с {report.start_date} по {report.end_date} был успешно обновлен.")

    generate_report.short_description = "Пересчитать и обновить отчет"

admin.site.register(Flower)
admin.site.register(CartItem)

