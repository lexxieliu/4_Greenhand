from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy
from . import views
from .forms import ResetPasswordForm

app_name = "userprofile"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("register/", views.signup_view, name="signup"),
    path("profile/", views.profile, name="profile"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),
    path("profile/location/", views.location_edit, name="location_edit"),
    path("onboarding/", views.onboarding, name="onboarding"),
    path("onboarding/<int:step>/", views.onboarding, name="onboarding"),
    path("forgot-password/", auth_views.PasswordResetView.as_view(
        template_name="accounts/forgot_password.html",
        email_template_name="accounts/emails/password_reset_email.txt",
        subject_template_name="accounts/emails/password_reset_subject.txt",
        success_url=reverse_lazy("userprofile:password_reset_done"),
    ), name="password_reset"),
    path("forgot-password/sent/", auth_views.PasswordResetDoneView.as_view(
        template_name="accounts/forgot_password_sent.html",
    ), name="password_reset_done"),
    path("reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="accounts/reset_password.html",
        form_class=ResetPasswordForm,
        success_url=reverse_lazy("userprofile:password_reset_complete"),
    ), name="password_reset_confirm"),
    path("reset/done/", auth_views.PasswordResetCompleteView.as_view(
        template_name="accounts/reset_password_done.html",
    ), name="password_reset_complete"),
]
