import collections
from importlib import import_module

from django import forms
from django.core import checks
from django.core.exceptions import ImproperlyConfigured
from django.template.loader import render_to_string
from django.utils.encoding import force_str
from django.utils.safestring import mark_safe
from django.utils.text import capfirst
from streamfield.utils import escape_script, versioned_static

__all__ = [
    'BaseBlock', 
    'Block',    
    'BoundBlock', 
    'DeclarativeSubBlocksMetaclass', 
    'BlockWidget', 
    'BlockField'
]


# =========================================
# Top-level superclasses and helper objects
# =========================================

#NB I don't find block code clever or neat, I think it's impenetrable and
# ugly. It may be efficient and it works. I'd wipe the lot out for
# some clarity in data structure, but that goes for most of Django, R.C.
class BaseBlock(type):
    def __new__(mcs, name, bases, attrs):
        meta_class = attrs.pop('Meta', None)

        cls = super(BaseBlock, mcs).__new__(mcs, name, bases, attrs)

        # Get all the Meta classes from all the bases
        meta_class_bases = [meta_class] + [getattr(base, '_meta_class', None)
                                           for base in bases]
        meta_class_bases = tuple(filter(bool, meta_class_bases))
        cls._meta_class = type(str(name + 'Meta'), meta_class_bases, {})

        return cls


class Block(metaclass=BaseBlock):
    '''
    A base for all StreamField blocks.
    The class is not a Django entity in itself. It is defined with
    common, or to make available, functionality of other classes.
     
    It can do seme model-field actions which cascade through the 
    block heap e.g.
    - clean()
    - get_prep_value()
    To make a model-field, it needs to be wrapped in BlockField, and 
    to make a form-widget it must be wrapped in BlockWidget.
    
    It can do some form-widget actions, like
    - render()
    - carry Media

    When wrapping Django fields, Block can be bound with data in 
    a streamfield.forms.BoundFieldWithErrors. 
    
    Also note, this base is not the default Block for a StreamField, 
    that is the subclass StreamBlock.
    
    label
        if '' is set from the name (which is the declared key of the 
        block)
    css_classes
        list of strings to be used as classnames in HTML rendering. The 
        value is passed to the context. 
    '''
    # Name of the block
    # The value is structurally significant, used for locating data 
    # values. It is also used for the label, if a label is not provided.
    # It is set by the user, in declarations picked up by __new__(),
    # in collection blocks by __init__()
    name = ''
    #NB labels are not changeable, as it happens, and not even used in 
    # code!
    label = ''
    creation_counter = 0

    TEMPLATE_VAR = 'value'

    # widget attribute, may be overrrden in initialization.
    needs_multipart_form = False
    
    class Meta:
        #label = None
        group = ''

    """
    Setting a 'dependencies' list serves as a shortcut for the common 
    case where a complex block type (such as struct, list or stream) 
    relies on one or more inner block objects, and needs to ensure that
    the responses from the 'media' and 'html_declarations' include the 
    relevant declarations for those inner blocks, as well as its own. 
    Specifying these inner block objects in a 'dependencies' list means 
    that the base 'media' and 'html_declarations' methods will return 
    those declarations; the outer block type can then add its own 
    declarations to the list by overriding those methods and using 
    super().
    """
    # shallow copies of dependant blocks
    dependencies = []

    #NB from field ChoiceBlock
    # keep a copy of all kwargs (including our normalised choices list) for deconstruct()
    # Note: we omit the `widget` kwarg, as widgets do not provide a serialization method
    # for migrations, and they are unlikely to be useful within the frozen ORM anyhow
        
    def __new__(cls, *args, **kwargs):
        # adapted from django.utils.deconstruct.deconstructible; capture the arguments
        # so that we can return them in the 'deconstruct' method
        obj = super(Block, cls).__new__(cls)
        obj._constructor_args = (args, kwargs)
        return obj

    def all_blocks(self):
        '''
        Return a list consisting of self and all block objects that are 
        direct or indirect dependencies of this block
        '''
        result = [self]
        for dep in self.dependencies:
            result.extend(dep.all_blocks())
        return result

    def all_media(self):
        '''
        Return media from this and composed blocks.
        Data is entries located on the property 'media'.
        Only influencial when wrapped as a widget. 
        ''' 
        media = forms.Media()
        for block in self.all_blocks():
            media += block.media
        return media

    def all_html_declarations(self):
        declarations = filter(bool, [block.html_declarations() for block in self.all_blocks()])
        return mark_safe('\n'.join(declarations))

    def __init__(self, label='', css_classes=None, **kwargs):
        self.css_classes = [] if css_classes is None else css_classes.copy()

        self.meta = self._meta_class()

        for attr, value in kwargs.items():
            setattr(self.meta, attr, value)

        # Increase the creation counter, and save our local copy.
        self.creation_counter = Block.creation_counter
        Block.creation_counter += 1
        self.definition_prefix = 'blockdef-%d' % self.creation_counter

        #self.label = self.meta.label or ''
        # If the user expresses a preference, push it in regardless
        # of auto generation
        if label:
            self.label = label

    def set_name(self, name):
        #NB Can be called in __new__ or __init__, depening on 
        # declaration style
        self.name = name
        #if not self.meta.label:
        if not self.label:
            self.label = capfirst(force_str(name).replace('_', ' '))

    @property
    def media(self):
        return forms.Media()

    def html_declarations(self):
        """
        Return an HTML fragment to be rendered on the form page 
        This will contain HTML templates for inputs, so they can be 
        dynamically added to the page. 
        
        They should only occur once per block definition. For example, 
        the block definition
        
            ListBlock(label="Shopping list", CharBlock(label="Product"))
        
        needs to output an HTML template containing the HTML for a 
        'product' text input. This template block should only occur 
        once, even if there are multiple 'shopping list'
        blocks on the page.

        Any element IDs used in this HTML fragment must begin with 
        definition_prefix (more precisely, they must either be 
        definition_prefix itself, or begin with definition_prefix
        followed by a '-' character) e.g.

            <script type="text/template" id="blockdef-14-newmember-decimal">
            </script>
        """
        return ''

    def js_initializer(self):
        """
        Returns a Javascript expression string, or None. 
        This returns a Javascript initializer function named as the 
        block class e.g.
        
        StreamBlock({
        'definition_prefix' : ('blockdef-N'),
            'childBlocks': ([ {name:'subBlock', initializer:''} ])
        })
        
        Note the function takes a map of data.
        
        The function is composed recursively through the block structure.
        So the parent block of this block (or the top-level page code) 
        should ensure this expression is evaluated once only (the 
        resulting initializer function can and will be called as many 
        times as there are instances of this block, though.)
        """
        return None

    def render_form(self, value, prefix='', errors=None):
        """
        Render the HTML for this block with 'value' as its content.
        """
        # This is passed through BoundBlock, when used as a Widget.
        # It is used to construct the output, but as one element that 
        # may include scripts and block templates.
        # On field blocks if will call a render() on the widget.
        raise NotImplementedError('%s.render_form' % self.__class__)

    def value_from_datadict(self, data, files, prefix):
        raise NotImplementedError('%s.value_from_datadict' % self.__class__)

    def value_omitted_from_data(self, data, files, name):
        """
        Used only for top-level blocks wrapped by BlockWidget (i.e.: typically only StreamBlock)
        to inform ModelForm logic on Django >=1.10.2 whether the field is absent from the form
        submission (and should therefore revert to the field default).
        """
        return name not in data

    def bind(self, value, prefix=None, errors=None):
        """
        Return a BoundBlock which represents the association of this block definition with a value
        and a prefix (and optionally, a ValidationError to be rendered).
        BoundBlock primarily exists as a convenience to allow rendering within templates:
        bound_block.render() rather than blockdef.render(value, prefix) which can't be called from
        within a template.
        """
        return BoundBlock(self, value, prefix=prefix, errors=errors)

    def get_default(self):
        """
        Return this block's default value (conventionally found in self.meta.default),
        converted to the value type expected by this block. This caters for the case
        where that value type is not something that can be expressed statically at
        model definition time (e.g. something like StructValue which incorporates a
        pointer back to the block definition object).
        """
        return self.meta.default

    def prototype_block(self):
        """
        Return a BoundBlock that can be used as a basis for new empty block instances to be added on the fly
        (new list items, for example). This will have a prefix of '__PREFIX__' (to be dynamically replaced with
        a real prefix when it's inserted into the page) and a value equal to the block's default value.
        """
        return self.bind(self.get_default(), '__PREFIX__')

    def clean(self, value):
        """
        Validate value and return a cleaned version.
        Present in models, model-fields, forms and form-fields. The 
        version used here is like a form-field. In collection blocks
        the value is hacked up and distributed to child blocks. In 
        field blocks the method is delegated to the wrapped field. 
        
        All the clean machinery can throw a ValidationError if 
        validation fails. Thrown ValidationError instance are passed to 
        render() to display the overall error message. Since blacks and 
        their values are nested, the ValidationError must therefore 
        include all detail necessary, such as identifying the specific 
        child block(s)  (It is suggested that you use the 'params' 
        attribute for this; using error_list / error_dict is unreliable 
        because Django tends to hack around with these when nested).
        """
        return value

    def to_python(self, value):
        """
        Convert a JSON-serialisable value to a Python form.
        This is a model-field and form-field method. In forms it's
        called before clean(). In models usually does some light 
        formatting, and conversion to special types such as datetimes. 
        In forms it may do some prep for display, such as localisation
        
        Used in the rest of the block API and within front-end 
        templates.
        
        In simple cases this might be the value itself; 
        alternatively, it might be a 'smart' version of the value 
        which behaves mostly like the original value but provides a 
        native HTML rendering when inserted into a template; or it
        might be something totally different (e.g. an image chooser 
        will use the image ID as the clean value, and turn this back 
        into an actual image object).
        """
        return value

    def get_prep_value(self, value):
        """
        Convert the Python value into JSON-serialisable form.
        
        This is an action from model-fields, where it is called 
        by a specialised get_db_prep_save() and at base will resolve 
        Promises. Confusingly, it may sometimes call to_python(). It's
        used for making the value to save to the DB. 
        JSON can soak up many datatypes, so code can be simple here.
        The reverse of to_python;().
        """
        #? What supplies Promises, anyhow
        return value
        
    # def pre_save_hook(self, field_value, value):
        # '''
        # Reun actions prior to saving.
        # pre_save is model-field action. It has no delecation into 
        # form-fields, having cleaned values. However, a block may want to
        # perform some pre_save action, so it is here delegated into 
        # blocks.
        # '''
        # # There is little point in passing the instance, as the 
        # # model-field action does, and the block is available as self, 
        # # for attribute data. value is the main interest.
        # # No return, either, as we are not interested in modifying 
        # # values. This method can't reach main save value, the JSON
        # # string.
        # pass
                
    def render_css_classes(self, context):
        '''
        Basic render of CSS classes.
        A fwidget-like action, like 'attrs' on form-widgets. Used where 
        not using a template e.g. in default_render(). 
        '''
        a = context.get('css_classes')
        if (not(a)):
            return ''
        return mark_safe(' class="{}"'.format(' '.join(a)))
    
    def get_context(self, value, parent_context=None):
        """
        Return a dict of context variables.
        A widget action. Derived from the block value and combined with 
        the parent_context. Used as the template context when rendering 
        this value through a template.
        """

        context = parent_context or {}
        context.update({
            'self': value,
            'css_classes': self.css_classes,
            self.TEMPLATE_VAR: value,
        })
        return context

    def get_template(self, context=None):
        """
        Return the template to use for rendering the block if specified on meta class.
        This extraction was added to make dynamic templates possible if you override this method
        """
        return getattr(self.meta, 'template', None)

    def render(self, value, context=None):
        """
        Return a text rendering of 'value', suitable for display on 
        templates. 
        A form-widget action. By default, this will use a template (with
        the passed context, supplemented by the result of get_context) 
        if a 'template' property is specified on the block, and fall 
        back on ender_basic otherwise.
        """
        template = self.get_template(context=context)
        
        if context is None:
            new_context = self.get_context(value)
        else:
            new_context = self.get_context(value, parent_context=dict(context))
            
        if not template:
            return self.render_basic(value, context=new_context)
            
        return mark_safe(render_to_string(template, new_context))

    def render_basic(self, value, context=None):
        """
        Return a text rendering of value. 
        This is for display on templates. render() will fall back on
        this if the block does not define a 'template' property.
        """
        return force_str(value)

    def get_searchable_content(self, value):
        """
        Returns content that may be used in a search engine.
        This recurses through child blocks. It should return text 
        content, and ignore blocks containing small or specialised data 
        such as dates, numbers, URLs etc. 
        It is available on StreamField, and this is the recusive method
        that implements it.
        """
        return []

    def check(self, **kwargs):
        """
        Hook for the Django system checks framework -
        returns a list of django.core.checks.Error objects indicating validity errors in the block
        """
        return []

    def _check_name(self, **kwargs):
        """
        Helper method called by container blocks as part of the system checks framework,
        to validate that this block's name is a valid identifier.
        (Not called universally, because not all blocks need names)
        """
        errors = []
        if not self.name:
            errors.append(checks.Error(
                "Block name %r is invalid" % self.name,
                hint="Block name cannot be empty",
                obj=kwargs.get('field', self),
                id='streamfield.block.E001',
            ))

        if ' ' in self.name:
            errors.append(checks.Error(
                "Block name %r is invalid" % self.name,
                hint="Block names cannot contain spaces",
                obj=kwargs.get('field', self),
                id='streamfield.block.E001',
            ))

        if '-' in self.name:
            errors.append(checks.Error(
                "Block name %r is invalid" % self.name,
                "Block names cannot contain dashes",
                obj=kwargs.get('field', self),
                id='streamfield.block.E001',
            ))

        if self.name and self.name[0].isdigit():
            errors.append(checks.Error(
                "Block name %r is invalid" % self.name,
                "Block names cannot begin with a digit",
                obj=kwargs.get('field', self),
                id='streamfield.block.E001',
            ))

        return errors

    def id_for_label(self, prefix):
        """
        An ID to be used as the 'for' attribute of <label> elements.
        This is a widget  action.When the given field prefix is in use. 
        Return None if no 'for' attribute should be used.
        """
        return None

    @property
    def required(self):
        """
        Flag used to determine whether labels for this block should display a 'required' marks.
        False by default, since Block does not provide any validation of its own - it's up to subclasses
        to define what required-ness means.
        """
        return False

    def deconstruct(self):
        # adapted from django.utils.deconstruct.deconstructible
        module_name = self.__module__
        name = self.__class__.__name__

        # Make sure it's actually there and not an inner class
        module = import_module(module_name)
        if not hasattr(module, name):
            raise ValueError(
                "Could not find object %s in %s.\n"
                "Please note that you cannot serialize things like inner "
                "classes. Please move the object into the main module "
                "body to use migrations.\n"
                % (name, module_name))

        # if the module defines a DECONSTRUCT_ALIASES dictionary, see if the class has an entry in there;
        # if so, use that instead of the real path
        try:
            path = module.DECONSTRUCT_ALIASES[self.__class__]
        except (AttributeError, KeyError):
            path = '%s.%s' % (module_name, name)

        return (
            path,
            self._constructor_args[0],
            self._constructor_args[1],
        )

    def __eq__(self, other):
        """
        Implement equality on block objects so that two blocks with matching definitions are considered
        equal. (Block objects are intended to be immutable with the exception of set_name(), so here
        'matching definitions' means that both the 'name' property and the constructor args/kwargs - as
        captured in _constructor_args - are equal on both blocks.)

        This was originally necessary as a workaround for https://code.djangoproject.com/ticket/24340
        in Django <1.9; the deep_deconstruct function used to detect changes for migrations did not
        recurse into the block lists, and left them as Block instances. This __eq__ method therefore
        came into play when identifying changes within migrations.

        As of Django >=1.9, this *probably* isn't required any more. However, it may be useful in
        future as a way of identifying blocks that can be re-used within StreamField definitions
        (https://github.com/wagtail/wagtail/issues/4298#issuecomment-367656028).
        """

        if not isinstance(other, Block):
            # if the other object isn't a block at all, it clearly isn't equal.
            return False

            # Note that we do not require the two blocks to be of the exact same class. This is because
            # we may wish the following blocks to be considered equal:
            #
            # class FooBlock(StructBlock):
            #     first_name = CharBlock()
            #     surname = CharBlock()
            #
            # class BarBlock(StructBlock):
            #     first_name = CharBlock()
            #     surname = CharBlock()
            #
            # FooBlock() == BarBlock() == StructBlock([('first_name', CharBlock()), ('surname': CharBlock())])
            #
            # For this to work, StructBlock will need to ensure that 'deconstruct' returns the same signature
            # in all of these cases, including reporting StructBlock as the path:
            #
            # FooBlock().deconstruct() == (
            #     'wagtail.core.blocks.StructBlock',
            #     [('first_name', CharBlock()), ('surname': CharBlock())],
            #     {}
            # )
            #
            # This has the bonus side effect that the StructBlock field definition gets frozen into
            # the migration, rather than leaving the migration vulnerable to future changes to FooBlock / BarBlock
            # in models.py.

        return (self.name == other.name) and (self.deconstruct() == other.deconstruct())



                
class BoundBlock:
    '''
    Binding to pull a block definition together with other data.
    The other data includes a value and associated errors.
    This is unlike a django.form BoundBlock. It ties data together,
    but the main functionality is rendering, which a form BoundBlock
    knows nothing about. 
    '''
    def __init__(self, block, value, prefix=None, errors=None):
        self.block = block
        self.value = value
        self.prefix = prefix
        self.errors = errors

    def render_form(self):
        return self.block.render_form(self.value, self.prefix, errors=self.errors)

    def render(self, context=None):
        return self.block.render(self.value, context=context)

    def render_as_block(self, context=None):
        """
        Alias for render; the include_block tag will specifically check for the presence of a method
        with this name. (This is because {% include_block %} is just as likely to be invoked on a bare
        value as a BoundBlock. If we looked for a `render` method instead, we'd run the risk of finding
        an unrelated method that just happened to have that name - for example, when called on a
        PageChooserBlock it could end up calling page.render.
        """
        return self.render(context=context)
        #return self.block.render(self.value, context=context)

    def id_for_label(self):
        return self.block.id_for_label(self.prefix)

    def __str__(self):
        """Render the value according to the block's native rendering"""
        return self.block.render(self.value)


class DeclarativeSubBlocksMetaclass(BaseBlock):
    """
    Metaclass that collects sub-blocks declared on the base classes.
    (cheerfully stolen from https://github.com/django/django/blob/master/django/forms/forms.py)
    """
    def __new__(mcs, name, bases, attrs):
        # Collect sub-blocks declared on the current class.
        # These are available on the class as `declared_blocks`
        current_blocks = []
        for key, value in list(attrs.items()):
            if isinstance(value, Block):
                current_blocks.append((key, value))
                value.set_name(key)
                attrs.pop(key)
        current_blocks.sort(key=lambda x: x[1].creation_counter)
        attrs['declared_blocks'] = collections.OrderedDict(current_blocks)

        new_class = (super(DeclarativeSubBlocksMetaclass, mcs).__new__(
            mcs, name, bases, attrs))

        # Walk through the MRO, collecting all inherited sub-blocks, to make
        # the combined `base_blocks`.
        base_blocks = collections.OrderedDict()
        for base in reversed(new_class.__mro__):
            # Collect sub-blocks from base class.
            if hasattr(base, 'declared_blocks'):
                base_blocks.update(base.declared_blocks)

            # Field shadowing.
            for attr, value in base.__dict__.items():
                if value is None and attr in base_blocks:
                    base_blocks.pop(attr)
                    
        # assert base blocks are instances
        base_blocks = {n:b() if (not(isinstance(b, Block))) else b for (n,b) in base_blocks.items()}
            
        new_class.base_blocks = base_blocks

        return new_class


# ========================
# django.forms integration
# ========================

class BlockWidget(forms.Widget):
    '''
    Wraps a block as a widget.
    This is so it can be incorporated into a Django form. Typically
    only used on a toplevel block, usually a StreamField.
    This particular implementation expands the parameters of render() 
    to include errors associated with the widget. It must be used with a
    field which binds with 
    stremfield.forms.boundfields.BoundFieldWithErrors (or similar)
    '''
    # A stock Django widget does not handle errors. the form places errors above
    # rows. Errors are held on a form's error dictionary. Calling 
    # is_valid() binds the form fields, then cleans the 
    # form, setting errors on the form's dictionary.
    # The error doesnt get to the field. Django renders row by 
    # row error/widget. 
    # We need to get errors into the widget, then
    # expand the widget definition, like Wagtail, or give up and go for 
    # a more expanded top tevel display. Or could we pass them in via
    # attrs {errors=XXX}?
    # Django binds on is_valid(), but this binds on render()
    def __init__(self, block_def, attrs=None):
        super().__init__(attrs=attrs)
        self.block_def = block_def

    def value_from_datadict(self, data, files, name):
        return self.block_def.value_from_datadict(data, files, name)
        
    def value_omitted_from_data(self, data, files, name):
        return self.block_def.value_omitted_from_data(data, files, name)

    #@property
    #def needs_multipart_form(self):
    #    return any(b.needs_multipart_form for b in self.block_def.all_blocks())

    def render(self, name, value, attrs=None, errors=None, renderer=None):
        '''
        Return data to write for a form input.
        This is a widget override.
        '''
        # a widget uses get_context() to add a context
        # typically, value is {0: ['Enter a valid URL.']} etc.

        bound_block = self.block_def.bind(value, prefix=name, errors=errors)
        
        #NB The widget is a top-level one-off, nothing to do with block
        # level rendering of wrapped form-fields, so following code 
        # runs only once.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                
        html_declarations = bound_block.block.all_html_declarations()
        
        js_initializer = self.block_def.js_initializer()
        if js_initializer:
            js_snippet = """
                <script>
                django.jQuery(function() {
                        var initializer = %s;
                        initializer('%s');
                    })
                </script>
            """ % (js_initializer, name)
        else:
            js_snippet = ''
        return mark_safe(bound_block.render_form() + js_snippet + html_declarations)
        
    @property
    def media(self):
        return self.block_def.all_media() + forms.Media(
            css={'all': [
                'streamfield/css/streamfield.css',
            ]}
        )



from streamfield.forms.boundfields import BoundFieldWithErrors

class BlockField(forms.Field):
    '''
    Wrap a block object to make a form-field.
    Then it can be embedded in a Django form.
    This field returns a special bound-field that can add errors to 
    widget rendering. So it must be used with a widget with expanded
    render() definition e.g.streamfield.blocks.base.BlockWidget
    '''
    # Blocks are nearly form fields anyway. It inherits
    # Field, ensures a widget, then returns the special 
    # BondBlockWithErrors.
    def __init__(self, block=None, **kwargs):
        if block is None:
            raise ImproperlyConfigured("BlockField was not passed a 'block' object")
        self.block = block

        if 'widget' not in kwargs:
            kwargs['widget'] = BlockWidget(block)

        super().__init__(**kwargs)

    def clean(self, value):
        return self.block.clean(value)

    def get_bound_field(self, form, field_name):
        '''
        Return a BoundField instance.
        This will be used when accessing the form field for rendering.
        The bound field ties the form, value and field together.
        This method returns a special boundfield that can add errors
        to widget rendering.
        '''
        return BoundFieldWithErrors(form, self, field_name)



DECONSTRUCT_ALIASES = {
    Block: 'streamfield.blocks.Block',
}
