import re
from django.templatetags.static import static

def camelcase_to_underscore(s):
    # https://djangosnippets.org/snippets/585/
    return re.sub('(((?<=[a-z])[A-Z])|([A-Z](?![A-Z]|$)))', '_\\1', s).lower().strip('_')

def default_to_underscore(s, default=''):
    try:
        return camelcase_to_underscore(s)
    except AttributeError:
        return default
                
# def field_to_underscore(field):
    # try:
        # return camelcase_to_underscore(field.field.__class__.__name__)
    # except AttributeError:
        # try:
            # return camelcase_to_underscore(field.__class__.__name__)
        # except AttributeError:
            # return ""


# def field_widget_to_underscore(field):
    # try:
        # return camelcase_to_underscore(field.field.widget.__class__.__name__)
    # except AttributeError:
        # try:
            # return camelcase_to_underscore(field.widget.__class__.__name__)
        # except AttributeError:
            # return ""
                        
# from admin.static_files
def versioned_static(path):
    """
    Wrapper for Django's static file finder to append a cache-busting query parameter
    that updates on each Wagtail version
    """
    # An absolute path is returned unchanged (either a full URL, or processed already)
    if path.startswith(('http://', 'https://', '/')):
        return path

    base_url = static(path)

    # if URL already contains a querystring, don't add our own, to avoid interfering
    # with existing mechanisms
    #if VERSION_HASH is None or '?' in base_url:
    #    return base_url
    #else:
    #    return base_url + '?v=' + VERSION_HASH
    return base_url
        
        
SCRIPT_RE = re.compile(r'<(-*)/script>')

def escape_script(text):
    """
    Escape `</script>` tags in 'text' so that it can be placed within a `<script>` block without
    accidentally closing it. A '-' character will be inserted for each time it is escaped:
    `<-/script>`, `<--/script>` etc.
    """
    return SCRIPT_RE.sub(r'<-\1/script>', text)
