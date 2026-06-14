from django import forms
from .models import ARace, TrainingBlock


class ARaceForm(forms.ModelForm):
    class Meta:
        model = ARace
        fields = ['name', 'date', 'goal_time', 'feeling', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'input input-bordered w-full'}),
            'name': forms.TextInput(attrs={'class': 'input input-bordered w-full'}),
            'goal_time': forms.TimeInput(attrs={'class': 'input input-bordered w-full'}),
            'feeling': forms.Textarea(attrs={'class': 'textarea textarea-bordered w-full', 'rows': 2}),
            'notes': forms.Textarea(attrs={'class': 'textarea textarea-bordered w-full', 'rows': 2}),
        }


class TrainingBlockForm(forms.ModelForm):
    DEFAULT_BLOCK_LENGTH_WEEKS = 16

    class Meta:
        model = TrainingBlock
        fields = ['name', 'start_date', 'end_date']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'input input-bordered w-full', 'placeholder': 'Leave blank to auto-generate from race name'}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'input input-bordered w-full'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'input input-bordered w-full'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_date')
        end = cleaned_data.get('end_date')
        if start and end and end < start:
            raise forms.ValidationError("End date must be after start date.")
        return cleaned_data
