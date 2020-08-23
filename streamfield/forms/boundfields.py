from django.forms.boundfield import BoundField



class BoundFieldWithErrors(BoundField):
    '''
    Binds the form and value to a widget, but also the error list.
    Like a usual BoundForm, but passing the error list to the widget is 
    new.
    '''
    def css_classes(self, extra_classes=None):
        r = super().css_classes(extra_classes=None)
        print('BoundFieldWithErrors css classes')
        print(str(r))
        return r

    # def value(self):
        # """
        # Return the value for this BoundField, using the initial value if
        # the form is not bound or the data otherwise.
        # """
        # data = self.initial
        # if self.form.is_bound:
            # data = self.field.bound_data(self.data, data)
        # return self.field.prepare_value(data)
        
    def as_widget(self, widget=None, attrs=None, only_initial=False):
        """
        Render the field by rendering the passed widget, adding any HTML
        attributes passed as attrs. If a widget isn't specified, use the
        field's default widget.
        """
        widget = widget or self.field.widget
        if self.field.localize:
            widget.is_localized = True
            
        # Tweaky. Calling the 'errors' property may cause a full_clean
        # with no protection against this completed. There's no
        # code guarentee.
        errors = None
        if (self.form.is_bound and (self.form._errors is not None)):
            errors = self.form._errors.get(self.name)
        attrs = attrs or {}
        attrs = self.build_widget_attrs(attrs, widget)
        if self.auto_id and 'id' not in widget.attrs:
            attrs.setdefault('id', self.html_initial_id if only_initial else self.auto_id)
        return widget.render(
            name=self.html_initial_name if only_initial else self.html_name,
            value=self.value(),
            attrs=attrs,
            errors=errors,
            renderer=self.form.renderer,
        )
