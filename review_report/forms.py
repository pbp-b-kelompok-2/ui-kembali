from django import forms
from .models import Report

INPUT = 'w-full rounded-xl border border-line bg-canvas p-3 text-ink focus:outline-2 focus:outline-green focus:outline-offset-2'


class ReviewForm(forms.Form):
    rating = forms.TypedChoiceField(label='Beri rating keseluruhan', choices=[(n, f'{n} bintang') for n in range(1, 6)], coerce=int, widget=forms.RadioSelect)
    comment = forms.CharField(label='Tulis ulasan', min_length=10, max_length=1000, widget=forms.Textarea(attrs={'class': INPUT, 'rows': 5, 'placeholder': 'Ceritakan pengalaman transaksimu…'}))


class ReportForm(forms.Form):
    category = forms.ChoiceField(label='Kategori masalah', choices=Report.Category.choices, widget=forms.Select(attrs={'class': INPUT}))
    description = forms.CharField(label='Deskripsi masalah', min_length=20, max_length=2000, widget=forms.Textarea(attrs={'class': INPUT, 'rows': 6, 'placeholder': 'Jelaskan kejadian dan informasi yang membantu pemeriksaan…'}))


class ReviewFilterForm(forms.Form):
    rating = forms.TypedChoiceField(required=False, coerce=int, empty_value=None, choices=[('', 'Semua rating')] + [(n, f'{n} bintang') for n in range(1, 6)], widget=forms.Select(attrs={'class': INPUT}))
    transaction_type = forms.ChoiceField(required=False, label='Jenis transaksi', choices=[('', 'Semua transaksi'), ('ADOPSI', 'Adopsi gratis'), ('JUAL', 'Pembelian')], widget=forms.Select(attrs={'class': INPUT}))
