from streamfield import blocks
from django.test import TestCase


# ./manage.py test streamfield.tests.test_blocks
class TestBlock(TestCase):
    '''
    Block can be passed by itself. Not a lot to test which makes 
    significant, though.
    '''
    def setUp(self):
        self.block = blocks.Block()

    def test_all_blocks(self):
        self.assertEqual(self.block.all_blocks(), [self.block])
        
    def test_bind(self):
        bb = self.block.bind(5, prefix=None, errors=None)
        self.assertEqual(type(bb), blocks.BoundBlock)
        self.assertEqual(bb.value, 5)

    def test_get_default(self):
        with self.assertRaises(AttributeError):
            self.block.get_default()


# FIELD_BLOCKS = [
    # CharBlock, URLBlock, 
    # #RichTextBlock, 
    # RawHTMLBlock, ChooserBlock,
    # #PageChooserBlock, 
    # TextBlock, BooleanBlock, DateBlock, TimeBlock,
    # DateTimeBlock, ChoiceBlock, EmailBlock, IntegerBlock, FloatBlock,
    # DecimalBlock, RegexBlock, BlockQuoteBlock
    # ]

#for b in blocks.block_classes:

# class TestFieldBlocks(TestCase):

   # # def setUp(self):
   # #     self.block = blocks.CharBlock()

    # for b, data in blocks.FIELD_BLOCKS.items:
        # value = data[0]
        # value = data[0]
        
        # b.to_python(value)


class TestCharBlock(TestCase):
        
    def test_render(self):
        block = blocks.CharBlock()
        value = 'off'
        r = block.render(value, context=None)
        self.assertHTMLEqual(r, 'off')
            
class TestListBlock(TestCase):

    def setUp(self):
        self.block = blocks.ListBlock(blocks.CharBlock)
        self.maxDiff=None

    def test_render_list_member(self):
        value = ['hi', 'ho', 'off', 'to', 'work']
        r = self.block.render(value, context=None)
        self.assertHTMLEqual(r, '<ul><li>hi</li><li>ho</li><li>off</li><li>to</li><li>work</li></ul>')

    #def test_to_python(self):
    #    self.assertEqual(self.block.to_python(), [self.block])

