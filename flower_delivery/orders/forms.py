from .models import Order, Flower, Review, Rating, Report
from django import forms

# Форма для оформления заказа
class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['quantity', 'flower', 'address', 'delivery_time', 'delivery_date']
        labels = {
            'quantity': 'Количество',
            'flower': 'Букет',
            'address': 'Адрес',
            'delivery_time': 'Время доставки',
            'delivery_date': 'Дата доставки'
        }

    flower = forms.ModelChoiceField(queryset=Flower.objects.all(), empty_label="Выберите букет", required=False)
    quantity = forms.IntegerField(min_value=1, required=False)
    address = forms.CharField(max_length=255, required=True)
    delivery_date = forms.DateField(widget=forms.SelectDateWidget(), required=True)
    delivery_time = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}), required=True)

class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['comment']
class RatingForm(forms.ModelForm):
    class Meta:
        model = Rating
        fields = ['rating']  # Поле для выставления рейтинга (например, от 1 до 5)

class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ['start_date', 'end_date']
        labels = {
            'start_date': 'Дата начала периода',
            'end_date': 'Дата окончания периода',
        }
