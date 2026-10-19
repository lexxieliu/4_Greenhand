from django import forms

from tutor.guardrails import MAX_RAW_CHARS


class PostForm(forms.Form):
    post_content = forms.CharField(
        label="What is happening in your garden?",
        max_length=MAX_RAW_CHARS,
        widget=forms.Textarea(attrs={
            "rows": 5,
            "class": "form-control",
            "placeholder": "Share a tip, a question, or a photo-worthy win...",
        }),
    )
