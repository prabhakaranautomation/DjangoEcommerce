from django import forms
from django_countries.fields import CountryField
from django_countries.widgets import CountrySelectWidget

PAYMENT_CHOICE = (
    ('S', 'Stripe'),
    ('P', 'PayPal')
)


class CheckoutForm(forms.Form):
    # street_address = forms.CharField(widget=forms.TextInput(attrs={
    #     'placeholder': '1234 Main street'
    # }))
    # apartment_address = forms.CharField(required=False, widget=forms.TextInput(attrs={
    #     'placeholder': 'Apartment or suite'
    # }))
    # country = CountryField(blank_label='(select country)').formfield(
    #     widget=CountrySelectWidget(attrs={
    #         'class': 'custom-select d-block w-100',
    #         'id': 'zip'
    #     }))
    # zip = forms.CharField(widget=forms.TextInput(attrs={
    #         'class': 'form-control'
    # }))
    # # same_billing_address = forms.BooleanField(widget=forms.BooleanField(required=False))
    # same_shipping_address = forms.BooleanField(widget=forms.BooleanField(required=False))
    # save_info = forms.BooleanField(widget=forms.BooleanField(required=False))
    # payment_option = forms.ChoiceField(widget=forms.RadioSelect(), choices=PAYMENT_CHOICE)

    shipping_address = forms.CharField(required=False)
    shipping_address2 = forms.CharField(required=False)
    shipping_country = CountryField(blank_label='(select country)').formfield(
        required=False,
        widget=CountrySelectWidget(attrs={
            'class': 'custom-select d-block w-100'
        }))
    shipping_zip = forms.CharField(required=False)

    billing_address = forms.CharField(required=False)
    billing_address2 = forms.CharField(required=False)
    billing_country = CountryField(blank_label='(select country)').formfield(
        required=False,
        widget=CountrySelectWidget(attrs={
            'class': 'custom-select d-block w-100'
        }))
    billing_zip = forms.CharField(required=False)

    same_shipping_address = forms.BooleanField(required=False)
    set_default_shipping = forms.BooleanField(required=False)
    use_default_shipping = forms.BooleanField(required=False)
    set_default_billing = forms.BooleanField(required=False)
    use_default_billing = forms.BooleanField(required=False)
    payment_option = forms.ChoiceField(widget=forms.RadioSelect, choices=PAYMENT_CHOICE)


class CouponForm(forms.Form):
    code = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'Promo code',
        'aria-label': 'Recipient\'s username',
        'aria-describedby': 'basic-addon2'
    }))


class RefundForm(forms.Form):
    ref_code = forms.CharField()
    message = forms.CharField(widget=forms.Textarea(attrs={
        'rows': '5'
    }))
    email = forms.EmailField()


class PaymentForm(forms.Form):
    stripeToken = forms.CharField(required=False)
    save = forms.BooleanField(required=False)
    use_default = forms.BooleanField(required=False)

