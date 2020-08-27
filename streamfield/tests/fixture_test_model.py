from django.db import models

from streamfield import StreamField
from streamfield.model_fields import ListField, DefinitionListField
from streamfield import blocks
from streamfield.blocks.field_block import DefinitionBlock



class Creepy(models.TextChoices):
    SPIDER = 'SP','Spider'
    ANT = 'AT','Ant'
    PYTHON = 'PY','Python'
    BAT = 'BT','Bat'
    CRICKET = 'CR','Cricket'
    MOTH = 'MO','Moth'
            
class Licence(models.TextChoices):
    NO_RIGHTS = 'CCO', 'Creative Commons ("No Rights Reserved")' 
    CREDIT = 'CC_BY', 'Creative Commons (credit)'
    CREDIT_NC = 'CC_BY-NC-ND', 'Creative Commons (credit, non-commercial, no adaption)'
    NON_EXCLUSIVE = 'NE','Non-exclusive Rights available'
    EXCLUSIVE = 'EX','Exclusive rights available'


class QuoteBlock(blocks.StructBlock):
    quote = blocks.BlockQuoteBlock()
    author = blocks.CharBlock()
    date = blocks.DateBlock()
    licence = blocks.ChoiceBlock(choices=Licence.choices)
        
        
        
from django.forms import widgets
class Page(models.Model):
    title = models.CharField('Title',
        max_length=255,
        null=True,
        blank=True
    )

    # stream = StreamField(
           # block_types = [
                # ('chars', blocks.CharBlock(
                    # required=False,
                    # help_text="A block inputting a short length of chars",
                    # max_length=5,
                    # ),
                # ),
                # ('subtitle', blocks.HeaderBlock()),
                # ('subsubtitle', blocks.HeaderBlock(level=4)),
                # ('quote', blocks.QuoteBlock(
                    # required=False,
                    # ),
                # ), 
                # ('url', blocks.URLBlock),
                # ('relurl', blocks.RelURLBlock),
                # ('email', blocks.EmailBlock(css_classes=['email'])),
                # ('regex', blocks.RegexBlock(regex='\w+')),
                # ('text', blocks.TextBlock()),    
                # ('blockquote', blocks.BlockQuoteBlock()),
                # ('html', blocks.RawHTMLBlock()),
                # ('bool', blocks.BooleanBlock()),
                # ('choice', blocks.ChoiceBlock(choices=Creepy.choices)),
                # ('choices', blocks.MultipleChoiceBlock(choices=Creepy.choices)),
                # ('integer', blocks.IntegerBlock()),
                # ('decimal', blocks.DecimalBlock()),
                # ('float', blocks.FloatBlock()),
                # ('date', blocks.DateBlock()),
                # ('time', blocks.TimeBlock()),
                # ('datetime', blocks.DateTimeBlock(css_classes=['datetime'])),
                # ('rawanchor', blocks.RawAnchorBlock()),
                # ('anchor', blocks.AnchorBlock()),
            # ],
        # verbose_name="Streamfield field block sampler"
    # )

    # stream = StreamField(
            # block_types = [
                # ('chars', blocks.CharBlock(
                    # required=True,
                    # help_text="A block inputting a short length of chars",
                    # max_length=5,
                    # ),
                # ),
            # ],
        # verbose_name="Streamfield with CharBlock attributes"
    # )

    # stream = StreamField(
        # block_types = [
            # ('subtitle', blocks.HeaderBlock()),
            # ('subsubtitle', blocks.HeaderBlock(level=4)),
            # ('text', blocks.TextBlock(placeholder='qzapp')),
            # ('blockquote', blocks.BlockQuoteBlock),
            # ('quote', QuoteBlock()),
            # ('anchor', blocks.AnchorBlock),
            # ('date', blocks.DateBlock),
        # ],
        # verbose_name="Streamfield for text content"
    # )

    # stream = ListField(
        # html_ordered = True,
        # verbose_name="ListField ordered"    
    # ) 
    
    # stream = DefinitionListField(
        # definition_block = blocks.RawAnchorBlock,
        # verbose_name="DefinitionListField for raw web links"    
    # ) 

    # stream = StreamField(
        # block_types = [
            # ('subtitle', blocks.CharBlock()),
            # ('text', blocks.TextBlock()),
            # ('quote', QuoteBlock()),
        # ],
        # verbose_name="StreamField with StructBlock quotes "
    # )
