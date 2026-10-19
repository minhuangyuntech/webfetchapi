from django import forms


class SearchForm(forms.Form):
    query = forms.CharField(label='搜尋對象與問題', max_length=720,
        widget=forms.TextInput(attrs={'placeholder': '例如：Raspberry Pi 5 適合哪些用途？', 'autofocus': True}))
    max_results = forms.IntegerField(label='最多來源數', min_value=1, max_value=8, initial=5)
