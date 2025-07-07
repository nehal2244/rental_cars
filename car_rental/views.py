from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, render, redirect
from car_rental.models import Car, Booking
from car_rental.forms import PaymentForm, BookingForm
from datetime import datetime
from django.utils.timezone import make_aware
from django.core.mail import send_mail
from django.conf import settings
from decimal import Decimal
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone


timezone.now()



def index(request):
    return render(request, 'index.html')


def browse_cars(request):
    cars = Car.objects.all()
    error = None

    search_query = request.GET.get('search', '')
    car_type = request.GET.get('car_type', '')
    transmission = request.GET.get('transmission', '')
    sort = request.GET.get('sort', '')

    start_date = request.GET.get('start_date')
    start_time = request.GET.get('start_time')
    end_date = request.GET.get('end_date')
    end_time = request.GET.get('end_time')

    calculated_prices = {}
    calculated_included_kms = {}  # ✅ NEW

    if all([start_date, start_time, end_date, end_time]):
        try:
            start_datetime = make_aware(datetime.strptime(f"{start_date} {start_time}", "%Y-%m-%d %I:%M %p"))
            end_datetime = make_aware(datetime.strptime(f"{end_date} {end_time}", "%Y-%m-%d %I:%M %p"))

            if end_datetime <= start_datetime:
                error = "Drop-off must be after pickup."
            else:
                booked_car_ids = Booking.objects.filter(
                    start_datetime__lt=end_datetime,
                    end_datetime__gt=start_datetime
                ).values_list('car_id', flat=True)

                cars = cars.exclude(id__in=booked_car_ids)

                rental_hours = (end_datetime - start_datetime).total_seconds() / 3600
                rental_hours_decimal = Decimal(str(rental_hours))
                estimated_km = rental_hours_decimal * Decimal(15)

                for car in cars:
                    car.dynamic_price_150km = float(car.calculate_price(rental_hours_decimal, '150km', total_km_driven=estimated_km))
                    car.dynamic_price_unlimited = float(car.calculate_price(rental_hours_decimal, 'unlimited'))

                    # ✅ FIXED: Pass '150km' to get dynamic included kms
                    calculated_included_kms[car.id] = car.get_included_kms(rental_hours_decimal, '150km')

        except ValueError:
            error = "Invalid date or time format."
        except Exception:
            pass

    if search_query:
        cars = cars.filter(name__icontains=search_query)

    if car_type:
        cars = cars.filter(car_type=car_type)

    if transmission:
        cars = cars.filter(transmission__iexact=transmission)

    if sort == 'price_low':
        cars = cars.order_by('price_150km')
    elif sort == 'price_high':
        cars = cars.order_by('-price_150km')

    if all([start_date, start_time, end_date, end_time]) and not error:
        try:
            start_datetime = make_aware(datetime.strptime(f"{start_date} {start_time}", "%Y-%m-%d %I:%M %p"))
            end_datetime = make_aware(datetime.strptime(f"{end_date} {end_time}", "%Y-%m-%d %I:%M %p"))
            rental_hours = (end_datetime - start_datetime).total_seconds() / 3600
            rental_hours_decimal = Decimal(str(rental_hours))
            estimated_km = rental_hours_decimal * Decimal(15)

            for car in cars:
                calculated_prices[car.id] = {
                    '150km': round(float(car.calculate_price(rental_hours_decimal, '150km', total_km_driven=estimated_km)), 2),
                    'unlimited': round(float(car.calculate_price(rental_hours_decimal, 'unlimited')), 2),
                }
        except Exception:
            pass

    context = {
        'cars': cars,
        'search_query': search_query,
        'car_type': car_type,
        'transmission': transmission,
        'sort': sort,
        'start_date': start_date,
        'start_time': start_time,
        'end_date': end_date,
        'end_time': end_time,
        'error': error,
        'calculated_prices': calculated_prices,
        'calculated_included_kms': calculated_included_kms,  # ✅ PASSED TO TEMPLATE
    }

    return render(request, 'browse_cars.html', context)


def car_detail(request, pk):
    car = get_object_or_404(Car, pk=pk)
    return render(request, 'car_detail.html', {'car': car})


def pay_online(request):
    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            # Payment processing logic here
            return redirect('payment_success')
    else:
        form = PaymentForm()
    return render(request, 'pay_online.html', {'form': form})


def payment_success(request):
    return render(request, 'payment_success.html')


def about(request):
    return render(request, "about.html")

from decimal import Decimal

def car_book(request, pk):
    car = get_object_or_404(Car, pk=pk)

    start_date = request.GET.get('start_date')
    start_time = request.GET.get('start_time') or "10:00 AM"
    end_date = request.GET.get('end_date')
    end_time = request.GET.get('end_time') or "10:00 AM"
    kms = request.GET.get('kms') or "150km"

    hours_float = 0.0
    estimated_km = 0.0
    included_kms = 0

    try:
        start_datetime = make_aware(datetime.strptime(f"{start_date} {start_time}", "%Y-%m-%d %I:%M %p"))
        end_datetime = make_aware(datetime.strptime(f"{end_date} {end_time}", "%Y-%m-%d %I:%M %p"))
        hours_float = round((end_datetime - start_datetime).total_seconds() / 3600, 2)
        estimated_km = hours_float * 15
        included_kms = car.get_included_kms(Decimal(str(hours_float)), kms)
    except Exception:
        start_datetime = None
        end_datetime = None

    try:
        price = float(car.calculate_price(Decimal(str(hours_float)), kms, total_km_driven=Decimal(str(estimated_km))))
    except Exception:
        price = 0.0

    try:
        price_150 = round(car.calculate_price(Decimal(str(hours_float)), '150km', total_km_driven=Decimal(str(estimated_km))), 2)
        price_unlimited = round(car.calculate_price(Decimal(str(hours_float)), 'unlimited'), 2)
    except Exception:
        price_150 = 0.0
        price_unlimited = 0.0

    initial_data = {}
    if start_datetime:
        initial_data['start_datetime'] = start_datetime
    if end_datetime:
        initial_data['end_datetime'] = end_datetime

    if request.method == 'POST':
        form = BookingForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            kms_post = request.POST.get('kms') or kms
            hours_float_post = round((data['end_datetime'] - data['start_datetime']).total_seconds() / 3600, 2)
            estimated_km_post = hours_float_post * 15

            # ✅ Included kms for email message
            included_kms_post = car.get_included_kms(Decimal(str(hours_float_post)), kms_post)

            try:
                price_post = float(car.calculate_price(Decimal(str(hours_float_post)), kms_post, total_km_driven=Decimal(str(estimated_km_post))))
            except Exception as e:
                print(f"❌ Error calculating price: {e}")
                price_post = 0.0

            if data['end_datetime'] <= data['start_datetime']:
                form.add_error('end_datetime', 'End datetime must be after start datetime.')
            elif data['start_datetime'] < timezone.now():
                form.add_error('start_datetime', 'Start datetime cannot be in the past.')
            else:
                booking = Booking.objects.create(
                    car=car,
                    start_datetime=data['start_datetime'],
                    end_datetime=data['end_datetime'],
                    user_email=data['email']
                )

                request.session[f'booking_info_{booking.id}'] = {
                    'full_name': data['full_name'],
                    'phone': data['phone'],
                    'email': data['email'],
                    'kms_plan': kms_post,
                }

                approval_link = request.build_absolute_uri(reverse('approve_booking', args=[str(booking.approval_token)]))

                # ✅ Updated message with included kms
                message = (
                    f"🚗 Booking Request: {car.name}\n\n"
                    f"Full Name: {data['full_name']}\n"
                    f"Email: {data['email']}\n"
                    f"Phone: {data['phone']}\n\n"
                    f"Pickup Date & Time: {data['start_datetime'].strftime('%d-%m-%Y %H:%M')}\n"
                    f"Drop-off Date & Time: {data['end_datetime'].strftime('%d-%m-%Y %H:%M')}\n"
                    f"Kilometers Plan: {kms_post} ({included_kms_post} km)\n"
                    f"Rental Hours: {hours_float_post} hours\n"
                    f"Estimated Price: ₹{price_post:.2f}\n\n"
                    f"✅ Approve here: {approval_link}"
                )

                send_mail(
                    subject=f"New Booking Request - {car.name}",
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.MANAGER_EMAIL],
                    fail_silently=False,
                )
                return redirect('booking_pending')
    else:
        form = BookingForm(initial=initial_data)

    context = {
        'car': car,
        'form': form,
        'start_date': start_date,
        'start_time': start_time,
        'end_date': end_date,
        'end_time': end_time,
        'hours': hours_float,
        'kms': kms,
        'price': price,
        'price_150': price_150,
        'price_unlimited': price_unlimited,
        'included_kms': included_kms,
    }

    return render(request, 'car_book.html', context)


def booking_pending(request):
    return render(request, 'booking_pending.html')


def approve_booking(request, token):
    booking = get_object_or_404(Booking, approval_token=token)

    if not booking.is_approved:
        booking.is_approved = True

        session_key = f'booking_info_{booking.id}'
        extra_info = request.session.get(session_key)

        if extra_info:
            booking.full_name = extra_info.get('full_name')
            booking.phone = extra_info.get('phone')
            booking.user_email = extra_info.get('email')
            del request.session[session_key]

        booking.save()

        success_link = request.build_absolute_uri(
            reverse('booking_success', args=[booking.id])
        )

        send_mail(
            subject="Your booking is approved!",
            message=(
                f"Dear {booking.full_name},\n\n"
                f"Your booking for {booking.car.name} has been approved.\n"
                f"Pickup: {booking.start_datetime.strftime('%d-%m-%Y %H:%M')}\n"
                f"Drop-off: {booking.end_datetime.strftime('%d-%m-%Y %H:%M')}\n"
                f"You can view confirmation details here:\n{success_link}"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[booking.user_email],
            fail_silently=False,
        )

    # ✅ Instead of rendering a separate approved page, redirect to the success page
    return redirect('booking_success', booking_id=booking.id)


def booking_success(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)

    if not booking.is_approved:
        return render(request, 'booking_pending.html', {'car': booking.car})

    return render(request, 'booking_success.html', {'booking': booking})



def get_dynamic_prices(request):
    def parse_datetime_flexible(date_str, time_str):
        try:
            return make_aware(datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %I:%M %p"))
        except ValueError:
            try:
                return make_aware(datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M"))
            except ValueError:
                return None

    # ✅ Get the parameters from the URL
    start_date = request.GET.get('start_date')
    start_time = request.GET.get('start_time')
    end_date = request.GET.get('end_date')
    end_time = request.GET.get('end_time')
    car_id = request.GET.get('car_id')

    # ✅ Check if all fields are given
    if not all([start_date, start_time, end_date, end_time, car_id]):
        return JsonResponse({'error': 'Missing data'}, status=400)

    # ✅ Convert date & time to datetime objects
    start_datetime = parse_datetime_flexible(start_date, start_time)
    end_datetime = parse_datetime_flexible(end_date, end_time)

    if not start_datetime or not end_datetime:
        return JsonResponse({'error': 'Invalid date/time format'}, status=400)

    # ✅ Calculate rental hours and estimated km
    rental_hours = (end_datetime - start_datetime).total_seconds() / 3600
    rental_hours_decimal = Decimal(str(rental_hours))
    estimated_km = rental_hours_decimal * Decimal(15)

    try:
        # ✅ Get the Car from the database
        car = Car.objects.get(id=car_id)

        # ✅ Calculate dynamic prices and kms
        prices = {
            '150km': round(float(car.calculate_price(rental_hours_decimal, '150km', total_km_driven=estimated_km)), 2),
            'unlimited': round(float(car.calculate_price(rental_hours_decimal, 'unlimited')), 2),
        }

        included_kms = {
            '150km': car.get_included_kms(rental_hours_decimal, '150km'),
            'unlimited': 'Unlimited',
        }

        # ✅ Send back the results as JSON
        return JsonResponse({
            'prices': prices,
            'included_kms': included_kms,
            'rental_hours': round(rental_hours, 2),
        })

    except Car.DoesNotExist:
        return JsonResponse({'error': 'Car not found'}, status=404)


def contactus(request):
    return render(request, "contactus.html")
