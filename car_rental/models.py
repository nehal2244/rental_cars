from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
import uuid

class Car(models.Model):
    TRANSMISSION_CHOICES = [
        ('manual', 'Manual'),
        ('automatic', 'Automatic'),
    ]

    FUEL_CHOICES = [
        ('petrol', 'Petrol'),
        ('ev', 'Electric Vehicle'),
        ('cng', 'CNG'),
        ('petrol_cng', 'Petrol/CNG'),
    ]

    name = models.CharField(max_length=100)
    car_type = models.CharField(max_length=50)
    seating_capacity = models.PositiveIntegerField()
    transmission = models.CharField(max_length=20, choices=TRANSMISSION_CHOICES)
    fuel_type = models.CharField(max_length=10, choices=FUEL_CHOICES, default='petrol')

    # Pricing fields
    free_km_price = models.DecimalField(max_digits=8, decimal_places=2, default=0.0)
    free_kms = models.PositiveIntegerField(default=0)
    unlimited_km_price = models.DecimalField(max_digits=8, decimal_places=2, default=0.0)
    extra_km_charge = models.DecimalField(max_digits=6, decimal_places=2, default=0.0)

    extra_km_per_hour_150km = models.PositiveIntegerField(
        default=0,
        help_text="After 12 hours, extra km given per hour in 150km plan"
    )

    extra_hour_charge = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0.0,
        help_text="Charge per hour after 12 hours rental"
    )
    extra_hour_charge_unlimited = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0.0,
        help_text="Extra hour charge if unlimited km plan is selected"
    )

    price_150km = models.DecimalField(max_digits=8, decimal_places=2, default=0.0)

    image_file = models.ImageField(upload_to='car_images/', blank=True, null=True)
    image_url = models.URLField(blank=True, null=True)

    def __str__(self):
        return self.name

    def image_preview(self):
        if self.image_file:
            return self.image_file.url
        elif self.image_url:
            return self.image_url
        return ''

    def calculate_price(self, rental_hours, km_package, total_km_driven=0):
        km_price_map = {
            '150km': self.price_150km,
            'unlimited': self.unlimited_km_price,
        }
        base_price = km_price_map.get(km_package, self.price_150km)

        # Step 1: Extra hours logic
        if rental_hours <= 12:
            extra_hours = 0
            extra_price = 0
        else:
            extra_hours = rental_hours - 12
            extra_price = extra_hours * (
                self.extra_hour_charge_unlimited if km_package == 'unlimited' else self.extra_hour_charge
            )

        # Step 2: Adjust included KM dynamically
        extra_km_price = 0
        if km_package == '150km':
            included_kms = 150 + (extra_hours * self.extra_km_per_hour_150km)
            if total_km_driven > included_kms:
                extra_kms = total_km_driven - included_kms
                extra_km_price = extra_kms * self.extra_km_charge

        return base_price + extra_price + extra_km_price

    def get_included_kms(self, rental_hours, km_package):
        if km_package == '150km':
            extra_hours = max(rental_hours - 12, 0)
            return 150 + (extra_hours * self.extra_km_per_hour_150km)
        elif km_package == 'unlimited':
            return float('inf')
        return self.free_kms or 0


class Booking(models.Model):
    car = models.ForeignKey('Car', on_delete=models.CASCADE, related_name='bookings')
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()

    full_name = models.CharField(max_length=150, null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)

    user_email = models.EmailField()
    is_approved = models.BooleanField(default=False)
    approval_token = models.UUIDField(default=uuid.uuid4, editable=False, null=True)

    pickup_by_customer = models.BooleanField(default=True, help_text="Will the customer pick up the car?")
    dropoff_by_customer = models.BooleanField(default=True, help_text="Will the customer drop off the car?")

    def __str__(self):
        return f"{self.car.name} from {self.start_datetime} to {self.end_datetime}"

    def clean(self):
        if self.start_datetime is None or self.end_datetime is None:
            raise ValidationError(_('Start date and end date must be provided.'))

        if self.end_datetime <= self.start_datetime:
            raise ValidationError({'end_datetime': _('End date and time must be after start date and time.')})

        if self.start_datetime < timezone.now():
            raise ValidationError({'start_datetime': _('Booking cannot start in the past.')})

        overlapping = Booking.objects.filter(
            car=self.car,
            end_datetime__gt=self.start_datetime,
            start_datetime__lt=self.end_datetime
        )
        if self.pk:
            overlapping = overlapping.exclude(pk=self.pk)

        if overlapping.exists():
            raise ValidationError(_('This booking overlaps with an existing booking for this car.'))

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
