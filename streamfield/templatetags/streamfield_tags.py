from django import template
from django.utils.text import (
    get_valid_filename, 
    camel_case_to_spaces
    )
from django.utils.safestring import mark_safe
from django.template import loader

register = template.Library()


# @register.simple_tag
# def format_field(field):
    # widget_name = get_widget_name(field)

    # t = loader.select_template([
            #'streamblocks/admin/fields/%s.html' % widget_name,
            # 'streamfield/admin/fields/%s.html' % widget_name,
            # 'streamfield/admin/fields/default.html'
        # ])

    # if widget_name == 'select':
        
        # # ForeignKey Field
        # if hasattr(field.field, '_queryset'):
            # for obj in field.field._queryset:
                # if obj.pk == field.value():
                    # field.obj = obj

        # # CharField choices
        # if hasattr(field.field, '_choices'):
            # for obj in field.field._choices:
                # if obj[0] == field.value():
                    # field.obj = obj[1]
        

    # return mark_safe(t.render(dict(
        # field=field
        # )))

# def get_widget_name(field):
    # return get_valid_filename(
                # camel_case_to_spaces(field.field.widget.__class__.__name__)
                # )

# @register.simple_tag
# def stream_render(stream_obj, **kwargs):
    # return stream_obj._render(kwargs)

#############################################

class IncludeBlockNode(template.Node):
    def __init__(self, block_var, extra_context, use_parent_context):
        self.block_var = block_var
        self.extra_context = extra_context
        self.use_parent_context = use_parent_context

    def render(self, context):
        try:
            value = self.block_var.resolve(context)
        except template.VariableDoesNotExist:
            return ''

        if hasattr(value, 'render_as_block'):
            if self.use_parent_context:
                new_context = context.flatten()
            else:
                new_context = {}

            if self.extra_context:
                for var_name, var_value in self.extra_context.items():
                    new_context[var_name] = var_value.resolve(context)

            return value.render_as_block(context=new_context)
        else:
            return force_str(value)

@register.tag
def streamfield(parser, token):
    """
    Render the passed item of StreamField content, passing the current template context
    if there's an identifiable way of doing so (i.e. if it has a `render_as_block` method).
    """
    tokens = token.split_contents()

    try:
        tag_name = tokens.pop(0)
        block_var_token = tokens.pop(0)
    except IndexError:
        raise template.TemplateSyntaxError("%r tag requires at least one argument" % tag_name)

    block_var = parser.compile_filter(block_var_token)

    if tokens and tokens[0] == 'with':
        tokens.pop(0)
        extra_context = token_kwargs(tokens, parser)
    else:
        extra_context = None

    use_parent_context = True
    if tokens and tokens[0] == 'only':
        tokens.pop(0)
        use_parent_context = False

    if tokens:
        raise template.TemplateSyntaxError("Unexpected argument to %r tag: %r" % (tag_name, tokens[0]))

    return IncludeBlockNode(block_var, extra_context, use_parent_context)
