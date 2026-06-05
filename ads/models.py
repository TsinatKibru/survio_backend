from django.db import models
from django.utils import timezone


class Ad(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='ads/')
    link_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', '-created_at']

    def __str__(self):
        return self.title


class NewsItem(models.Model):
    TAG_CHOICES = [
        ('standard', 'Regulatory Standard'),
        ('announcement', 'Training / Announcement'),
        ('update', 'System Update'),
    ]

    title = models.CharField(max_length=250)
    tag = models.CharField(max_length=50, choices=TAG_CHOICES, default='standard')
    description = models.TextField()
    link_url = models.URLField(blank=True, help_text="Optional link to full article or document")
    link_text = models.CharField(max_length=100, default="Read More", help_text="Text to display for the link")
    image = models.ImageField(upload_to='news/', blank=True, null=True, help_text="Optional image representing the news item")
    is_published = models.BooleanField(default=True)
    published_date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-published_date', '-created_at']

    def __str__(self):
        return self.title
