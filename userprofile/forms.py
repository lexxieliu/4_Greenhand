import datetime
import re

from django import forms
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.models import User
from django.core.files.uploadedfile import UploadedFile

from .models import Profile
from .services import clean_avatar


def check_password_rule(password):
    """Shared by signup and password reset: 8+ characters with a letter and a number."""
    if len(password) < 8 or not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise forms.ValidationError("Use 8+ characters with at least one letter and one number.")
    return password


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
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("That username is taken.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_password(self):
        return check_password_rule(self.cleaned_data["password"])


class ResetPasswordForm(SetPasswordForm):
    def clean_new_password1(self):
        return check_password_rule(self.cleaned_data["new_password1"])


# ---------- Onboarding wizard (PRD 3.1) ----------

class LocationSearchForm(forms.Form):
    query = forms.CharField(max_length=100, error_messages={"required": "Enter your city or town."})

    def clean_query(self):
        return self.cleaned_data["query"].strip()


class LocationChoiceForm(forms.Form):
    """The place the user picked from the search results (a JSON blob in the radio value)."""
    city = forms.CharField(max_length=100)
    region = forms.CharField(max_length=100, required=False)
    country_code = forms.CharField(max_length=2, required=False)
    latitude = forms.DecimalField(min_value=-90, max_value=90, max_digits=12, decimal_places=8)
    longitude = forms.DecimalField(min_value=-180, max_value=180, max_digits=12, decimal_places=8)
    timezone = forms.CharField(max_length=50, required=False)

    def clean_latitude(self):
        return round(self.cleaned_data["latitude"], 2)

    def clean_longitude(self):
        return round(self.cleaned_data["longitude"], 2)


class SpaceForm(forms.Form):
    space_type = forms.ChoiceField(choices=Profile.Space.choices, widget=forms.RadioSelect(attrs={"class": "peer sr-only"}),
                                   error_messages={"required": "Pick the space you will grow in."})


class SunlightForm(forms.Form):
    sunlight_level = forms.ChoiceField(choices=Profile.Sunlight.choices, widget=forms.RadioSelect(attrs={"class": "peer sr-only"}),
                                       error_messages={"required": "Pick how much sun your space gets."})


class ExperienceForm(forms.Form):
    experience_level = forms.ChoiceField(choices=Profile.Experience.choices, widget=forms.RadioSelect(attrs={"class": "peer sr-only"}),
                                         error_messages={"required": "Pick your experience level."})


# ---------- Profile (PRD FR-02/FR-04) ----------

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["display_name", "avatar", "bio", "pronouns", "birthdate",
                  "space_type", "sunlight_level", "experience_level", "units"]
        widgets = {
            "birthdate": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "bio": forms.Textarea(attrs={"rows": 3}),
            "avatar": forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["space_type"].required = True
        self.fields["sunlight_level"].required = True
        for name, field in self.fields.items():
            if name != "avatar":
                field.widget.attrs.setdefault("class", "field-input")

    def clean_birthdate(self):
        birthdate = self.cleaned_data["birthdate"]
        if birthdate and birthdate > datetime.date.today():
            raise forms.ValidationError("Birthday can't be in the future.")
        return birthdate

    def clean_avatar(self):
        avatar = self.cleaned_data["avatar"]
        if isinstance(avatar, UploadedFile):  # a new upload; anything else is "keep" or "clear"
            try:
                return clean_avatar(avatar)
            except ValueError as exc:
                raise forms.ValidationError(str(exc)) from exc
        return avatar

    def save(self, commit=True):
        old_avatar = Profile.objects.get(pk=self.instance.pk).avatar if self.instance.pk else None
        profile = super().save(commit)
        if commit and old_avatar and "avatar" in self.changed_data and old_avatar.name != profile.avatar.name:
            old_avatar.storage.delete(old_avatar.name)
        return profile
