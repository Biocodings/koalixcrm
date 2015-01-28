# -*- coding: utf-8 -*-
import StringIO
from braces.views import PermissionRequiredMixin, LoginRequiredMixin
from django.utils.translation import ugettext_lazy as _
from django.conf import settings
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView, DeleteView, DetailView
from django.http import HttpResponse, HttpResponseRedirect
from django.template import RequestContext, loader
from extra_views import UpdateWithInlinesView, InlineFormSet, NamedFormsetsMixin, CreateWithInlinesView
from crm_core.const.states import InvoiceStatesEnum
from crm_core.forms import PurchaseOrderPositionInlineForm, PurchaseOrderForm, SalesContractPositionInlineForm, \
    QuoteForm, InvoiceForm
from crm_core.impex import CustomerResource, SupplierResource, CustomerGroupResource, InvoiceResource, \
    ProductResource, ContractResource, CustomerBillingCycleResource, PurchaseOrderResource, QuoteResource, \
    TaxRateResource, UnitResource
from crm_core.models import Customer, Invoice, Supplier, Unit, TaxRate, Contract, Product, CustomerBillingCycle, \
    PurchaseOrder, CustomerGroup, Quote, PostalAddress, PhoneAddress, EmailAddress, UserExtension, \
    PurchaseOrderPosition, SalesContractPosition
from django.shortcuts import render_to_response, redirect, render
from django.contrib.auth import authenticate, login, logout


# ######################
# ##   Helper Views   ##
# ######################


def login_user(request):
    logout(request)
    username = password = ''
    if request.POST:
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(username=username, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                return redirect(reverse_lazy('dashboard'))
    return render_to_response('registration/login.html', context_instance=RequestContext(request))


def show_dashboard(request):
    contractcount = Contract.objects.all().count()
    invoicecount = Invoice.objects.all().count()
    customercount = Customer.objects.all().count()
    suppliercount = Supplier.objects.all().count()
    productcount = Product.objects.all().count()
    opencontracts = []
    for invoice in Invoice.objects.all():
        if invoice.state != InvoiceStatesEnum.Payed or invoice.state != InvoiceStatesEnum.Deleted \
                and invoice not in opencontracts:
            opencontracts.append(invoice.contract)
    for contract in Contract.objects.all():
        if contract not in opencontracts:
            opencontracts.append(contract)
    template = loader.get_template('dashboard.html')
    context = RequestContext(request, {
        'contractcount': contractcount,
        'invoicecount': invoicecount,
        'customercount': customercount,
        'suppliercount': suppliercount,
        'productcount': productcount,
        'opencontracts': opencontracts,
    })
    return HttpResponse(template.render(context))


# ##############################
# ##   CRM Functional Views   ##
# ##############################


def create_contract_from_customer(request, customer_pk):
    customer = Customer.objects.get(pk=customer_pk)
    contract = customer.create_contract(request)
    if not customer.default_currency:
        return redirect('contract_edit', pk=contract.pk)
    return redirect('contract_detail', pk=contract.pk)


def create_quote_from_customer(request, customer_pk):
    customer = Customer.objects.get(pk=customer_pk)
    quote = customer.create_quote(request)
    if not customer.default_currency:
        return redirect('contract_edit', pk=quote.contract.pk)
    return redirect('quote_edit', pk=quote.pk)


def create_purchaseorder_from_customer(request, customer_pk):
    customer = Customer.objects.get(pk=customer_pk)
    purchase_order = customer.create_purchase_order(request)
    if not customer.default_currency:
        return redirect('contract_edit', pk=purchase_order.contract.pk)
    return redirect('purchaseorder_edit', pk=purchase_order.pk)


def create_quote_from_contract(request, contract_pk):
    contract = Contract.objects.get(pk=contract_pk)
    quote = contract.create_quote()
    return redirect('quote_edit', pk=quote.pk)


def create_invoice_from_contract(request, contract_pk):
    contract = Contract.objects.get(pk=contract_pk)
    invoice = contract.create_invoice()
    return redirect('invoice_edit', pk=invoice.pk)


def create_purchaseorder_from_contract(request, contract_pk):
    contract = Contract.objects.get(pk=contract_pk)
    purchase_order = contract.create_purchase_order()
    return redirect('purchaseorder_edit', pk=purchase_order.pk)


def create_invoice_from_quote(request, quote_pk):
    quote = Quote.objects.get(pk=quote_pk)
    invoice = quote.create_invoice()
    return redirect('invoice_edit', pk=invoice.pk)


def create_purchaseorder_from_quote(request, quote_pk):
    quote = Quote.objects.get(pk=quote_pk)
    purchase_order = quote.create_purchase_order()
    return redirect('purchaseorder_edit', pk=purchase_order.pk)


# ############################
# ##   PDF Creation Views   ##
# ############################


def create_pdf_from_quote(request, quote_pk):
    quote = Quote.objects.get(pk=quote_pk)
    html_string = StringIO.StringIO()
    print render(request, 'pdf_templates/quote.html', {'quote': quote}).content
    html_string.write(render(request, 'pdf_templates/quote.html', {'quote': quote}).content)
    quote.create_pdf(html_string)
    return redirect('quote_list')


def create_pdf_from_purchaseorder(request, purchaseorder_pk):
    purchase_order = PurchaseOrder.objects.get(pk=purchaseorder_pk)
    html_string = StringIO.StringIO()
    html_string.write(render(request, 'pdf_templates/purchaseorder.html', {'purchaseorder': purchase_order}).content)
    purchase_order.create_pdf(html_string)
    return redirect('purchaseorder_list')


def create_pdf_from_invoice(request, invoice_pk):
    invoice = Invoice.objects.get(pk=invoice_pk)
    html_string = StringIO.StringIO()
    html_string.write(render(request, 'pdf_templates/invoice.html', {'invoice': invoice}).content)
    invoice.create_pdf(html_string)
    return redirect('invoice_list')


# #############################
# ##   Import Export Views   ##
# #############################


def _get_export_response(dataset, name, format=None):
    if format == 'xls':
        response = HttpResponse(content_type='text/vnd.ms-excel')
        response['Content-Disposition'] = 'attachment; filename="%s.xls"' % name
        response.content = dataset.xls
    elif format == 'xlsx':
        response = HttpResponse(content_type='text/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="%s.xlsx"' % name
        response.content = dataset.xlsx
    elif format == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="%s.csv"' % name
        response.content = dataset.csv
    else:
        response = HttpResponse(content_type='text/json')
        response['Content-Disposition'] = 'attachment; filename="%s.json"' % name
        response.content = dataset.json
    return response


def export_customers(request, format='xls'):
    dataset = CustomerResource().export()
    return _get_export_response(dataset, 'customers', format)


def import_customers(request):
    pass


def export_suppliers(request, format='xls'):
    dataset = SupplierResource().export()
    return _get_export_response(dataset, 'suppliers', format)


def export_products(request, format='xls'):
    dataset = ProductResource().export()
    return _get_export_response(dataset, 'products', format)


def export_contracts(request, format='xls'):
    dataset = ContractResource().export()
    return _get_export_response(dataset, 'contracts', format)


def export_quotes(request, format='xls'):
    dataset = QuoteResource().export()
    return _get_export_response(dataset, 'quotes', format)


def export_invoices(request, format='xls'):
    dataset = InvoiceResource().export()
    return _get_export_response(dataset, 'invoices', format)


def export_purchaseorders(request, format='xls'):
    dataset = PurchaseOrderResource().export()
    return _get_export_response(dataset, 'purchaseorders', format)


def export_taxrates(request, format='xls'):
    dataset = TaxRateResource().export()
    return _get_export_response(dataset, 'taxrates', format)


def export_units(request, format='xls'):
    dataset = UnitResource().export()
    return _get_export_response(dataset, 'units', format)


def export_billingcycles(request, format='xls'):
    dataset = CustomerBillingCycleResource().export()
    return _get_export_response(dataset, 'billingcycles', format)


def export_customergroups(request, format='xls'):
    dataset = CustomerGroupResource().export()
    return _get_export_response(dataset, 'customergroups', format)


# ###########################
# ##   Class Based Views   ##
# ###########################


class PurchaseOrderPositionInline(InlineFormSet):
        model = PurchaseOrderPosition
        extra = 5
        can_delete = True
        form_class = PurchaseOrderPositionInlineForm
        prefix = 'purchaseorderposition'


class SalesContractPositionInline(InlineFormSet):
        model = SalesContractPosition
        extra = 5
        can_delete = True
        form_class = SalesContractPositionInlineForm
        prefix = 'salescontractposition'


class PostalAddressInline(LoginRequiredMixin, PermissionRequiredMixin, InlineFormSet):
    model = PostalAddress
    permission_required = 'crm_core.view_postaladdress'
    raise_exception = False
    extra = 1
    can_delete = False
    fields = ['addressline1', 'addressline2', 'zipcode', 'city', 'state', 'country', 'purpose']


class PhoneAddressInline(LoginRequiredMixin, PermissionRequiredMixin, InlineFormSet):
    model = PhoneAddress
    permission_required = 'crm_core.view_phoneaddress'
    raise_exception = False
    extra = 1
    max_num = 4
    can_delete = False
    fields = ['phone', 'purpose']


class EmailAddressInline(LoginRequiredMixin, PermissionRequiredMixin, InlineFormSet):
    model = EmailAddress
    permission_required = 'crm_core.view_emailaddress'
    raise_exception = False
    extra = 1
    max_num = 2
    can_delete = False
    fields = ['email', 'purpose']


class UserExtensionInline(InlineFormSet):
    model = UserExtension
    extra = 1
    max_num = 1
    can_delete = False


class UpdateUserProfile(LoginRequiredMixin, NamedFormsetsMixin, UpdateWithInlinesView):
    model = User
    inlines = [UserExtensionInline, ]
    inlines_names = ['userprofile_formset']
    fields = ['first_name', 'last_name', 'email', 'is_superuser', 'is_staff', 'is_active', 'groups']
    success_url = reverse_lazy('home')


class ListCustomers(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Customer
    permission_required = 'crm_core.view_customer'
    login_url = settings.LOGIN_URL
    fields = ['name', 'firstname', 'billingcycle', 'ismemberof']


class ViewCustomer(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Customer
    permission_required = 'crm_core.view_customer'
    login_url = settings.LOGIN_URL


class CreateCustomer(LoginRequiredMixin, PermissionRequiredMixin, NamedFormsetsMixin, CreateWithInlinesView):
    model = Customer
    permission_required = 'crm_core.add_customer'
    login_url = settings.LOGIN_URL
    fields = ['prefix', 'name', 'firstname', 'default_currency', 'billingcycle', 'ismemberof']
    inlines = [PostalAddressInline, PhoneAddressInline, EmailAddressInline]
    inlines_names = ['postaladdress_formset', 'phoneaddress_formset', 'emailaddress_formset']
    success_url = reverse_lazy('customer_list')


class EditCustomer(LoginRequiredMixin, PermissionRequiredMixin, NamedFormsetsMixin, UpdateWithInlinesView):
    model = Customer
    permission_required = 'crm_core.change_customer'
    login_url = settings.LOGIN_URL
    fields = ['prefix', 'name', 'firstname', 'default_currency', 'billingcycle', 'ismemberof']
    inlines = [PostalAddressInline, PhoneAddressInline, EmailAddressInline]
    inlines_names = ['postaladdress_formset', 'phoneaddress_formset', 'emailaddress_formset']
    success_url = reverse_lazy('customer_list')


class DeleteCustomer(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Customer
    permission_required = 'crm_core.delete_customer'
    login_url = settings.LOGIN_URL
    success_url = reverse_lazy('customer_list')


class ListSuppliers(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Supplier
    permission_required = 'crm_core.view_supplier'
    login_url = settings.LOGIN_URL
    fields = ['name', 'direct_shipment_to_customers']


class ViewSupplier(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Supplier
    permission_required = 'crm_core.view_supplier'
    login_url = settings.LOGIN_URL


class CreateSupplier(LoginRequiredMixin, PermissionRequiredMixin, NamedFormsetsMixin, CreateWithInlinesView):
    model = Supplier
    permission_required = 'crm_core.add_supplier'
    login_url = settings.LOGIN_URL
    fields = ['prefix', 'name', 'default_currency', 'direct_shipment_to_customers']
    inlines = [PostalAddressInline, PhoneAddressInline, EmailAddressInline]
    inlines_names = ['postaladdress_formset', 'phoneaddress_formset', 'emailaddress_formset']
    success_url = reverse_lazy('supplier_list')


class EditSupplier(LoginRequiredMixin, PermissionRequiredMixin, NamedFormsetsMixin, UpdateWithInlinesView):
    model = Supplier
    permission_required = 'crm_core.change_supplier'
    login_url = settings.LOGIN_URL
    fields = ['prefix', 'name', 'default_currency', 'direct_shipment_to_customers']
    inlines = [PostalAddressInline, PhoneAddressInline, EmailAddressInline]
    inlines_names = ['postaladdress_formset', 'phoneaddress_formset', 'emailaddress_formset']
    success_url = reverse_lazy('supplier_list')


class DeleteSupplier(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Supplier
    permission_required = 'crm_core.delete_supplier'
    login_url = settings.LOGIN_URL
    success_url = reverse_lazy('supplier_list')


class ListTaxes(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = TaxRate
    permission_required = 'crm_core.view_tax'
    login_url = settings.LOGIN_URL


class CreateTax(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = TaxRate
    permission_required = 'crm_core.add_tax'
    login_url = settings.LOGIN_URL
    success_url = reverse_lazy('tax_list')


class EditTax(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = TaxRate
    permission_required = 'crm_core.change_tax'
    login_url = settings.LOGIN_URL
    success_url = reverse_lazy('tax_list')


class DeleteTax(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = TaxRate
    permission_required = 'crm_core.delete_tax'
    login_url = settings.LOGIN_URL
    success_url = reverse_lazy('tax_list')


class ListUnits(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Unit
    permission_required = 'crm_core.view_unit'
    login_url = settings.LOGIN_URL


class CreateUnit(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Unit
    permission_required = 'crm_core.add_unit'
    login_url = settings.LOGIN_URL
    success_url = reverse_lazy('unit_list')


class EditUnit(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Unit
    permission_required = 'crm_core.change_unit'
    login_url = settings.LOGIN_URL
    success_url = reverse_lazy('unit_list')


class DeleteUnit(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Unit
    permission_required = 'crm_core.delete_unit'
    login_url = settings.LOGIN_URL
    success_url = reverse_lazy('unit_list')


class ListProducts(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Product
    permission_required = 'crm_core.view_product'
    login_url = settings.LOGIN_URL
    fields = ['product_number', 'item_title', 'item_description', 'item_unit', 'item_tax', 'item_category']


class CreateProduct(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Product
    permission_required = 'crm_core.add_product'
    login_url = settings.LOGIN_URL
    fields = ['product_number', 'item_title', 'item_description', 'item_unit', 'item_tax', 'item_category']
    success_url = reverse_lazy('product_list')


class EditProduct(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Product
    permission_required = 'crm_core.change_product'
    login_url = settings.LOGIN_URL
    fields = ['product_number', 'item_title', 'item_description', 'item_unit', 'item_tax', 'item_category']
    success_url = reverse_lazy('product_list')


class ViewProduct(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Product
    permission_required = 'crm_core.view_product'
    login_url = settings.LOGIN_URL


class DeleteProduct(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Product
    permission_required = 'crm_core.delete_product'
    login_url = settings.LOGIN_URL
    success_url = reverse_lazy('product_list')


class ListBillingCycles(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = CustomerBillingCycle
    permission_required = 'crm_core.view_customerbillingcycles'
    login_url = settings.LOGIN_URL


class CreateBillingCycle(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = CustomerBillingCycle
    permission_required = 'crm_core.add_customerbillingcycle'
    login_url = settings.LOGIN_URL
    success_url = reverse_lazy('customerbillingcycle_list')


class EditBillingCycle(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = CustomerBillingCycle
    permission_required = 'crm_core.change_customerbillingcycle'
    login_url = settings.LOGIN_URL
    success_url = reverse_lazy('customerbillingcycle_list')


class DeleteBillingCycle(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = CustomerBillingCycle
    permission_required = 'crm_core.delete_customerbillingcycle'
    login_url = settings.LOGIN_URL
    success_url = reverse_lazy('customerbillingcycle_list')


class ListPurchaseOrders(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = PurchaseOrder
    permission_required = 'crm_core.view_purchaseorder'
    login_url = settings.LOGIN_URL
    fields = ['description', 'contract', 'supplier', 'state', 'currency', 'last_calculated_price',
              'last_pricing_date', ]


class EditPurchaseOrder(LoginRequiredMixin, PermissionRequiredMixin, UpdateWithInlinesView):
    model = PurchaseOrder
    form_class = PurchaseOrderForm
    inlines = [PurchaseOrderPositionInline]
    permission_required = 'crm_core.change_purchaseorder'
    login_url = settings.LOGIN_URL
    success_url = reverse_lazy('purchaseorder_list')


class DeletePurchaseOrder(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = PurchaseOrder
    permission_required = 'crm_core.delete_purchaseorder'
    login_url = settings.LOGIN_URL
    success_url = reverse_lazy('purchaseorder_list')


class ListCustomerGroups(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = CustomerGroup
    permission_required = 'crm_core.view_customergroup'
    login_url = settings.LOGIN_URL


class CreateCustomerGroup(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = CustomerGroup
    permission_required = 'crm_core.add_customergroup'
    login_url = settings.LOGIN_URL
    success_url = reverse_lazy('customergroup_list')


class EditCustomerGroup(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = CustomerGroup
    permission_required = 'crm_core.change_customergroup'
    login_url = settings.LOGIN_URL
    success_url = reverse_lazy('customergroup_list')


class DeleteCustomerGroup(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = CustomerGroup
    permission_required = 'crm_core.delete_customergroup'
    login_url = settings.LOGIN_URL
    success_url = reverse_lazy('customergroup_list')


class ListContracts(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Contract
    permission_required = 'crm_core.view_contract'
    login_url = settings.LOGIN_URL
    fields = ['description', 'default_customer', 'default_supplier', 'default_currency']


class ViewContract(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Contract
    permission_required = 'crm_core.view_contract'
    login_url = settings.LOGIN_URL


class CreateContract(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Contract
    permission_required = 'crm_core.add_contract'
    login_url = settings.LOGIN_URL
    fields = ['description', 'default_customer', 'default_supplier', 'default_currency']
    success_url = reverse_lazy('contract_list')


class EditContract(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Contract
    permission_required = 'crm_core.change_contract'
    login_url = settings.LOGIN_URL
    fields = ['description', 'default_customer', 'default_supplier', 'defaultcurrency']
    success_url = reverse_lazy('contract_list')


class DeleteContract(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Contract
    permission_required = 'crm_core.delete_contract'
    login_url = settings.LOGIN_URL
    success_url = reverse_lazy('contract_list')


class ListInvoice(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Invoice
    permission_required = 'crm_core.view_invoice'
    login_url = settings.LOGIN_URL
    fields = ['description', 'contract', 'customer', 'payableuntil', 'state', 'currency', 'last_calculated_price',
              'last_pricing_date']


class EditInvoice(LoginRequiredMixin, PermissionRequiredMixin, UpdateWithInlinesView):
    model = Invoice
    form_class = InvoiceForm
    inlines = [SalesContractPositionInline]
    permission_required = 'crm_core.change_invoice'
    login_url = settings.LOGIN_URL
    fields = ['description', 'contract', 'customer', 'payableuntil', 'state', 'currency']
    success_url = reverse_lazy('invoice_list')


class DeleteInvoice(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Invoice
    permission_required = 'crm_core.delete_invoice'
    login_url = settings.LOGIN_URL
    success_url = reverse_lazy('invoice_list')


class ListQuotes(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Quote
    permission_required = 'crm_core.view_quote'
    login_url = settings.LOGIN_URL
    fields = ['description', 'contract', 'customer', 'validuntil', 'lastmodifiedby',
              'last_calculated_price', 'last_pricing_date']


class CreateQuote(LoginRequiredMixin, PermissionRequiredMixin, CreateWithInlinesView):
    model = Quote
    inlines = [SalesContractPositionInline]
    form_class = QuoteForm
    permission_required = 'crm_core.add_quote'
    login_url = settings.LOGIN_URL
    fields = ['description', 'contract', 'customer', 'currency', 'lastmodifiedby',
              'last_calculated_price', 'last_pricing_date']
    success_url = reverse_lazy('quote_list')


class EditQuote(LoginRequiredMixin, PermissionRequiredMixin, UpdateWithInlinesView):
    model = Quote
    inlines = [SalesContractPositionInline]
    form_class = QuoteForm
    permission_required = 'crm_core.change_quote'
    login_url = settings.LOGIN_URL
    fields = ['description', 'contract', 'customer', 'currency', 'lastmodifiedby',
              'last_calculated_price', 'last_pricing_date']
    success_url = reverse_lazy('quote_list')


class DeleteQuote(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Quote
    permission_required = 'crm_core.delete_quote'
    login_url = settings.LOGIN_URL
    success_url = reverse_lazy('quote_list')