from django import forms
from django.forms import widgets
from django.utils.safestring import mark_safe
from django.contrib.admin.widgets import AdminSplitDateTime
from django.utils.translation import get_language, gettext as _



class WithScript(widgets.Widget):
    '''
    Add extra functions to hook into rendering.
    '''
    def render_html(self, name, value, attrs, renderer=None):
        """Render the HTML (non-JS) portion of the field markup"""
        return super().render(name, value, attrs, renderer)

    def render(self, name, value, attrs=None, renderer=None):
        # no point trying to come up with sensible semantics for when 'id' is missing from attrs,
        # so let's make sure it fails early in the process
        try:
            id_ = attrs['id']
        except (KeyError, TypeError):
            raise TypeError("WidgetWithScript cannot be rendered without an 'id' attribute")

        widget_html = self.render_html(name, value, attrs, renderer)

        js = self.render_js_init(id_, name, value)
        out = '{0}<script>{1}</script>'.format(widget_html, js)
        return mark_safe(out)

    def render_js_init(self, id_, name, value):
        '''
        Override ti return a JS script after tthe widget.
        This can be used for initialisation of Javascript.
        id
            id of the associated widget. For multi-widgets, add a 
            traailing '_X' to get the id of the widgets in the list..
        '''
        return ''


        
class  MiniTimeWidget(WithScript, widgets.TimeInput):    
    '''
    Input placeholding a time format, and validating edits against the format.
    The widget responds to field and widget format declarations. 
    However, it is unable to function on any format but American 
    language, with a given separator, and limited set of fields,
    
        '%H': num hours (24)
        '%M': num minutes
        '%S': num seconds
        '%d': num day
        '%j': num day in year
        '%U': num week in year
        '%W': num week in year
        '%m': num month
        '%y': num short year
        '%Y': num long year
        '%a': short day
        '%b': short month
        
    If the format is not recognised, the Javascript will fail with a 
    warning. If your app is creating an unusable format, you can make 
    the widget work by stating a format on the field.
    
    Note that Django makes localisation of time/date by forcing formats 
    on the fields and widgets, If this widget is used in an 
    internationalised app, in most cases the format must be explicitly 
    stated.
    '''
    #NB date/time widgets localise in format_value(self, value):
    # They delocalize using strptime()/to_python() in the form field
    # This is not symetric, or easy to override
    def render_js_init(self, id_, name, value):
        return 'e = document.getElementById("{eid}"); DateTimeInputs.enable(e, "{wFormat}");'.format(
            eid = id_,
            wFormat=self.format or '%H:%M:%S',
        )
    
    
    
class MiniDateWidget(WithScript, widgets.DateInput):
    '''
    An input placeholding a date format, and validating edits against 
    the format.
    The widget responds to field and widget format declarations. 
    However, it is unable to function on any format but American 
    language, with a given separator, and limited set of fields,
    
        '%H': num hours (24)
        '%M': num minutes
        '%S': num seconds
        '%d': num day
        '%j': num day in year
        '%U': num week in year
        '%W': num week in year
        '%m': num month
        '%y': num short year
        '%Y': num long year
        '%a': short day
        '%b': short month
        
    If the format is not recognised, the Javascript will fail with a 
    warning. If your app is creating an unusable format, you can make 
    the widget work by stating a format on the field.
    
    Note that Django makes localisation of time/date by forcing formats 
    on the fields and widgets, If this widget is used in an 
    internationalised app, in most cases the format must be explicitly 
    stated.
    '''
    #NB date/time widgets localise in format_value(self, value):
    # They delocalize using strptime()/to_python() in the form field
    # This is not symetric, or easy to override
    def render_js_init(self, id_, name, value):
        return 'e = document.getElementById("{eid}"); DateTimeInputs.enable(e, "{wFormat}");'.format(
            eid=id_, 
            wFormat=self.format or '%d/%m/%Y',
            #wFormat='%Y / %m / %d',
        )
   

#from wagtail.admin.widgets import AdminDateTimeInput
class  MiniDateTimeWidget(WithScript, widgets.SplitDateTimeWidget):
    template_name = 'streamfield/widgets/split_datetime.html'

    def __init__(self, attrs=None):
        widgets = [MiniDateWidget, MiniTimeWidget]
        # Note that we're calling MultiWidget, not SplitDateTimeWidget, because
        # we want to define widgets.
        forms.MultiWidget.__init__(self, widgets, attrs)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['date_label'] = _('Date:')
        context['time_label'] = _('Time:')
        return context
        
    def render_js_init(self, id_, name, value):
        w1 = 'e = document.getElementById("{eid}_{wid}"); DateTimeInputs.enable(e, "{wFormat}");'.format(
            eid=id_, 
            wid=0,
            wFormat=self.widgets[0].format or '%d/%m/%Y',
        )
        w2 = 'e = document.getElementById("{eid}_{wid}"); DateTimeInputs.enable(e, "{wFormat}");'.format(
            eid = id_, 
            wid=1,
            wFormat=self.widgets[1].format or '%H:%M:%S',
        )
        return w1 + w2
        
        
    
class AutoHeightTextWidget(WithScript, widgets.Textarea):
    '''
    Textarea that eexpands and contracts with text content.
    '''
    def __init__(self, attrs=None):
        # Use more appropriate rows default, given autoheight will 
        # alter this anyway
        default_attrs = {'rows': '1'}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)

    def render_js_init(self, id_, name, value):
        return 'autosize(document.getElementById("{eid}"));'.format(eid=id_)

    class Media():
        js = (
            'admin/js/jquery.init.js',
            'streamfield/js/vendor/jquery.autosize.js',
        )
