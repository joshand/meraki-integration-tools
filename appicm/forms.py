from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.forms import ModelForm
from appicm.models import UploadZip


class SignUpForm(UserCreationForm):
    first_name = forms.CharField(max_length=30, required=False, help_text='Optional.')
    last_name = forms.CharField(max_length=30, required=False, help_text='Optional.')
    email = forms.EmailField(max_length=254, help_text='Required. Inform a valid email address.')

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password1', 'password2')


class UploadForm(ModelForm):
    description = forms.CharField(max_length=255, required=False, widget=forms.HiddenInput())
    tenant_id = forms.HiddenInput()
    file = forms.FileField()

    class Meta:
        model = UploadZip
        fields = ('file', )

