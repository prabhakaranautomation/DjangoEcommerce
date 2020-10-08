import random
import string
# import time
import traceback
import stripe
from django.shortcuts import render, redirect, get_object_or_404

from django.views.generic import ListView, DetailView, View, CreateView, UpdateView, DeleteView
from django.utils import timezone
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.conf import settings

from .models import Item, OrderItem, Order, Address, Payment, Coupon, Refund, UserProfile, UserCards
from .forms import CheckoutForm, CouponForm, RefundForm, PaymentForm

# stripe.api_key = settings.STRIPE_SECRET_KEY
stripe.api_key = 'sk_test_51HT8HGLDTNwpDpBQ2hJXL7wUpsxeVmMOanGkjTjcOtYxTOwnQsDPLNel93NQ0WWlUxdxEwivcGxwwXHryNnw8t9L00moxI8o7U'


def create_ref_code():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=20))


def products(request):
    context = {
        'items': Item.objects.all()
    }
    return render(request, "products.html", context)


def is_valid_form(values):
    valid = True
    for fields in values:
        if fields == '':
            valid = False
    return valid


class CheckoutView(View):
    def get(self, *args, **kwargs):
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            form = CheckoutForm()
            context = {
                'form': form,
                'couponform': CouponForm(),
                'DISPLAY_COUPON_FORM': True,
                'order': order
            }

            shipping_address_qs = Address.objects.filter(
                user=self.request.user,
                address_type='S',
                default=True
            )
            if shipping_address_qs.exists():
                context.update({'default_shipping_address': shipping_address_qs[0]})

            billing_address_qs = Address.objects.filter(
                user=self.request.user,
                address_type='B',
                default=True
            )
            if billing_address_qs.exists():
                context.update({'default_billing_address': billing_address_qs[0]})

            return render(self.request, 'checkout.html', context)
        except ObjectDoesNotExist:
            messages.info(self.request, "You do not have an active order")
            return redirect("home:checkout")

    def post(self, *args, **kwargs):
        form = CheckoutForm(self.request.POST or None)
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            # print(self.request.POST)
            if form.is_valid():
                # Shipping Address details
                use_default_shipping = form.cleaned_data.get('use_default_shipping')
                if use_default_shipping:
                    print("Using default shipping address")
                    address_qs = Address.objects.filter(
                        user=self.request.user,
                        address_type='S',
                        default=True
                    )
                    if address_qs.exists():
                        shipping_address = address_qs[0]
                        order.shipping_address = shipping_address
                        order.save()
                    else:
                        messages.info(self.request, " No default shipping address available")
                        return redirect('home:checkout')
                else:
                    print("User is entering a new shipping address")
                    shipping_address1 = form.cleaned_data.get('shipping_address')
                    shipping_address2 = form.cleaned_data.get('shipping_address2')
                    shipping_country = form.cleaned_data.get('shipping_country')
                    shipping_zip = form.cleaned_data.get('shipping_zip')

                    if is_valid_form([shipping_address1, shipping_country, shipping_zip]):
                        shipping_address = Address(
                            user=self.request.user,
                            street_address=shipping_address1,
                            apartment_address=shipping_address2,
                            country=shipping_country,
                            zip=shipping_zip,
                            address_type='S'
                        )
                        shipping_address.save()

                        order.shipping_address = shipping_address
                        order.save()

                        set_default_shipping = form.cleaned_data.get('set_default_shipping')
                        if set_default_shipping:
                            shipping_address.default = True
                            shipping_address.save()

                    else:
                        messages.info(self.request, "Please fill in the required shipping address fields")


                # Billing Address details
                use_default_billing = form.cleaned_data.get('use_default_billing')
                same_billing_address = form.cleaned_data.get('same_billing_address')
                if same_billing_address:
                    billing_address = shipping_address
                    billing_address.pk = None
                    billing_address.save()
                    billing_address.address_type = 'B'
                    billing_address.save()
                    order.billing_address = billing_address
                    order.save()

                elif use_default_billing:
                    print("Using default billing address")
                    address_qs = Address.objects.filter(
                        user=self.request.user,
                        address_type='B',
                        default=True
                    )
                    if address_qs.exists():
                        billing_address = address_qs[0]
                        order.billing_address = billing_address
                        order.save()
                    else:
                        messages.info(self.request, " No default billing address available")
                        return redirect('home:checkout')
                else:
                    print("User is entering a new billing address")
                    billing_address1 = form.cleaned_data.get('billing_address')
                    billing_address2 = form.cleaned_data.get('billing_address2')
                    billing_country = form.cleaned_data.get('billing_country')
                    billing_zip = form.cleaned_data.get('billing_zip')

                    if is_valid_form([billing_address1, billing_country, billing_zip]):
                        billing_address = Address(
                            user=self.request.user,
                            street_address=billing_address1,
                            apartment_address=billing_address2,
                            country=billing_country,
                            zip=billing_zip,
                            address_type='B'
                        )
                        billing_address.save()

                        order.billing_address = billing_address
                        order.save()

                        set_default_billing = form.cleaned_data.get('set_default_billing')
                        if set_default_billing:
                            billing_address.default = True
                            billing_address.save()

                    else:
                        messages.info(self.request, "Please fill in the required billing address fields")

                payment_option = form.cleaned_data.get('payment_option')
                if payment_option == 'S':
                    return redirect('home:payment', payment_option='stripe')
                elif payment_option == 'P':
                    return redirect('home:payment', payment_option='paypal')
                else:
                    messages.warning(self.request, "Invalid payment option selected")
                    return redirect('home:checkout')

                # print(form.cleaned_data)
                # print('the form is valid')
                # return redirect('home:checkout')
            messages.warning(self.request, "Failed checkout")
            return redirect('home:checkout')
        except ObjectDoesNotExist:
            messages.warning(self.request, "You do not have active order")
            return redirect("home:order-summary")


class PaymentView(View):
    def get(self, *args, **kwargs):
        order = Order.objects.get(user=self.request.user, ordered=False)

        if order.billing_address:
            context = {
                'order': order,
                'DISPLAY_COUPON_FORM': False,
                # 'STRIPE_PUBLIC_KEY' : settings.STRIPE_PUBLIC_KEY
                'STRIPE_PUBLIC_KEY': 'pk_test_51HT8HGLDTNwpDpBQ59l0dDtge2bUJijJoxFGeAbIV2t7iWFYsndB3CEZ7jmSYYAKEnWe7Ej5ZPsiqWw71s4tM1LB00CiImzDj2'
            }
            print(self.request)
            userprofile = self.request.user.userprofile
            if userprofile.one_click_purchasing:
                # fetch the users card list
                cards = stripe.Customer.list_sources(
                    userprofile.stripe_customer_id,
                    limit=3,
                    object='card'
                )
                print(cards)
                card_list = cards['data']
                if len(card_list) > 0:
                    # update the context with the default card
                    context.update({
                        'card': card_list[0]
                    })
                return render(self.request, "payment.html", context)
            return render(self.request, "payment.html", context)
        else:
            messages.warning(self.request, "You have not added a billing address")
            return redirect("home:checkout")

    def post(self, *args, **kwargs):
        print('I am in POST')
        order = Order.objects.get(user=self.request.user, ordered=False)
        form = PaymentForm(self.request.POST or None)
        userprofile = UserProfile.objects.get(user=self.request.user)
        # try:
        #     user_cards = UserCards.objects.get(user=self.request.user)
        # except user_cards.DoesNotExist:
        #     user_cards = None

        if form.is_valid():
            token = form.cleaned_data.get('stripeToken')
            save = form.cleaned_data.get('save')
            use_default = form.cleaned_data.get('use_default')

            # 0. enter card dont do payment
            #
            # 1. enter card save --> success or failure
            # 2. enter card dont save --> success or failure
            #
            # 3. enter new card save
            # 4. enter new card dont save
            #
            # 5. select and use saved old default card
            # 6. update old saved card
            # 6. delete old saved card

            # get all the customer
            # customers = stripe.Customer.list(limit=10)
            # print(customers)
            # cus_I63r3UC9EoX7a5
            # deleet customer
            # stripe.Customer.delete("cus_I68QcSgg0dzegO")
            # List all the cards

            # Cardslist = stripe.Customer.list_sources(
            #     "cus_I63r3UC9EoX7a5",
            #     object="card",
            #     limit=3,
            # )
            # print(Cardslist)

            # get source

            if userprofile.stripe_customer_id != '' and userprofile.stripe_customer_id is not None:
                customer = stripe.Customer.retrieve(userprofile.stripe_customer_id)
                # TODO: Verify all the Stripe Aavailable billing address details are same
            else:
                print(token)
                print('Creating Strip customer Strip ')
                # customer = stripe.PaymentIntent.create(
                #     description='Testing Prabha1',
                #     shipping={
                #         'name': 'Prabha1_Shipper1',
                #         'address': {
                #             'line1': '510 Townsend St',
                #             'postal_code': '98140',
                #             'city': 'San Francisco',
                #             'state': 'CA',
                #             'country': 'US',
                #         },
                #     },
                #     amount=700,
                #     currency='inr',
                #     payment_method_types=['card'],
                # )
                customer = stripe.Customer.create(
                    email=self.request.user.email,
                    name='Prabha2_shipper2',
                    description='createCustDesc2',
                    address={
                        'line1': '510 Townsend St',
                        'line2': '',
                        'city': 'San Francisco',
                        'state': 'CA',
                        'country': 'US',
                        'postal_code': '98140'
                    }
                )
                userprofile.stripe_customer_id = customer['id']
                userprofile.save()

                # stripe customer ID generated and saved in Customer Profile
                print('customer')
                print(customer)
                print(customer.id)

                # default_card_source = 'src_1HVt1gLDTNwpDpBQYMGOUHbF'
                default_card_source = 'src_1HW0dhLDTNwpDpBQlmG0I5ZC'

            # cards_list = stripe.Customer.list_sources(
            #     customer.id,
            #     object="card",
            #     limit=3,
            # )
            # print('cards_list')
            # print(cards_list)
            # card_1HWF25LDTNwpDpBQWuR6NesF

            # Retrive source
            # retrieved_source = stripe.Source.retrieve(
            #     user_cards.source_id
            # )
            # print('retrieved_source')
            # print(retrieved_source)
            # print(retrieved_source.id)

            # Add Card for customer and source
            # card_id = stripe.Customer.create_source(
            #     customer.id,
            #     source=user_cards.source_id
            # )
            # print('card_id')
            # print(card_id)
            # print(card_id.id)

            user_card = UserCards()
            # try:
            #     user_cards = UserCards.objects.get(user=self.request.user)
            # except user_cards.DoesNotExist:
            #     user_cards = None

            if save:
                # Create a card for a customer
                card_id = stripe.Customer.create_source(
                    customer.id,
                    source=token,
                )
                # source = card_source.id,
                print('card_id')
                print(card_id)
                print(card_id.id)

                # ach_credit_transfer, ach_debit, alipay, bancontact, card, card_present, eps, giropay, ideal, multibanco, klarna, p24, sepa_debit, sofort, three_d_secure, or wechat
                # card_source = stripe.Source.create(
                #     type='card',
                #     currency='inr',
                #     owner={
                #         'email': self.request.user.email
                #     },
                #     token=token
                # )
                # # ,
                # # token = token
                # print('card_source')
                # print(card_source)
                # print(card_source.id)

                user_card.user = self.request.user
                user_card.default_source_id = True
                user_card.card_id = card_id.id
                # user_card.source_id = card_source.id
                user_card.save()

                userprofile.one_click_purchasing = True
                userprofile.save()
            else:
                pass
                # card_id = stripe.Customer.create_source(
                #     customer.id,
                #     source=default_card_source
                # )
                # user_card.user = self.request.user
                # user_card.default_source_id = False
                # user_card.card_id = card_id.id
                # user_card.source_id = default_card_source
                # user_card.save()

            # amount = 800
            amount = int(order.get_total() * 100)

            try:
                # TODO: WORKING CUSTOMER
                # cus_I63r3UC9EoX7a5
                # src_1HWF2cLDTNwpDpBQEplRtrdS
                # card_1HWF25LDTNwpDpBQWuR6NesF

                charge = stripe.Charge.create(
                    amount=amount,  # cents
                    currency="inr",
                    customer=userprofile.stripe_customer_id,
                    description="second test charge",
                )
                # TODO: If source is available charge the source
                # source=user_card.source_id
                # source = "src_1HWF2cLDTNwpDpBQEplRtrdS"
                print(charge)

                # create the payment
                payment = Payment()
                payment.stripe_charge_id = charge['id']
                payment.user = self.request.user
                payment.amount = order.get_total()
                payment.save()

                # assign the payment to the order
                order_items = order.items.all()
                order_items.update(ordered=True)
                for item in order_items:
                    item.save()

                order.ordered = True
                order.payment = payment
                order.ref_code = create_ref_code()
                order.save()

                messages.success(self.request, "Your order was successful!")
                return redirect("/")

            except stripe.error.CardError as e:
                body = e.json_body
                err = body.get('error', {})
                traceback.print_exc()
                messages.warning(self.request, f"{err.get('message')}")
                return redirect("/")

            except stripe.error.RateLimitError as e:
                # Too many requests made to the API too quickly
                traceback.print_exc()
                messages.warning(self.request, "Rate limit error")
                return redirect("/")

            except stripe.error.InvalidRequestError as e:
                # Invalid parameters were supplied to Stripe's API
                print(e)
                traceback.print_exc()
                messages.warning(self.request, "Invalid parameters")
                return redirect("/")

            except stripe.error.AuthenticationError as e:
                # Authentication with Stripe's API failed
                # (maybe you changed API keys recently)
                traceback.print_exc()
                messages.warning(self.request, "Not authenticated")
                return redirect("/")

            except stripe.error.APIConnectionError as e:
                # Network communication with Stripe failed
                traceback.print_exc()
                messages.warning(self.request, "Network error")
                return redirect("/")

            except stripe.error.StripeError as e:
                # Display a very generic error to the user, and maybe send
                # yourself an email
                print(e)
                traceback.print_exc()
                messages.warning(
                    self.request, "Something went wrong. You were not charged. Please try again.")
                return redirect("/")

            except Exception as e:
                # send an email to ourselves
                print(e)
                traceback.print_exc()
                messages.warning(self.request, "A serious error occurred. We have been notifed.")
                return redirect("/")
        messages.warning(self.request, "Invalid data received")
        return redirect("/payment/stripe/")

    # def post(self, *args, **kwargs):
    #     print('I am in ')
    #     order = Order.objects.get(user=self.request.user, ordered=False)
    #     form = PaymentForm(self.request.POST or None)
    #     userprofile = UserProfile.objects.get(user=self.request.user)
    #     if form.is_valid():
    #         token = form.cleaned_data.get('stripeToken')
    #         save = form.cleaned_data.get('save')
    #         use_default = form.cleaned_data.get('use_default')
    #
    #         if save:
    #             if userprofile.stripe_customer_id != '' and userprofile.stripe_customer_id is not None:
    #                 customer = stripe.Customer.retrieve(userprofile.stripe_customer_id)
    #                 customer.sources.create(source=token)
    #             else:
    #                 print('I am in  customer else Token')
    #                 print(token)
    #
    #                 # print('I am in Customer')
    #                 # customer = stripe.Customer.create(
    #                 #     email=self.request.user.email,
    #                 #     name='Prabha2',
    #                 #     description='Money to mani2',
    #                 #     address={
    #                 #         'line1': '510 Townsend St',
    #                 #         'line2': '',
    #                 #         'city': 'San Francisco',
    #                 #         'state': 'CA',
    #                 #         'country': 'US',
    #                 #         'postal_code': '98140'
    #                 #     }
    #                 # )
    #                 # print(customer)
    #                 # print('I am in Customer id ')
    #                 # print(customer.id)
    #
    #                 # customer = stripe.PaymentIntent.create(
    #                 #     description='Software development services',
    #                 #     shipping={
    #                 #         'name': 'Jenny Rosen',
    #                 #         'address': {
    #                 #             'line1': '510 Townsend St',
    #                 #             'postal_code': '98140',
    #                 #             'city': 'San Francisco',
    #                 #             'state': 'CA',
    #                 #             'country': 'US',
    #                 #         },
    #                 #     },
    #                 #     amount=1099,
    #                 #     currency='usd',
    #                 #     payment_method_types=['card'],
    #                 # )
    #
    #                 # print('I am in Source')
    #                 # src = stripe.Source.create(
    #                 #     type='ach_credit_transfer',
    #                 #     currency='usd',
    #                 #     owner={
    #                 #         'email': 'prabhakaranautomatin@gmail.com'
    #                 #     }
    #                 # )
    #                 # print(src)
    #                 # print('I am in Source id')
    #                 # print(src.id)
    #                 # src_1HVt1gLDTNwpDpBQYMGOUHbF
    #
    #                 # source = stripe.Customer.create_source(
    #                 #     customer.id,
    #                 #     source=src.id
    #                 # )
    #                 # print('I am in add customer in source')
    #                 # print(source)
    #                 # print(source.id)
    #                 # print('all over') # 'src_1HVt1gLDTNwpDpBQYMGOUHbF'
    #
    #                 # src = 'src_1HVt1gLDTNwpDpBQYMGOUHbF'
    #                 # source = stripe.Customer.create_source(
    #                 #     customer.id,
    #                 #     source=src
    #                 # )
    #
    #                 # customer.sources.create(source=token)
    #                 userprofile.stripe_customer_id = customer['id']
    #                 userprofile.one_click_purchasing = True
    #                 userprofile.save()
    #         amount = int(order.get_total() * 100)
    #         try:
    #             if use_default or save:
    #                 # charge the customer because we cannot charge the token more than once
    #                 charge = stripe.Charge.create(
    #                     amount=amount,  # cents
    #                     currency="usd",
    #                     customer=userprofile.stripe_customer_id,
    #                     description="First test charge"
    #                 )
    #                 print('I am in With customer')
    #                 # charge = stripe.InvoiceItem.create(
    #                 #     customer=userprofile.stripe_customer_id,
    #                 #     amount=amount,
    #                 #     currency='usd',
    #                 #     description='One-time setup fee',
    #                 # )
    #             else:
    #                 # charge once off on the token
    #                 charge = stripe.Charge.create(
    #                     amount=amount,  # cents
    #                     currency="usd",
    #                     source=token,
    #                     description="First test charge"
    #                 )
    #                 # print('I am in With out customer')
    #                 # charge = stripe.InvoiceItem.create(
    #                 #     customer='cus_Ej0c314UoUXBgX',
    #                 #     amount=2500,
    #                 #     currency='usd',
    #                 #     description='One-time setup fee',
    #                 # )
    #
    #             # create the payment
    #             payment = Payment()
    #             payment.stripe_charge_id = charge['id']
    #             payment.user = self.request.user
    #             payment.amount = order.get_total()
    #             payment.save()
    #
    #             # assign the payment to the order
    #             order_items = order.items.all()
    #             order_items.update(ordered=True)
    #             for item in order_items:
    #                 item.save()
    #
    #             order.ordered = True
    #             order.payment = payment
    #             order.ref_code = create_ref_code()
    #             order.save()
    #
    #             messages.success(self.request, "Your order was successful!")
    #             return redirect("/")
    #
    #         except stripe.error.CardError as e:
    #             body = e.json_body
    #             err = body.get('error', {})
    #             messages.warning(self.request, f"{err.get('message')}")
    #             return redirect("/")
    #
    #         except stripe.error.RateLimitError as e:
    #             # Too many requests made to the API too quickly
    #             messages.warning(self.request, "Rate limit error")
    #             return redirect("/")
    #
    #         except stripe.error.InvalidRequestError as e:
    #             # Invalid parameters were supplied to Stripe's API
    #             print(e)
    #             messages.warning(self.request, "Invalid parameters")
    #             return redirect("/")
    #
    #         except stripe.error.AuthenticationError as e:
    #             # Authentication with Stripe's API failed
    #             # (maybe you changed API keys recently)
    #             messages.warning(self.request, "Not authenticated")
    #             return redirect("/")
    #
    #         except stripe.error.APIConnectionError as e:
    #             # Network communication with Stripe failed
    #             messages.warning(self.request, "Network error")
    #             return redirect("/")
    #
    #         except stripe.error.StripeError as e:
    #             # Display a very generic error to the user, and maybe send
    #             # yourself an email
    #             messages.warning(
    #                 self.request, "Something went wrong. You were not charged. Please try again.")
    #             return redirect("/")
    #
    #         except Exception as e:
    #             # send an email to ourselves
    #             messages.warning(self.request, "A serious error occurred. We have been notifed.")
    #             return redirect("/")
    #     messages.warning(self.request, "Invalid data received")
    #     return redirect("/payment/stripe/")


class HomeView(ListView):
    model = Item
    paginate_by = 10
    template_name = "home.html"


class ItemDetailView(DetailView):
    model = Item
    template_name = "product.html"


class OrderSummaryView(LoginRequiredMixin, View):
    def get(self, *args, **kwargs):
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            context = {
                'object': order
            }
            return render(self.request, 'order_summary.html', context)
        except ObjectDoesNotExist:
            messages.warning(self.request, "You do not have active order")
            return redirect("/")


@login_required
def add_to_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_item, created = OrderItem.objects.get_or_create(
        item=item,
        user=request.user,
        ordered= False
    )
    order_qs = Order.objects.filter(user = request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item.quantity += 1
            order_item.save()
            messages.info(request, "This item quantity was updated in your cart.")
            return redirect("home:product", slug=slug)
        else:
            order.items.add(order_item)
            messages.info(request, "This item was added to your cart.")
            return redirect("home:product", slug=slug)
    else:
        ordered_data = timezone.now()
        order = Order.objects.create(user = request.user, ordered_data = ordered_data)
        order.items.add(order_item)
        messages.info(request, "This item was added to your cart.")
        return redirect("home:product", slug=slug)


@login_required
def add_single_item_to_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_item, created = OrderItem.objects.get_or_create(
        item=item,
        user=request.user,
        ordered= False
    )
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item.quantity += 1
            order_item.save()
            messages.info(request, "This item quantity was updated in your cart.")
            return redirect("home:order-summary")
        else:
            order.items.add(order_item)
            messages.info(request, "This item was added to your cart.")
            return redirect("home:order-summary")
    else:
        ordered_data = timezone.now()
        order = Order.objects.create(user=request.user, ordered_data=ordered_data)
        order.items.add(order_item)
        messages.info(request, "This item was added to your cart.")
        return redirect("home:order-summary")


@login_required
def remove_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(
                item=item,
                user=request.user,
                ordered=False
            )[0]
            order.items.remove(order_item)
            order_item.delete()
            messages.info(request, "This item was removed from your cart.")
            return redirect("home:product", slug=slug)
        else:
            messages.info(request, "This item was not in your cart.")
            return redirect("home:product", slug=slug)
    else:
        messages.info(request, "you do not have an active order")
        return redirect("home:product", slug=slug)


@login_required
def remove_single_item_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(
                item=item,
                user=request.user,
                ordered=False
            )[0]
            if order_item.quantity > 1:
                order_item.quantity -= 1
                order_item.save()
                messages.info(request, "This item quantity was reduced from your cart.")
            else:
                order.items.remove(order_item)
                order_item.delete()
                messages.info(request, "This item was removed from your cart.")
            return redirect("home:order-summary")
        else:
            messages.info(request, "This item was not in your cart.")
            return redirect("home:product", slug=slug)
    else:
        messages.info(request, "you do not have an active order")
        return redirect("home:product", slug=slug)


@login_required
def remove_from_cart_summary(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(
                item=item,
                user=request.user,
                ordered=False
            )[0]
            order.items.remove(order_item)
            order_item.delete()
            messages.info(request, "This item was removed from your cart.")
            return redirect("home:order-summary")
        else:
            messages.info(request, "This item was not in your cart.")
            return redirect("home:product", slug=slug)
    else:
        messages.info(request, "you do not have an active order")
        return redirect("home:product", slug=slug)


def get_coupon(request, code):
    try:
        coupon = Coupon.objects.get(code=code)
        return coupon
    except ObjectDoesNotExist:
        messages.info(request, "This coupon does not exist")
        return redirect("home:checkout")


class AddCouponView(View):
    def post(self, *args, **kwargs):
        form = CouponForm(self.request.POST or None)
        if form.is_valid():
            try:
                code = form.cleaned_data.get('code')
                order = Order.objects.get(user=self.request.user, ordered=False)
                order.coupon = get_coupon(self.request, code)
                order.save()
                messages.success(self.request, "Successfully added coupon")
                return redirect("home:checkout")
            except ObjectDoesNotExist:
                messages.info(self.request, "You do not have an active order")
                return redirect("home:checkout")


class RemoveCouponView(View):
    def post(self, *args, **kwargs):
        form = CouponForm(self.request.POST or None)
        if form.is_valid():
            try:
                code = form.cleaned_data.get('code')
                order = Order.objects.get(user=self.request.user, ordered=False)
                order.coupon = get_coupon(self.request, code)
                order.save()
                messages.success(self.request, "Successfully added coupon")
                return redirect("home:checkout")
            except ObjectDoesNotExist:
                messages.info(self.request, "You do not have an active order")
                return redirect("home:checkout")


class RequestRefundView(View):
    def get(self, *args, **kwargs):
        form = RefundForm()
        context = {
            'form': form
        }
        return render(self.request, "request_refund.html", context)

    def post(self, *args, **kwargs):
        form = RefundForm(self.request.POST)
        if form.is_valid():
            ref_code = form.cleaned_data.get('ref_code')
            message = form.cleaned_data.get('message')
            email = form.cleaned_data.get('email')
            # edit the order
            try:
                order = Order.objects.get(ref_code=ref_code)
                order.refund_requested = True
                order.save()

                # store the refund
                refund = Refund()
                refund.order = order
                refund.reason = message
                refund.email = email
                refund.save()

                messages.info(self.request, "Your request was received.")
                return redirect("home:request-refund")

            except ObjectDoesNotExist:
                messages.info(self.request, "This order does not exist.")
                return redirect("home:request-refund")
