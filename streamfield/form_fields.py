import re
from urllib.parse import urlsplit, urlunsplit
from django.core.exceptions import ValidationError
from django.forms.widgets import TextInput
from django.utils.translation import gettext_lazy as _, ngettext_lazy
from django.forms.fields import CharField
from streamfield.validators import RelURLValidator

from streamfield.validators import validators



class RelURLField(CharField):
    #NB URL Inputs are for absolute URLs. They'll potentially display
    # incorrect/unhelpful dropdowns for relative URLs.
    widget = TextInput
    default_error_messages = {
        'invalid': _('Enter a valid URL.'),
    }
    default_validators = [RelURLValidator()]

    def __init__(self, **kwargs):
        super().__init__(strip=True, **kwargs)

    def to_python(self, value):

        def split_url(url):
            """
            Return a list of url parts via urlparse.urlsplit(), or raise
            ValidationError for some malformed URLs.
            """
            try:
                return list(urlsplit(url))
            except ValueError:
                # urlparse.urlsplit can raise a ValueError with some
                # misformatted URLs.
                raise ValidationError(self.error_messages['invalid'], code='invalid')

        value = super().to_python(value)
        if value:
            url_fields = split_url(value)
            if not url_fields[0]:
                # If no URL scheme given, assume http://
                #NB annoying. A one-line change
                #url_fields[0] = 'http'
                url_fields[0] = ''
            if not url_fields[1]:
                # Assume that if no domain is provided, that the path segment
                # contains the domain.
                url_fields[1] = url_fields[2]
                url_fields[2] = ''
                
                # Rebuild the url_fields list, since the domain segment may now
                # contain the path too.
                url_fields = split_url(urlunsplit(url_fields))
            value = urlunsplit(url_fields)
        return value
