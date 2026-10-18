import re

from django import forms


class LoginForm(forms.Form):
    email = forms.EmailField(error_messages={"required": "Enter your email address.", "invalid": "That email doesn’t look right."})
    password = forms.CharField(error_messages={"required": "Enter your password."})
    remember = forms.BooleanField(required=False, initial=True)


class SignupForm(forms.Form):
    username = forms.CharField(max_length=30, error_messages={"required": "Choose a username."})
    email = forms.EmailField(error_messages={"required": "Enter your email address.", "invalid": "That email doesn’t look right."})
    password = forms.CharField(error_messages={"required": "Create a password."})
    terms = forms.BooleanField(error_messages={"required": "Please accept the Terms and Privacy Policy to continue."})

    def clean_username(self):
        username = self.cleaned_data["username"]
        if not re.fullmatch(r"[A-Za-z0-9_]{3,30}", username):
            raise forms.ValidationError("Use 3–30 letters, numbers, or underscores.")
        return username

    def clean_password(self):
        password = self.cleaned_data["password"]
        if len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
            raise forms.ValidationError("Use 8+ characters with at least one letter and one number.")
        return password
