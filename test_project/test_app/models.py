from django.db import models
from django.contrib.contenttypes.generic import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from denorm import denormalized, depend_on_related, CountField

class Tag(models.Model):
    name = models.CharField(max_length=255)

    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

class TaggedModel(models.Model):
    tags = GenericRelation(Tag)

    @denormalized(models.TextField)
    @depend_on_related(Tag)
    def tags_string(self):
        return ', '.join(sorted([t.name for t in self.tags.all()]))

    class Meta:
        abstract = True

class Forum(TaggedModel):

    title = models.CharField(max_length=255)

    # Simple count() aggregate
    post_count = CountField('post_set')

    @denormalized(models.CharField,max_length=255)
    @depend_on_related('Post')
    def author_names(self):
        return ', '.join((m.author_name for m in self.post_set.all()))

    @denormalized(models.ManyToManyField,'Member',null=True,blank=True)
    @depend_on_related('Post')
    def authors(self):
        return [m.author for m in self.post_set.all() if m.author]

    # let's say this forums supports subforums, sub-subforums and so forth
    # so we can test depend_on_related('self') (for tree structures).
    parent_forum = models.ForeignKey('self',blank=True,null=True)

    @denormalized(models.TextField)
    @depend_on_related('self',type='forward')
    def path(self):
        if self.parent_forum:
            return self.parent_forum.path+self.title+'/'
        else:
            return '/'+self.title+'/'


class Post(TaggedModel):

    forum = models.ForeignKey(Forum, blank=True, null=True)
    author = models.ForeignKey('Member', blank=True, null=True)
    response_to = models.ForeignKey('self',blank=True,null=True,related_name='responses')
    title = models.CharField(max_length=255,blank=True)

    attachment_count = CountField('attachment_set')

    # Brings down the forum title
    @denormalized(models.CharField, max_length=255)
    @depend_on_related(Forum)
    def forum_title(self):
        return self.forum.title


    @denormalized(models.CharField, max_length=255)
    @depend_on_related('Member',foreign_key="author")
    def author_name(self):
        if self.author:
            return self.author.name
        else:
            return ''

    @denormalized(models.PositiveIntegerField)
    @depend_on_related('self',type='backward')
    def response_count(self):
        # Work around odd issue during testing with PostgresDB
        if not self.pk:
            return 0
        rcount = self.responses.count()
        rcount += sum((x.response_count for x in self.responses.all()))
        return rcount


class Attachment(models.Model):

    post = models.ForeignKey(Post,blank=True,null=True)

    @denormalized(models.ForeignKey, Forum, blank=True, null=True)
    @depend_on_related(Post)
    def forum(self):
        if self.post and self.post.forum:
            return self.post.forum.pk
        return None


class Member(models.Model):

    first_name = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    bookmarks = models.ManyToManyField('Post',blank=True)

    @denormalized(models.CharField,max_length=255)
    def full_name(self):
        return u"%s %s"% (self.first_name, self.name)

    @denormalized(models.TextField)
    @depend_on_related('Post',foreign_key="bookmarks")
    def bookmark_titles(self):
        if self.id:
            return '\n'.join([p.title for p in self.bookmarks.all()])
