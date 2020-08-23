from collections.abc import Sequence

from django import forms
from django.core.exceptions import ValidationError
from django.forms.utils import ErrorList
from django.template.loader import render_to_string
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe

#from wagtail.admin.staticfiles import versioned_static
#from wagtail.core.utils import escape_script
from streamfield.utils import escape_script, versioned_static

from .base import Block
from .utils import js_dict

__all__ = ['ListBlock'] #, 'OrderedListBlock']


class ListValue(Sequence):
    '''
    Qrap the values used in a listblock.
    It acts like a list. It mainly exists because it's __str__()
    methods reference the block methods, meaning even template
    references can be automatically written as HTML lists.
    '''
    #? Don't know why wagtail breaks out __html__()
    def __init__(self, list_block, data):
        self.list_block = list_block
        self.data = data  # a list of data

    def __getitem__(self, i):
        return self.data[i]
        
    def __len__(self):
        return len(self.data)

    def __repr__(self):
        return repr(list(self))

    def render_as_block(self, context=None):
        return self.list_block.render(self, context=context)

    def __str__(self):
        return self.list_block.render(self)
        
        
        
class ListBlock(Block):
    '''
    An extendable collection of similar blocks.
    Compare to StructBlock, a collection of not similar blocks. 
    '''
    # When a listblock renders as a block, it is bound, which calls 
    # a block render, which understands to make an HTML list of it.
    # However, we allow to wrap ListBlock as a model-field. If ListBlock 
    # is wrapped as a model-field, when rendered as a value, none of the
    # above happens. the value is 
    def __init__(self, 
        child_block, 
        element_template="</li{0}</li>",
        wrap_template = "<ul{1}>{0}</ul>", 
        **kwargs
    ):
        super().__init__(**kwargs)
        
        # assert child block is instance
        if (not(isinstance(child_block, Block))):
            child_block = child_block()

        self.child_block = child_block

            
        self.wrap_template = wrap_template
        self.element_template = element_template
        if not hasattr(self.meta, 'default'):
            # Default to a list consisting of one empty (i.e. default-valued) child item
            self.meta.default = [self.child_block.get_default()]

        self.dependencies = [self.child_block]
        self.child_js_initializer = self.child_block.js_initializer()

    @property
    def media(self):
        # Here's something Pythonic, an attribute muddle. 
        # Django documentation blithely states it tries to maintain 
        # order in media statements. In tact, it runs a dependancy 
        # analysis which can scatter media declarations into unexpected
        # orders. Indeed a static/ prefix can influence the order!
        #
        # Not only is this a horror of unpredicatablility, it influences
        # us. Wagtails JS uses it's own admin, and has no need/interest 
        # in namespacing. But all of Django's admin namespaces jQuery 
        # using jquery.init (and the jQuery command |noConflict). The
        # resolutions are to remove the namespacing, easy but 
        # makes a pool of specialist code, or namespace the Wagtail 
        # code.
        # We also want to remove Wagtails cachebusting URLS. They are 
        # valuable code, but are not Django-like, and auto-generate 
        # static/ URLS, leading to worse complexity.
        #
        # But remember what is above, rendering order of JS is 
        # erratic. We need to declare at least 
        # 'admin/js/jquery.init.js' in every media declaration BEFORE
        # any media ineritance or merge, to establish that dependency.
        #
        # Upshot: all Wagtail code has been namespaced. Remove the
        # apparently repetitive statements of Django JS code, and 
        # the Wagtail code may be placed in non-namespaced positions, 
        # resulting in multiple and cascading errors. 
        return forms.Media(js=[
            'admin/js/jquery.init.js',
            'admin/js/core.js',
            'streamfield/js/blocks/sequence.js',
            'streamfield/js/blocks/list.js'
        ])

    def render_list_member(self, value, prefix, index, errors=None):
        """
        Render the HTML for a single list item in the form. This consists of an <li> wrapper, hidden fields
        to manage ID/deleted state, delete/reorder buttons, and the child block's own form HTML.
        """
        child = self.child_block.bind(value, prefix="%s-value" % prefix, errors=errors)
        return render_to_string('streamfield/block_forms/list_member.html', {
            'child_block': self.child_block,
            'prefix': prefix,
            'child': child,
            'index': index,
        })

    def html_declarations(self):
        # generate the HTML to be used when adding a new item to the list;
        # this is the output of render_list_member as rendered with the prefix '__PREFIX__'
        # (to be replaced dynamically when adding the new item) and the child block's default value
        # as its value.
        list_member_html = self.render_list_member(self.child_block.get_default(), '__PREFIX__', '')

        return format_html(
            '<script type="text/template" id="{0}-newmember">{1}</script>',
            self.definition_prefix, mark_safe(escape_script(list_member_html))
        )

    def js_initializer(self):
        opts = {'definitionPrefix': "'%s'" % self.definition_prefix}

        if self.child_js_initializer:
            opts['childInitializer'] = self.child_js_initializer

        return "ListBlock(%s)" % js_dict(opts)

    def render_form(self, value, prefix='', errors=None):
        if errors:
            if len(errors) > 1:
                # We rely on ListBlock.clean throwing a single ValidationError with a specially crafted
                # 'params' attribute that we can pull apart and distribute to the child blocks
                raise TypeError('ListBlock.render_form unexpectedly received multiple errors')
            error_list = errors.as_data()[0].params
        else:
            error_list = None

        # value can be None when a ListBlock is initialising
        if value is None:
            value = []
            
        list_members_html = [
            self.render_list_member(child_val, "%s-%d" % (prefix, i), i,
                                    errors=error_list[i] if error_list else None)
            for (i, child_val) in enumerate(value)
        ]

        return render_to_string('streamfield/block_forms/list.html', {
            'help_text': getattr(self.meta, 'help_text', None),
            'prefix': prefix,
            'list_members_html': list_members_html,
        })

    def value_from_datadict(self, data, files, prefix):
        count = int(data['%s-count' % prefix])
        values_with_indexes = []
        for i in range(0, count):
            if data['%s-%d-deleted' % (prefix, i)]:
                continue
            values_with_indexes.append(
                (
                    int(data['%s-%d-order' % (prefix, i)]),
                    self.child_block.value_from_datadict(data, files, '%s-%d-value' % (prefix, i))
                )
            )

        values_with_indexes.sort()
        return [v for (i, v) in values_with_indexes]

    def value_omitted_from_data(self, data, files, prefix):
        return ('%s-count' % prefix) not in data

    def clean(self, value):
        result = []
        errors = []
        for child_val in value:
            try:
                result.append(self.child_block.clean(child_val))
            except ValidationError as e:
                errors.append(ErrorList([e]))
            else:
                errors.append(None)

        if any(errors):
            # The message here is arbitrary - outputting error messages is delegated to the child blocks,
            # which only involves the 'params' list
            raise ValidationError('Validation error in ListBlock', params=errors)

        return result

    def to_python(self, value):
        return ListValue(self, [
            self.child_block.to_python(item)
            for item in value
            ]
        )
        
    def get_prep_value(self, value):
        # recursively call get_prep_value on children and return as a list
        return [
            self.child_block.get_prep_value(item)
            for item in value
        ]

    # def pre_save_hook(self, field_value, value):
        # for child_val in value:
            # self.child_block.pre_save_hook(field_value, child_val)
                            
    def render_basic(self, value, context=None):
        print("ListBlock render")
        children = format_html_join(
            '\n', self.element_template,
            [
                (self.child_block.render(child_value, context=context),)
                for child_value in value
            ]
        )
        return format_html(self.wrap_template, 
            children, 
            self.render_css_classes(context)
        )

    def get_searchable_content(self, value):
        content = []

        for child_value in value:
            content.extend(self.child_block.get_searchable_content(child_value))

        return content

    def check(self, **kwargs):
        errors = super().check(**kwargs)
        errors.extend(self.child_block.check(**kwargs))
        return errors



DECONSTRUCT_ALIASES = {
    ListBlock: 'streamfield.blocks.ListBlock',
}
