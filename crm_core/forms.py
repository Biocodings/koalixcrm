# coding=utf-8

from datetimewidget.widgets import DateWidget
from django import forms
from crispy_forms.helper import FormHelper
from django.forms import inlineformset_factory
from models import PurchaseOrder, Quote, Invoice, CustomerCartItem, ProductUnit, ProductTax
from cartridge.shop.models import Cart, Product
from ajax_select import make_ajax_field


class PurchaseOrderForm(forms.ModelForm):

    class Meta:
        model = PurchaseOrder
        fields = ['currency', 'billing_detail_external_reference', 'description']

    def __init__(self, *args, **kwargs):
        super(PurchaseOrderForm, self).__init__(*args, **kwargs)
        self.fields['description'].widget = forms.TextInput()
        self.helper = FormHelper()
        self.helper.form_tag = False


class QuoteForm(forms.ModelForm):

    class Meta:
        model = Quote
        fields = ['currency', 'external_reference', 'description']

    def __init__(self, *args, **kwargs):
        super(QuoteForm, self).__init__(*args, **kwargs)
        self.fields['description'].widget = forms.TextInput()
        self.helper = FormHelper()
        self.helper.form_tag = False


class InvoiceForm(forms.ModelForm):

    class Meta:
        model = Invoice
        fields = ['currency', 'payableuntil', 'external_reference', 'description']

    def __init__(self, *args, **kwargs):
        super(InvoiceForm, self).__init__(*args, **kwargs)
        self.fields['description'].widget = forms.TextInput()
        self.fields['payableuntil'] = forms.DateField(widget=DateWidget(bootstrap_version=3, usel10n=True))
        self.helper = FormHelper()
        self.helper.form_tag = False


class ProductForm(forms.ModelForm):

    class Meta:
        model = Product
        exclude = ('status', 'meta_title', )


class ProductUnitForm(forms.ModelForm):

    class Meta:
        model = ProductUnit
        exclude = ('product', )


class ProductTaxForm(forms.ModelForm):

    class Meta:
        model = ProductTax
        exclude = ('product', )


PositionFormSet = inlineformset_factory(
    Cart, CustomerCartItem,
    fields=('quantity', 'description', 'unit_price', 'total_price', 'product'),
    widgets={
        'total_price': forms.TextInput(attrs={'readonly': True}),
        'unit_price': forms.TextInput(attrs={'readonly': True})
    },
    extra=5, can_delete=True)
