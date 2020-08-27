import datetime
import copy
from django import forms
from django.contrib import admin
from django.db.models.fields import BLANK_CHOICE_DASH
from django.forms.fields import CallableChoiceIterator
from django.template.loader import render_to_string
from django.utils.dateparse import parse_date, parse_datetime, parse_time
from django.utils.encoding import force_str
from django.utils.functional import cached_property
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from django.forms.widgets import Media, FileInput
from streamfield import widgets
from streamfield import utils
from streamfield.blocks.base import Block
from streamfield.form_fields import RelURLField
from streamfield.widgets import (
    AutoHeightTextWidget, 
    MiniTimeWidget, 
    MiniDateWidget,
    MiniDateTimeWidget,
)
        


class FieldBlock(Block):
    '''
    A block that wraps a Django form field.
    Can be used by itself, but mainly used as a base for creating blocks
    from most of the standard Django model fields.
    
    self.field
        Undeclared internal. A Django form field
        
    Some standard attributes from the form fields are exposed. Other 
    paremeters such as 'label_suffix', 'initial', 'error_messages', 
    'disabled', are fixed or not useful for blocks.
    
    required
        Works, but in a slightly different way to the usual attribute. If True (the default) the block inpput can not be empty, if the block is requested. 
    widget
        As usual, sets a differnt widget
    placeholder    
        set the placeholder on an input
            #initial  
    help_text
        Set a help tect on the block  
    validators
        Add validators to the block
    localize
        Will localise block displays

    Note that all blocks are required unless stated otherwise.
    '''
    #NB For implementers:
    # self.field is unallocated. You need to,
    # make __init__, call super()_ 
    #    not only for block base atrributes, but to ensure the widget 
    #    attribute is resolved and if not None, is a new instance 
    # then use __init__ to create a field
    #     the field should have 'widget': self.widget parameter, or the
    #     widget preference code will not operate
    widget = None
    
    #def __init__(self, widget=None, **kwargs):
    # 'reuired' is of less use, saying a block must be filled if deployed.
    # 'widget' is widget and can be set on the class, too.
    # 'label' and 'initial' parameters are not exposed, as Block handles
    # that functionality natively (via Media 'label' and 'default')
    #x  default to initial? No, initial is for placeholders. Default is 
    # on the model, if formfield is blank
    def __init__(self, 
            required=True, 
            widget=None, 
            placeholder='',
            #initial=None,  
            help_text=None,  
            validators=(),
            localize=False, 
            **kwargs
        ):
        #NB kwargs that reach block initialisation are placed on Meta.
        super().__init__(**kwargs)
        #if (not self.field):
        #    raise AttributeError("'field' is not declared. class:{}".format(self.__class__.__name__) )
        widget = widget or self.widget
        if (widget):
            if isinstance(widget, type):
                widget = widget()
            else:
                widget = copy.deepcopy(widget)
        self.placeholder = placeholder
        self.field_options = {
            'required': required,
            'widget':  widget,
            #'initial': initial,
            'help_text': help_text,
            'validators': validators,
            'localize': False,
        }

    def id_for_label(self, prefix):
        return self.field.widget.id_for_label(prefix)
                        
    def render_form(self, value, prefix='', errors=None):
        field = self.field
        widget = field.widget
        widget_attrs = {'id': prefix, 'placeholder': self.placeholder}
        field_value = field.prepare_value(self.value_for_form(value))
        widget_html = widget.render(prefix, field_value, attrs=widget_attrs)
        #print('render_form')
        #print(str(utils.default_to_underscore(widget.__class__.__name__, 'oqqq')))
        # Render the form fragment, with errors and help text
        return render_to_string('streamfield/block_forms/field.html', {
            'name': self.name,
            'widget': widget_html,
            'field': field,
            'fieldtype': utils.default_to_underscore(field.__class__.__name__),
            'widgettype': utils.default_to_underscore(widget.__class__.__name__),
            'errors': errors
        })

    def render_basic(self, value, context=None):
        if value:
            return format_html('{0}', value)
        else:
            return 
            
    def value_from_form(self, value):
        """
        Convert a form field's value to one that can be rendered by
        this block.
        
        The value that we get back from the form field might not be the 
        type that this block works with natively; for example, the block
        may want to wrap a simple value such as a string in an object 
        that provides a fancy HTML rendering (e.g. EmbedBlock).
        
        It transforms data from the datadict, and the return from 
        clean().

        We therefore provide this method to perform any necessary 
        conversion from the form field value to the block's native 
        value. As standard, this returns the form field value unchanged.
        """
        return value

    def value_for_form(self, value):
        """
        Convert this block's native value to one that can be rendered by
        the form field
        Reverse of value_from_form; Used to set up clean() and in render()
        """
        return value

    def value_from_datadict(self, data, files, prefix):
        return self.value_from_form(self.field.widget.value_from_datadict(data, files, prefix))

    def value_omitted_from_data(self, data, files, prefix):
        return self.field.widget.value_omitted_from_data(data, files, prefix)

    def clean(self, value):
        # We need an annoying value_for_form -> value_from_form round trip here to account for
        # the possibility that the form field is set up to validate a different value type to
        # the one this block works with natively
        return self.value_from_form(self.field.clean(self.value_for_form(value)))

    @property
    def media(self):
        return self.field.widget.media
        
    @property
    def required(self):
        # a FieldBlock is required if and only if its underlying form field is required
        return self.field.required

    class Meta:
        # Default value can be None, as a leaf block usually is
        # a *something* value
        default = None



class CharBlock(FieldBlock):

    def __init__(self,
        max_length=None, 
        min_length=None, 
        **kwargs
    ):
        super().__init__(**kwargs)
        self.field_options.update({
            'max_length':max_length,
            'min_length':min_length,
        })
        self.field = forms.CharField(
           **self.field_options
        )
        
    def render_basic(self, value, context=None):
        if value:
            return format_html('<span{1}>{0}</span>', 
                value,
                self.render_css_classes(context)
            )
        else:
            return 

    def get_searchable_content(self, value):
        return [force_str(value)]



class HeaderBlock(CharBlock):
    '''
    level
        level to set the HTML heading (<h1>, <h4> etc). Default=3.
    '''
    level = 3
    def __init__(self,
            level=3, 
            **kwargs
        ):
        #NB kwargs that reach block initialisation are placed on Meta.
        super().__init__(**kwargs)
        self.level = level or self.level
        
    def render_basic(self, value, context=None):
        if value:
            return format_html('<h{1}{2}>{0}</h{1}>', 
                value,
                self.level,
                self.render_css_classes(context)
            )
        else:
            return ''
            
            

class QuoteBlock(CharBlock):

    def render_basic(self, value, context=None):
        if value:
            return format_html('<quote{1}>{0}</quote>', 
                value,
                self.render_css_classes(context)
            )
        else:
            return ''
            


class RegexBlock(CharBlock):

    def __init__(self, regex, **kwargs):
        super().__init__(**kwargs)
        self.field_options.update({
            'regex':regex,
        })
        self.field = forms.RegexField(
           **self.field_options
        )



class EmailBlock(CharBlock):
    widget = admin.widgets.AdminEmailInputWidget
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.field = forms.EmailField(
           **self.field_options
        )


            
class URLBlock(CharBlock):
    '''
    Block for URLs.
    This uses Django core.validators.URLValidator so is strict. It 
    accepts a full-formed URL, with scheme, path etc. It will accept
    queries and fragments, and 'www' scheme, but not relative URIs.
    
    '''
    widget = admin.widgets.AdminURLFieldWidget
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.field = forms.URLField(
           **self.field_options
        )
                
    def render_basic(self, value, context=None):
        if value:
            return format_html('<span{1}>{0}</span>', 
                value,
                self.render_css_classes(context)
            )
        else:
            return 



class RelURLBlock(CharBlock):
    '''
    Block for URLs.
    This uses streamfield.RelURLValidator. It accepts a full-formed URL, 
    with scheme, path etc. but will also accept fragments and relative 
    URLs.
    '''
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.field = RelURLField(
           **self.field_options
        )  
        
    def render_basic(self, value, context=None):
        if value:
            return format_html('<span{1}>{0}</span>', 
                value,
                self.render_css_classes(context)
            )
        else:
            return 



 
class RawAnchorBlock(RelURLBlock):
    def render_basic(self, value, context=None):
        print(str(self.render_css_classes(context)))
        if value:
            return format_html('<a href="{0}"{1}>{0}</a>', 
                value, 
                self.render_css_classes(context)
            )
        else:
            return  
        
        
        
from .struct_block import StructBlock
class AnchorBlock(StructBlock):
    url = RelURLBlock()
    text = CharBlock()
    
    def render_basic(self, value, context=None):
        if value:
            return format_html('<a href="{0}"{2}>{1}</a>', 
                value['url'], 
                value['text'],
                self.render_css_classes(context),
            )
        else:
            return             



class TextBlock(FieldBlock):
    widget = AutoHeightTextWidget(attrs={'rows': 1})
    
    def __init__(self,
        max_length=None, 
        min_length=None, 
        **kwargs
    ):
        super().__init__(**kwargs)
        self.field_options.update({
            'max_length':max_length,
            'min_length':min_length,
        })
 
    @cached_property
    def field(self):
        return forms.CharField(**self.field_options)

    def get_searchable_content(self, value):
        return [force_str(value)]

    def render_basic(self, value, context=None):
        if value:
            return format_html('<p{1}>{0}</p>', 
                value,
                self.render_css_classes(context)
            )
        else:
            return 



class DefinitionBlock(StructBlock):
    term_block = CharBlock
    definition_block = TextBlock
    
    def __init__(self, term_block, definition_block, **kwargs):
        trm_block = term_block or self.term_block
        dfn_block = definition_block or self.definition_block

        # assert blocks are instances
        super().__init__(
            (('term', trm_block), ('definition', dfn_block)), 
            **kwargs
        )

    def render_basic(self, value, context=None):
        print(str(value))
        if value:
            return format_html('<dt{2}>{0}</dt><dd>{1}</dd>',
                self.child_blocks['term'].render(value['term'], context), 
                self.child_blocks['definition'].render(value['definition'], context),
                self.render_css_classes(context)
            )
        else:
            return  



class BlockQuoteBlock(TextBlock):

    def render_basic(self, value, context=None):
        if value:
            return format_html('<blockquote{1}>{0}</blockquote>',
                value,
                self.render_css_classes(context)
             )
        else:
            return ''



class RawHTMLBlock(TextBlock):
    # make a default HTML box start a little larger
    widget = AutoHeightTextWidget(attrs={'rows': 7})

    def get_default(self):
        return mark_safe(self.meta.default or '')

    def to_python(self, value):
        return mark_safe(value)

    def get_prep_value(self, value):
        # explicitly convert to a plain string, just in case we're using some serialisation method
        # that doesn't cope with SafeString values correctly
        return str(value) + ''

    def value_for_form(self, value):
        # need to explicitly mark as unsafe, or it'll output unescaped HTML in the textarea
        return str(value) + ''

    def value_from_form(self, value):
        return mark_safe(value)

    def render_basic(self, value, context=None):
        if value:
            return format_html('<div{1}>{0}</div>', 
                value,
                self.render_css_classes(context)
            )
        else:
            return 
            
            

class BooleanBlock(FieldBlock):

    def __init__(self, **kwargs):
        # NOTE: As with forms.BooleanField, the default of required=True means that the checkbox
        # must be ticked to pass validation (i.e. it's equivalent to an "I agree to the terms and
        # conditions" box). To get the conventional yes/no behaviour, you must explicitly pass
        # required=False.
        super().__init__(**kwargs)
        self.field = forms.BooleanField(
           **self.field_options
        )



class IntegerBlock(FieldBlock):
    widget = admin.widgets.AdminIntegerFieldWidget
    
    def __init__(self, 
        min_value=None,
        max_value=None, 
        **kwargs
    ):
        super().__init__(**kwargs)        
        self.field_options.update({
            'min_value':min_value,
            'max_value':max_value,
        })
        self.field = forms.IntegerField(
           **self.field_options
        )



class DecimalBlock(FieldBlock):
    widget = admin.widgets.AdminBigIntegerFieldWidget
    
    def __init__(self,
        max_value=None, 
        min_value=None,
        max_digits=None, 
        decimal_places=None, 
        **kwargs
    ):
        super().__init__(**kwargs)
        self.field_options.update({
            'min_value':min_value,
            'max_value':max_value,
            'max_digits':max_digits,
            'decimal_places':decimal_places,
        })
        self.field = forms.DecimalField(
           **self.field_options
        )


class FloatBlock(FieldBlock):

    def __init__(self,
        max_value=None, 
        min_value=None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.field_options.update({
            'min_value':min_value,
            'max_value':max_value,
        })
        self.field = forms.FloatField(
           **self.field_options
        )

# import posixpath

# from django.core.files import File
# from django.db.models.fields.files import FileField

# class FieldFileDumb(File):
    # def __init__(self, name, upload_to='', max_length=255, storage=None):
    # #def __init__(self, instance, field, name):
        # # Django file takes two params, the file and an optional name.
        # # but it will fuction if the file is None.
        # super().__init__(None, name)
        # self.storage = storage
        # self.upload_to = upload_to
        # self.max_length = max_length
        # #self.instance = instance
        # #self.field = field
        # self._committed = True

    # def __eq__(self, other):
        # # Older code may be expecting FileField values to be simple strings.
        # # By overriding the == operator, it can remain backwards compatibility.
        # if hasattr(other, 'name'):
            # return self.name == other.name
        # return self.name == other

    # def __hash__(self):
        # return hash(self.name)

    # # The standard File contains most of the necessary properties, but
    # # FieldFiles can be instantiated without a name, so that needs to
    # # be checked for here.

    # def _require_file(self):
        # if not self:
            # raise ValueError("The '%s' attribute has no file associated with it." % self.name)

    # def _get_file(self):
        # self._require_file()
        # if getattr(self, '_file', None) is None:
            # self._file = self.storage.open(self.name, 'rb')
        # return self._file

    # def _set_file(self, file):
        # self._file = file

    # def _del_file(self):
        # del self._file

    # file = property(_get_file, _set_file, _del_file)

    # @property
    # def path(self):
        # self._require_file()
        # return self.storage.path(self.name)

    # @property
    # def url(self):
        # self._require_file()
        # return self.storage.url(self.name)

    # @property
    # def size(self):
        # self._require_file()
        # if not self._committed:
            # return self.file.size
        # return self.storage.size(self.name)

    # def open(self, mode='rb'):
        # self._require_file()
        # if getattr(self, '_file', None) is None:
            # self.file = self.storage.open(self.name, mode)
        # else:
            # self.file.open(mode)
        # return self
    # # open() doesn't alter the file's contents, but it does reset the pointer
    # open.alters_data = True

    # # In addition to the standard File API, FieldFiles have extra methods
    # # to further manipulate the underlying file, as well as update the
    # # associated model instance.

    # def save(self, name, content, save=True):
        # #name = self.field.generate_filename(self.instance, name)
        # name = posixpath.join(self.upload_to, name)
        # #name = self.storage.generate_filename(filename)
        # self.name = self.storage.save(name, content, max_length=self.max_length)
        # #setattr(self.instance, self.field.name, self.name)
        # self._committed = True

        # # Save the object because it has changed, unless save is False
        # #if save:
            # #self.instance.save()
    # save.alters_data = True

    # def delete(self, save=True):
        # if not self:
            # return
        # # Only close the file if it's already open, which we know by the
        # # presence of self._file
        # if hasattr(self, '_file'):
            # self.close()
            # del self.file

        # self.storage.delete(self.name)

        # self.name = None
        # #setattr(self.instance, self.field.name, self.name)
        # self._committed = False

        # #if save:
        # #    self.instance.save()
    # delete.alters_data = True

    # @property
    # def closed(self):
        # file = getattr(self, '_file', None)
        # return file is None or file.closed

    # def close(self):
        # file = getattr(self, '_file', None)
        # if file is not None:
            # file.close()

    # def __getstate__(self):
        # # FieldFile needs access to its associated model field and an instance
        # # it's attached to in order to work properly, but the only necessary
        # # data to be pickled is the file's name itself. Everything else will
        # # be restored later, by FileDescriptor below.
        # return {'name': self.name, 'closed': False, '_committed': True, '_file': None}
        
        
# from django.core.files.storage import default_storage

# class FileBlock(FieldBlock):
    # needs_multipart_form = True
    
    # def __init__(self, 
        # required=True, 
        # help_text=None, 
        # validators=(),
        # max_length=None, 
        # upload_to='', 
        # storage=None,
        # allow_empty_file=False, 
        # **kwargs
    # ):
        # # This is how it works - uploaded files are something like
        # # InMemoryUploadedFile. These get wrapped in a upload
        # # handler, like MemoryFileUploadHandler in the request, then 
        # # managed. But the uphot is, post.files are 
        # # InMemoryUploadedFile.
        # # 
        # # That's not all. clean() and save() take values from the 
        # # instance field attribute. This is a descriptor packed with
        # # trickery. Broadly, if the value is only a string, it gets 
        # # wrapped in  attr_class which is FieldFile or ImageFieldFile.
        # # Non-string files get wrapped in attr_class, with 
        # # the file attribute set and  _committed = False
        # # 
        # # In admin, files are bound, for sure. But what does that mean?
        # # because there is no field to bind to (it's a streamfield).
        # # And this is how formdata gets to a field, by binding it 
        # # The big problem here is the lack of model machinery,
        # # speciality pre_save() is not called, because there is no
        # # model field
        # Somehow, that bound value needs changing.
        # super().__init__(**kwargs)

        # self.model_opts = {
            # 'upload_to':upload_to, 
            # 'storage':storage or default_storage, 
            # 'max_length': max_length
        # }
        
        # self.field = forms.FileField(
            # required=required,
            # help_text=help_text,
            # validators=validators,
            # max_length=max_length,
            # #name=None,
            # #upload_to='', 
            # #storage=None,
            # allow_empty_file=allow_empty_file,
            # widget=FileInput,
            # **kwargs
        # )

    # #def value_from_form(self, value):
    # #    pass
        
    # #def value_for_form(self, value):
    # #    pass

    # #? cache
    # def file_descriptor(self, value):
        # '''
        # A model-field like descriptor.
        # Works like the model field descriptor, but needs and works on
        # no instance.
        # value
            # string, File or FieldFile
        # '''
        # if isinstance(value, str) or value is None:
            # file = FieldFileDumb(value, **self.model_opts)
        # elif isinstance(value, File) and not isinstance(value, FieldFile):
            # file = FieldFileDumb(str(value), **self.model_opts)
            # file.file = value
            # file._committed = False
            
        # #? can happen on pickle, it is said
        # elif isinstance(value, FieldFileDumb) and not hasattr(value, 'file'):
            # file = FieldFileDumb(str(value), **self.model_opts)
            # file.file = value
        # return file
        
    # def to_python(self, value):
        # # The model version does nothing
        # # The formfield gets an UploadedFile object
        # # all we get is a string.
        # # No, this overrides form. But without a field, it's getting a 
        # # raw string
        # # it probably needs the descriptor gear
        # # if value in self.empty_values:
            # # return None
        # # if value is None or isinstance(value, datetime.date):
            # # return value
        # # else:
            # # return parse_date(value)
        # print('FileBlock to_python')
        # print(str(value))
        # print(str(value.__class__))
        # # A FileDescriptor would  wrap in a FieldFile
        # # value of None is acceptable.
        # value = FieldFileDumb(value, **self.model_opts)

        # print(str(value))
        # print(str(value.__class__))
        # # to_python() in a form would be supplied with a FieldFile value.
        # #return self.field.to_python(value)
        # return value

   # # def value_from_form(self, value):

    # # def clean(self, value):
        # # # ChooserBlock works natively with model instances as its 'value' type (because that's what you
        # # # want to work with when doing front-end templating), but ModelChoiceField.clean expects an ID
        # # # as the input value (and returns a model instance as the result). We don't want to bypass
        # # # ModelChoiceField.clean entirely (it might be doing relevant validation, such as checking page
        # # # type) so we convert our instance back to an ID here. It means we have a wasted round-trip to
        # # # the database when ModelChoiceField.clean promptly does its own lookup, but there's no easy way
        # # # around that...
        # # if isinstance(value, self.target_model):
            # # value = value.pk
        # # return super().clean(value)
        
    # def get_prep_value(self, value):
        # #value = super().get_prep_value(value)
        # # Need to convert File objects provided via a form to string for database insertion
        # #?     def save_form_data(self, instance, data):
        # if value is None:
            # return None
        # return str(value)

    # def pre_save_hook(self, field_value, value):
        # # The value is a upload file, but needs to be....
        # print('FileBlock pre_save_hook')
        # print(str(value.__class__))
        # file = FieldFileDumb(str(value), **self.model_opts)
        # file.file = value
        # file._committed = False
        # print(str(file))
        # if file and not file._committed:
            # # Commit the file to storage prior to saving the model
            # file.save(file.name, file.file, save=False)
            # value = file.name
            # print('saved to')
            # print(str(file.name))
            
        # print('_')
        # #return file
        
    # #def value_from_datadict(self, data, files, prefix):
    # #    return super().value_from_datadict(data, files, prefix)



class TimeBlock(FieldBlock):
    widget = MiniTimeWidget
    
    def __init__(self, input_formats=None, **kwargs):
        super().__init__(**kwargs)
        self.field_options.update({
            'input_formats': input_formats,
        })
        
    @property
    def media(self):
        return Media(
            js = [
            'streamfield/js/widgets/DateTimeInputs.js',
        ])
        
    @cached_property
    def field(self):
        return forms.TimeField(**self.field_options)

    def to_python(self, value):
        if value is None or isinstance(value, datetime.time):
            return value
        else:
            return parse_time(value)

    def render_basic(self, value, context=None):
        if value:
            return format_html('<time{1}>{0}</time>',
                value,
                self.render_css_classes(context)
            )
        else:
            return 
                        
            
            
class DateBlock(FieldBlock):
    widget = MiniDateWidget
    
    def __init__(self, input_formats=None, **kwargs):
        super().__init__(**kwargs)
        self.field_options.update({
            'input_formats': input_formats,
        })
        
    @property
    def media(self):
        return Media(
            js = [
            'streamfield/js/widgets/DateTimeInputs.js',
        ])

    @cached_property
    def field(self):
        return forms.DateField(**self.field_options)

    def to_python(self, value):
        # Serialising to JSON uses DjangoJSONEncoder, which converts date/time objects to strings.
        # The reverse does not happen on decoding, because there's no way to know which strings
        # should be decoded; we have to convert strings back to dates here instead.
        #
        #? Which is cute but why not evoke all the localisation and formatting via the field
        if value is None or isinstance(value, datetime.date):
            return value
        else:
            return parse_date(value)

    def render_basic(self, value, context=None):
        if value:
            return format_html('<time{1}>{0}</time>', 
                value,
                self.render_css_classes(context)
            )
        else:
            return 
            
            

class DateTimeBlock(FieldBlock):
    widget = MiniDateTimeWidget
    
    def __init__(self,
        input_date_formats=None, 
        input_time_formats=None,
        **kwargs
    ):
        
        super().__init__(**kwargs)
        self.field_options.update({
            'input_date_formats': input_date_formats,
            'input_time_formats': input_time_formats,
        })
        
    @cached_property
    def field(self):
        return forms.SplitDateTimeField(**self.field_options)

    def to_python(self, value):
        if value is None or isinstance(value, datetime.datetime):
            return value
        else:
            return parse_datetime(value)
            
    def render_basic(self, value, context=None):
        if value:
            return format_html('<time{1}>{0}</time>', 
                value,
                self.render_css_classes(context)
            )
        else:
            return 
            


class ChoiceBlockBase(FieldBlock):
    '''
    A block handling choices.
    Choices can be declared as literals or via. enumerations. See Django
    documentation 
    https://docs.djangoproject.com/en/3.0/ref/models/fields/#choices
    The blocks will handle the types and their storage. 
    However, these blocks cut back on Wagtail/Django provision, they 
    need static declarations, and will not will not accept callables, 
    etc. 
    '''
    choices = ()

    def __init__(
            self, 
            choices=None, 
            default=None,
            **kwargs
    ):
        super().__init__(default=default, **kwargs)

        if choices is None:
            # no choices specified, so pick up the choice defined at the class level
            choices = self.choices
        choices = list(choices)
        
        # if not required, and no blank option, force a blank option.
        if (not(self.field_options['required']) and not(self.has_blank_choice(choices))):
            choices = BLANK_CHOICE_DASH + choices
            
        self.field_options.update({
            'choices': choices,
        })      
        self.field = self.field_model(
           **self.field_options
        )

    def has_blank_choice(self, choices):
        has_blank_choice = False
        for v1, v2 in choices:
            if isinstance(v2, (list, tuple)):
                # this is a named group, and v2 is the value list
                has_blank_choice = any([value in ('', None) for value, label in v2])
                if has_blank_choice:
                    break
            else:
                # this is an individual choice; v1 is the value
                if v1 in ('', None):
                    has_blank_choice = True
                    break
        return has_blank_choice
                  
        

class ChoiceBlock(ChoiceBlockBase):
    field_model = forms.ChoiceField
    
    # def deconstruct(self):
        # """
        # Always deconstruct ChoiceBlock instances as if they were plain ChoiceBlocks with their
        # choice list passed in the constructor, even if they are actually subclasses. This allows
        # users to define subclasses of ChoiceBlock in their models.py, with specific choice lists
        # passed in, without references to those classes ending up frozen into migrations.
        # """
        # return ('streamfield.blocks.ChoiceBlock', [], self._constructor_kwargs)

    def get_searchable_content(self, value):
        # Return the display value as the searchable value
        text_value = force_str(value)
        for k, v in self.field.choices:
            if isinstance(v, (list, tuple)):
                # This is an optgroup, so look inside the group for options
                for k2, v2 in v:
                    if value == k2 or text_value == force_str(k2):
                        return [force_str(k), force_str(v2)]
            else:
                if value == k or text_value == force_str(k):
                    return [force_str(v)]
        return []

    def render_basic(self, value, context=None):
        return format_html('<span{1}>{0}</span>', 
            value,
            self.render_css_classes(context)
        )



class MultipleChoiceBlock(ChoiceBlockBase):
    field_model = forms.MultipleChoiceField

    # def deconstruct(self):
        # """
        # Always deconstruct MultipleChoiceBlock instances as if they were plain
        # MultipleChoiceBlocks with their choice list passed in the constructor,
        # even if they are actually subclasses. This allows users to define
        # subclasses of MultipleChoiceBlock in their models.py, with specific choice
        # lists passed in, without references to those classes ending up frozen
        # into migrations.
        # """
        # return ('streamfield.blocks.MultipleChoiceBlock', [], self._constructor_kwargs)

    def get_searchable_content(self, value):
        # Return the display value as the searchable value
        content = []
        text_value = force_str(value)
        for k, v in self.field.choices:
            if isinstance(v, (list, tuple)):
                # This is an optgroup, so look inside the group for options
                for k2, v2 in v:
                    if value == k2 or text_value == force_str(k2):
                        content.append(force_str(k))
                        content.append(force_str(v2))
            else:
                if value == k or text_value == force_str(k):
                    content.append(force_str(v))
        return content

    def render_basic(self, value, context=None):
        #? format_html_join() flakes...
        optionsL = [format_html('<li>{0}</li>', v) for v in value]
        options = mark_safe(''.join(optionsL))
        return format_html('<ul{1}>{0}</ul>', 
            options,
            self.render_css_classes(context)
        )




class ModelChoiceBlockBase(FieldBlock):
    '''
    Base for fields that implement a choice of models.
    It works with model instances as it's values. The block has the 
    expense of a DB lookup. However, it opens the possibility of 
    selecting on Django models, which may be worth the expense.
    
    This is not a choice of enumerables, see ChoiceBlock and 
    MultipleChoiceBlock for that.
    
    target_model
        The model to do queries on
    target_filter
        A query to limit offered options. The query is organised as a 
        dict e.g. {'headline__contains':'Lennon'} 
    to_field_name
        The model field to use to supply label names.
    empty_label
        An alternative to the default empty label, which is '--------'
    '''
    def __init__(self, 
        target_model,
        target_filter={},
        to_field_name=None,
        empty_label="---------",
        **kwargs
    ):
        super().__init__(**kwargs)
        self.target_model = target_model
        if issubclass(target_model, Model):
            raise AttributeError("'target_model' must be a Model. class:{}".format(self.__class__.__name__) )
        self.field_options.update({
            'queryset': target_model.objects.filter(target_filter),
            'to_field_name': to_field_name,
            'empty_label': empty_label,
        })
        
        
        
class ModelChoiceBlock(ModelChoiceBlockBase):
    '''
    Base for fields that implement a choice of models.
    It works with model instances as it's values. The block has the 
    expense of a DB lookup. However, it opens the possibility of 
    selecting on any Django model, which may be worth the expense.
    
    This is not a choice of enumerables, see ChoiceBlock and 
    MultipleChoiceBlock for that.
    '''
        
    """Abstract superclass for fields that implement a chooser interface (page, image, snippet etc)"""
    @cached_property
    def field(self):
        return forms.ModelChoiceField(
            **self.field_options
        )
        
    def to_python(self, value):
        # the incoming serialised value should be None or an ID
        if value is None:
            return value
        else:
            try:
                return self.target_model.objects.get(pk=value)
            except self.target_model.DoesNotExist:
                return None

    # def bulk_to_python(self, values):
        # """Return the model instances for the given list of primary keys.

        # The instances must be returned in the same order as the values and keep None values.
        # """
        # objects = self.target_model.objects.in_bulk(values)
        # return [objects.get(id) for id in values]  # Keeps the ordering the same as in values.

    def get_prep_value(self, value):
        # the native value (a model instance or None) should serialise to a PK or None
        if value is None:
            return None
        else:
            return value.pk

    def value_from_form(self, value):
        # ModelChoiceField sometimes returns an ID, and sometimes an instance; we want the instance
        if value is None or isinstance(value, self.target_model):
            return value
        else:
            try:
                return self.target_model.objects.get(pk=value)
            except self.target_model.DoesNotExist:
                return None

    def clean(self, value):
        # ChooserBlock works natively with model instances as its 'value' type (because that's what you
        # want to work with when doing front-end templating), but ModelChoiceField.clean expects an ID
        # as the input value (and returns a model instance as the result). We don't want to bypass
        # ModelChoiceField.clean entirely (it might be doing relevant validation, such as checking page
        # type) so we convert our instance back to an ID here. It means we have a wasted round-trip to
        # the database when ModelChoiceField.clean promptly does its own lookup, but there's no easy way
        # around that...
        if isinstance(value, self.target_model):
            value = value.pk
        return super().clean(value)

    def value_from_form(self, value):
        # ModelChoiceField sometimes returns IDs, and sometimes instances; we want the instance
        if value is None or isinstance(value, self.target_model):
            return value
        else:
            try:
                return self.target_model.objects.get(pk=value)
            except self.target_model.DoesNotExist:
                return None



class ModelMultipleChoiceBlock(ModelChoiceBlock):

    @cached_property
    def field(self):
        # # return forms.ModelChoiceField(
            # # queryset=self.target_model.objects.all(), widget=self.widget, required=self._required,
            # # validators=self._validators,
            # # help_text=self._help_text)
        return forms.ModelMultipleChoiceField(
            **self.field_options
        )

    def to_python(self, value):
        # # the incoming serialised value should be None or IDs
        if value is None:
            return value
        else:
            try:
                return self.target_model.objects.filter(pk__in=value)
            except self.target_model.DoesNotExist:
                return None
                
    def get_prep_value(self, value):
        # the native value (a model instance or None) should serialise to PKs or None
        if value is None:
            return None
        else:
            return [e.pk for e in value]                

    def clean(self, value):
        # ChooserBlocks work natively with model instances as its 'value' type (because that's what you
        # want to work with when doing front-end templating), but ModelChoiceField.clean expects an ID
        # as the input value (and returns a model instance as the result). We don't want to bypass
        # ModelChoiceField.clean entirely (it might be doing relevant validation, such as checking page
        # type) so we convert our instance back to an ID here. It means we have a wasted round-trip to
        # the database when ModelChoiceField.clean promptly does its own lookup, but there's no easy way
        # around that...
        #        if not isinstance(value, (list, tuple)):
        if isinstance(value[0], self.target_model):
            value = value.pk
        return super().clean(value)
        
    def value_from_form(self, value):
        # ModelChoiceField sometimes returns an ID, and sometimes an instance; we want the instance
        if value is None or isinstance(value[0], self.target_model):
            return value
        else:
            try:
                return self.field_options['target_model'].objects.filter(pk__in=value)
            except self.field_options['target_model'].DoesNotExist:
                return None
                    
                    
                                
# Ensure that the blocks defined here get deconstructed as streamfield.blocks.FooBlock
# rather than streamfield.blocks.field_block.FooBlock
block_classes = [
    FieldBlock, 
    CharBlock, HeaderBlock, QuoteBlock, EmailBlock, RegexBlock, URLBlock, RelURLBlock,
    RawAnchorBlock, AnchorBlock,
    TextBlock, BlockQuoteBlock, RawHTMLBlock, 
    BooleanBlock, 
    IntegerBlock, DecimalBlock, FloatBlock,  
    DateBlock, TimeBlock, DateTimeBlock, 
    ChoiceBlock, MultipleChoiceBlock,
]

DECONSTRUCT_ALIASES = {
    cls: 'streamfield.blocks.%s' % cls.__name__
    for cls in block_classes
}
__all__ = [cls.__name__ for cls in block_classes]
