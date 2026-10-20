from django import forms


class ResearchForm(forms.Form):
    query = forms.CharField(label='搜尋關鍵字', max_length=720,
        widget=forms.TextInput(attrs={'placeholder': '例如：Raspberry Pi 5 用途'}))
    question = forms.CharField(label='希望模型整理什麼？', max_length=600,
        initial='請整理主要用途、優點與限制，並標示來源。', widget=forms.Textarea(attrs={'rows': 3}))
    max_results = forms.IntegerField(label='最多來源數', min_value=1, max_value=8, initial=5)
    model = forms.CharField(label='模型名稱', max_length=160,
        help_text='使用 Pi 上已安裝的模型名稱；也可在此網站的 .env 設定預設值。')
