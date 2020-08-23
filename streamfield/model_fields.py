import json
from django.db import models
from django.core import checks, exceptions, validators
from django.core.serializers.json import DjangoJSONEncoder
from streamfield.blocks import (
    StreamValue, 
    BlockField,
    Block, 
    StreamBlock,
    ListBlock,
    CharBlock
)



        
# https://github.com/django/django/blob/64200c14e0072ba0ffef86da46b2ea82fd1e019a/django/db/models/fields/subclassing.py#L31-L44
class Creator:
    """
    A placeholder class that provides a way to set the attribute on the model.
    """
    def __init__(self, field):
        self.field = field

    def __get__(self, obj, type=None):
        if obj is None:
            return self
        return obj.__dict__[self.field.name]

    def __set__(self, obj, value):
        obj.__dict__[self.field.name] = self.field.to_python(value)



class StreamFieldBase(models.Field):
    
    def get_internal_type(self):
        return 'TextField'
     
    #def get_prep_value(self, value):
    #    return json.dumps(self.root_block.get_prep_value(value), cls=DjangoJSONEncoder)

    def from_db_value(self, value, expression, connection):
        return self.to_python(value)

    def value_to_string(self, obj):
        value = self.value_from_object(obj)
        return self.get_prep_value(value)
        
        
        
class StreamField(StreamFieldBase):
    # think this renders throug h 
    # streamfield/stream_form/stream.html
    # Which includes a menu
    # streamfield/templates/streamfield/block_forms/stream_menu.html
    # embedded in,
    # streamfield/templates/streamfield/block_forms/ssequence.html
    block_types = []

    def __init__(self, block_types=[], **kwargs):
        super().__init__(**kwargs)
        # if isinstance(block_types, Block):
            # self.stream_block = block_types
        # elif isinstance(block_types, type):
            # self.stream_block = block_types(required=not self.blank)
        # else:
            # self.stream_block = StreamBlock(block_types, required=not self.blank)
        # assert the parameter, if given
        if (block_types):
            self.block_types = block_types
        self.block_types = list(self.block_types)
        self.root_block = StreamBlock(block_types, required=not self.blank)
            
    #def get_internal_type(self):
    #    return 'TextField'

    def deconstruct(self):
        # Deconstruct will find all the usaul model field attributes.
        # It will also succeed in deconstructing block classes
        # returned to one of it's attributes.
        # But it will fail to note custom parameters.
        name, path, args, kwargs = super().deconstruct()
        block_types = list(self.root_block.child_blocks.items())
        kwargs['block_types'] = block_types
        return name, path, args, kwargs

    def to_python(self, value):
        if value is None or value == '':
            return StreamValue(self.root_block, [])
        elif isinstance(value, StreamValue):
            return value
        elif isinstance(value, str):
            try:
                unpacked_value = json.loads(value)
            except ValueError:
                # value is not valid JSON; most likely, this field was previously a
                # rich text field before being migrated to StreamField, and the data
                # was left intact in the migration. Return an empty stream instead
                # (but keep the raw text available as an attribute, so that it can be
                # used to migrate that data to StreamField)
                return StreamValue(self.root_block, [], raw_text=value)

            if unpacked_value is None:
                # we get here if value is the literal string 'null'. This should probably
                # never happen if the rest of the (de)serialization code is working properly,
                # but better to handle it just in case...
                return StreamValue(self.root_block, [])

            return self.root_block.to_python(unpacked_value)
        else:
            # See if it looks like the standard non-smart representation of a
            # StreamField value: a list of (block_name, value) tuples
            try:
                [None for (x, y) in value]
            except (TypeError, ValueError):
                # Give up trying to make sense of the value
                raise TypeError("Cannot handle %r (type %r) as a value of StreamField" % (value, type(value)))

            # Test succeeded, so return as a StreamValue-ified version of that value
            return StreamValue(self.root_block, value)
        
    def get_prep_value(self, value):
        if isinstance(value, StreamValue) and not(value) and value.raw_text is not None:
            # An empty StreamValue with a nonempty raw_text attribute should have that
            # raw_text attribute written back to the db. (This is probably only useful
            # for reverse migrations that convert StreamField data back into plain text
            # fields.)
            return value.raw_text
        else:
            return json.dumps(self.root_block.get_prep_value(value), cls=DjangoJSONEncoder)

    #def from_db_value(self, value, expression, connection):
    #    return self.to_python(value)

    def formfield(self, **kwargs):
        '''
        Return  a formfield for use with this model field.
        The default is BlockField with the root_block attribute from 
        this class.
        '''
        #NB dont modify unleess you wish to subvert the entire 
        # streamblocks render chain!
        defaults = {'form_class': BlockField, 'block': self.root_block}
        defaults.update(kwargs)
        return super().formfield(**defaults)

    #def value_to_string(self, obj):
    #    value = self.value_from_object(obj)
    #    return self.get_prep_value(value)

    def get_searchable_content(self, value):
        return self.root_block.get_searchable_content(value)

    def _check_block_spec(self, spec):
        errors = []   

        # test the kv
        #NB init will ensure two values i.e. kv
        label = spec[0]
        block_class = spec[1]
        try:
            if (not(isinstance(block_class, Block))):
                raise TypeError
        except TypeError:
            #NB catch 'not a class' too
            errors.append(
                checks.Error(
                    "'block_types' value must be subclass of blocks.Block. value:'{}'".format(
                        block_class
                    ),
                    id='streamfield.model_fields.E004',
                )
            )
        return errors

    # fails in init before this?
    def _check_block_types(self, **kwargs):
        if (not self.block_types):
            return [
                checks.Warning(
                    "'block_types' attribute is empty, so offers no blocks.",
                    id='streamfield.model_fields.W001',
                )
            ]   
        try:
            block_specs = list(self.block_types)
        except TypeError:
            return [
                checks.Error(
                    "'block_types' structure must cast to a list.",
                    id='streamfield.model_fields.E001',
                )
            ]            
        errors = []
        #for bs in self.block_types:
        #    errors.extend(self._check_block_spec(bs))
        keys = [kv[0] for kv in self.block_types]
        if len(block_specs) != len(set(keys)):
            return [
                checks.Error(
                    "'block_types' value contains duplicate field(s).",
                    id='admin.E002',
                )
            ]
        return errors

    #! to be extended, maybe with checks in other class
    def check(self, **kwargs):
        errors = super().check(**kwargs)
        errors.extend(self._check_block_types(**kwargs))
        errors.extend(self.root_block.check(field=self, **kwargs))
        return errors

    def contribute_to_class(self, cls, name, **kwargs):
        super().contribute_to_class(cls, name, **kwargs)

        # Add Creator descriptor to allow the field to be set from a list or a
        # JSON string.
        setattr(cls, self.name, Creator(self))

      
        
        
class ListFieldBase(StreamFieldBase):

    def __init__(self, 
        child_block,
        element_template,
        wrap_template,
        **kwargs
     ):
        super().__init__(**kwargs)
        #self.block_type = block_type
        #if (block_type):
        #    self.block_type = block_type
            
        self.root_block = ListBlock(
            child_block,
            element_template,
            wrap_template,
            required=not self.blank
         )

    # def deconstruct(self):
        # name, path, args, kwargs = super().deconstruct()
        # kwargs['block_type'] = self.root_block.child_block
        # return name, path, args, kwargs
        
    def to_python(self, value):
        if value is None or value == '':
            return []
        elif isinstance(value, list):
            return value
        elif isinstance(value, str):
            try:
                unpacked_value = json.loads(value)
            except ValueError:
                # value is not valid JSON; most likely, this field was previously a
                # text field before being migrated, and the data
                # was left intact in the migration. Return an empty stream instead
                # (but keep the raw text available as an attribute, so that it can be
                # used to migrate that data to StreamField)
                return [value]

            if unpacked_value is None:
                # we get here if value is the literal string 'null'. This should probably
                # never happen if the rest of the (de)serialization code is working properly,
                # but better to handle it just in case...
                return []

            return self.root_block.to_python(unpacked_value)
        else:
            raise TypeError("Cannot handle %r (type %r) as a value of ListField" % (value, type(value)))

    def get_prep_value(self, value):
        return json.dumps(self.root_block.get_prep_value(value), cls=DjangoJSONEncoder)
 
    def formfield(self, **kwargs):
        '''
        Return  a formfield for use with this model field.
        The default is BlockField with the stream.block attribute from 
        this class.
        '''
        #NB dont modify unleess you wish to subvert the entire 
        # streamblocks render chain!
        defaults = {'form_class': BlockField, 'block': self.root_block}
        defaults.update(kwargs)

        return super().formfield(**defaults)



class ListField(ListFieldBase):
    block_type = CharBlock

    def __init__(self, 
        block_type=CharBlock,
        html_ordered=False,
        **kwargs
     ):
        self.block_type = block_type or self.block_type 
        self.html_ordered = html_ordered
        wrap_template = "<ul>{0}</ul>"
        if (html_ordered):
            wrap_template = "<ol>{0}</ol>"
        super().__init__(
            self.block_type, 
            "<li>{0}</li>", 
            wrap_template, 
            **kwargs
        )

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs['block_type'] = self.root_block.child_block
        if (self.html_ordered):
            kwargs['html_ordered'] = self.html_ordered
        return name, path, args, kwargs



from streamfield.blocks.field_block import DefinitionBlock

class DefinitionListField(ListFieldBase):
    '''
    A field rendering as an HTML definition list.
    term_block_type
    definition_block_type
        block to be used as definition
    '''
    term_block = CharBlock
    definition_block = CharBlock
        
    def __init__(self, 
        term_block = CharBlock,
        definition_block = CharBlock,
        **kwargs
     ): 
        self.term_block = term_block or self.term_block
        self.definition_block = definition_block or self.definition_block
        super().__init__(
            DefinitionBlock(self.term_block, self.definition_block),
            "{0}",
            "<dl>{0}</dl>",
            **kwargs
        )        
  
    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs['term_block'] = self.term_block
        kwargs['definition_block'] = self.definition_block
        return name, path, args, kwargs
