from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError

User = get_user_model()


class RegistrationForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        help_text="150 characters or fewer. Letters, digits and @/./+/-/_ only.",
    )
    first_name = forms.CharField(max_length=150, label="First name")
    last_name = forms.CharField(max_length=150, label="Last name")
    email = forms.EmailField(label="Email address")
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput, strip=False)
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput, strip=False)

    def __init__(self, *args, invited_email=None, invited_name=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._invited_email = invited_email
        # Pre-fill and lock email/name fields for per-user invitation codes
        if invited_email:
            self.fields['email'].initial = invited_email
            self.fields['email'].widget.attrs['readonly'] = True
        if invited_name:
            parts = invited_name.split(' ', 1)
            self.fields['first_name'].initial = parts[0]
            self.fields['last_name'].initial = parts[1] if len(parts) > 1 else ''

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise ValidationError("This username is already taken.")
        return username

    def clean_email(self):
        email = self.cleaned_data['email']
        if self._invited_email and email != self._invited_email:
            raise ValidationError("You must register with the invited email address.")
        if User.objects.filter(email=email).exists():
            raise ValidationError("An account with this email address already exists.")
        return email

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise ValidationError("The two password fields didn't match.")
        return password2

    def _post_clean(self):
        super()._post_clean()
        password = self.cleaned_data.get('password2')
        if password:
            try:
                password_validation.validate_password(password)
            except ValidationError as error:
                self.add_error('password2', error)

    def save(self):
        return User.objects.create_user(
            username=self.cleaned_data['username'],
            email=self.cleaned_data['email'],
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
            password=self.cleaned_data['password1'],
        )


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise ValidationError("An account with this email address already exists.")
        return email
