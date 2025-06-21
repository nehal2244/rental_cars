from django.contrib import admin  
from car_rental.models import Car, Booking

@admin.register(Car)
class CarAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'car_type',
        'seating_capacity',
        'transmission',
        'fuel_type',
        'price_150km',                # ✅ New fixed 150km plan price
        'unlimited_km_price',
        'free_kms',
        'free_km_price',
        'extra_km_charge',
        'extra_hour_charge',
        'extra_hour_charge_unlimited',
        'extra_km_per_hour_150km'     # ✅ NEW FIELD SHOWN IN LIST
    ]

    list_filter = ['car_type', 'transmission', 'fuel_type']
    search_fields = ['name']

    fields = [
        'name',
        'car_type',
        'seating_capacity',
        'transmission',
        'fuel_type',

        # Pricing fields
        'price_150km',                # ✅ Include this
        'unlimited_km_price',
        'free_kms',
        'free_km_price',
        'extra_km_charge',
        'extra_hour_charge',
        'extra_hour_charge_unlimited',
        'extra_km_per_hour_150km',    # ✅ NEW FIELD IN FORM

        # Images
        'image_file',
        'image_url',
    ]

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ['car', 'start_datetime', 'end_datetime']
    list_filter = ['car']
    search_fields = ['car__name']

    def save_model(self, request, obj, form, change):
        obj.full_clean()
        super().save_model(request, obj, form, change)
