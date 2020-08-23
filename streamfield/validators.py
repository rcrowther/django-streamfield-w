import ipaddress
import re
from urllib.parse import urlsplit, urlunsplit

from django.core.exceptions import ValidationError
from django.utils.deconstruct import deconstructible
from django.utils.encoding import punycode
from django.utils.translation import gettext_lazy as _, ngettext_lazy
from django.core import validators



@deconstructible
class RelURLValidator(validators.RegexValidator):
    '''
    Validate an absolute or relative URL.
    This is different to django.validators.URLValidator. It will test
    domain/auth if present. But that information is not necessary. It
    will also accept a relative path section + optional query/fragment
    parameters only.
    '''
    ul = '\u00a1-\uffff'  # unicode letters range (must not be a raw string)

    # IP patterns
    ipv4_re = r'(?:25[0-5]|2[0-4]\d|[0-1]?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|[0-1]?\d?\d)){3}'
    ipv6_re = r'\[[0-9a-f:\.]+\]'  # (simple regex, validated later)

    # Host patterns
    hostname_re = r'[a-z' + ul + r'0-9](?:[a-z' + ul + r'0-9-]{0,61}[a-z' + ul + r'0-9])?'
    # Max length for domain name labels is 63 characters per RFC 1034 sec. 3.1
    domain_re = r'(?:\.(?!-)[a-z' + ul + r'0-9-]{1,63}(?<!-))*'
    tld_re = (
        r'\.'                                # dot
        r'(?!-)'                             # can't start with a dash
        r'(?:[a-z' + ul + '-]{2,63}'         # domain label
        r'|xn--[a-z0-9]{1,59})'              # or punycode label
        r'(?<!-)'                            # can't end with a dash
        r'\.?'                               # may have a trailing dot
    )
    host_re = '(' + hostname_re + domain_re + tld_re + '|localhost)'

    regex = validators._lazy_re_compile(
        # make scheme and userpass/port optional
        r'^(?:(?:[a-z0-9\.\-\+]*)://)?'  # scheme is validated separately
        r'(?:[^\s:@/]+(?::[^\s:@/]*)?@)?'  # user:pass authentication
        r'(?:(?:' + ipv4_re + '|' + ipv6_re + '|' + host_re + ')'
        r'(?::\d{2,5})?)?'  # port
        r"[\w\/$\-.+!*'():;?@&#]+"  # resource path
        r'\Z', re.IGNORECASE)
    message = _('Enter a valid URL.')
    schemes = ['http', 'https', 'ftp', 'ftps']

    def __init__(self, schemes=None, **kwargs):
        super().__init__(**kwargs)
        if schemes is not None:
            self.schemes = schemes

    def __call__(self, value):
        # Check first if the scheme is valid
        split = value.split('://')
        if (len(split) > 1):
            # in words, there was a split
            scheme = split[0].lower()
            if scheme not in self.schemes:
                raise ValidationError(self.message, code=self.code)

        # Then check full URL
        try:
            super().__call__(value)
        except ValidationError as e:
            # Trivial case failed. Try for possible IDN domain
            if value:
                try:
                    scheme, netloc, path, query, fragment = urlsplit(value)
                except ValueError:  # for example, "Invalid IPv6 URL"
                    raise ValidationError(self.message, code=self.code)
                try:
                    netloc = punycode(netloc)  # IDN -> ACE
                except UnicodeError:  # invalid domain part
                    raise e
                url = urlunsplit((scheme, netloc, path, query, fragment))
                super().__call__(url)
            else:
                raise
        else:
            # Now verify IPv6 in the netloc part
            host_match = re.search(r'^\[(.+)\](?::\d{2,5})?$', urlsplit(value).netloc)
            if host_match:
                potential_ip = host_match.groups()[0]
                try:
                    validate_ipv6_address(potential_ip)
                except ValidationError:
                    raise ValidationError(self.message, code=self.code)

        # The maximum length of a full host name is 253 characters per RFC 1034
        # section 3.1. It's defined to be 255 bytes or less, but this includes
        # one byte for the length of the name and one byte for the trailing dot
        # that's used to indicate absolute names in DNS.
        if len(urlsplit(value).netloc) > 253:
            raise ValidationError(self.message, code=self.code)
