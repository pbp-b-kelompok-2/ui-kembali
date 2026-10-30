from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.core.paginator import Paginator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from pathlib import Path

from .forms import CommentForm, ForumPostForm
from .models import Comment, ForumAttachment, ForumPost
from auth_ssoui.models import Profile


def _save_post_attachments(post, uploads):
    for upload in uploads:
        ForumAttachment.objects.create(post=post, file=upload)


def _attachment_data(file_field):
    name = Path(file_field.name).name
    extension = Path(name).suffix.lstrip(".").upper()
    return {
        "url": file_field.url,
        "name": name,
        "extension": extension,
        "is_image": extension.lower() in {
            "jpg", "jpeg", "png", "gif", "webp", "bmp", "svg", "avif"
        },
        "size": file_field.size,
    }


def _existing_post_attachments(post):
    attachments = []
    if post.attachment:
        legacy_attachment = _attachment_data(post.attachment)
        legacy_attachment["key"] = "legacy"
        attachments.append(legacy_attachment)
    for item in post.attachments.all():
        attachment = _attachment_data(item.file)
        attachment["key"] = str(item.pk)
        attachments.append(attachment)
    return attachments


def _safe_next_redirect(request, fallback_view, **fallback_kwargs):
    next_url = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect(fallback_view, **fallback_kwargs)


def forum_list(request):
    posts = ForumPost.objects.select_related("author", "author__profile").annotate(
        comment_count=Count("comments", distinct=True),
        like_count=Count("liked_by", distinct=True),
    )
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "")
    valid_categories = {value for value, _label in ForumPost.Category.choices}
    if category not in valid_categories:
        category = ""
    selected_sort = request.GET.get("sort", "newest")
    if selected_sort not in {"newest", "oldest", "popular"}:
        selected_sort = "newest"
    selected_mine = request.GET.get("mine") == "1" and request.user.is_authenticated
    selected_saved = request.GET.get("saved") == "1" and request.user.is_authenticated

    category_counts = dict(
        ForumPost.objects.values("category")
        .annotate(total=Count("pk"))
        .values_list("category", "total")
    )
    categories = [
        (value, label, category_counts.get(value, 0))
        for value, label in ForumPost.Category.choices
    ]

    if query:
        posts = posts.filter(Q(title__icontains=query) | Q(content__icontains=query))
    if category:
        posts = posts.filter(category=category)
    if selected_mine:
        posts = posts.filter(author=request.user)
    if selected_saved:
        posts = posts.filter(saved_by=request.user)

    if selected_sort == "oldest":
        posts = posts.order_by("created_at", "pk")
    elif selected_sort == "popular":
        posts = posts.order_by("-like_count", "-created_at", "-pk")
    else:
        posts = posts.order_by("-created_at", "-pk")

    post_count = posts.count()
    page_obj = Paginator(posts, 4).get_page(request.GET.get("page"))
    page_numbers = range(
        max(1, page_obj.number - 2),
        min(page_obj.paginator.num_pages, page_obj.number + 2) + 1,
    )

    return render(
        request,
        "forum/forum_list.html",
        {
            "posts": page_obj,
            "page_obj": page_obj,
            "page_numbers": page_numbers,
            "query": query,
            "selected_category": category,
            "selected_sort": selected_sort,
            "selected_mine": selected_mine,
            "selected_saved": selected_saved,
            "post_count": post_count,
            "categories": categories,
        },
    )


def post_detail(request, pk):
    post = get_object_or_404(
        ForumPost.objects.select_related("author").annotate(
            like_count=Count("liked_by", distinct=True)
        ),
        pk=pk,
    )
    all_comments = list(
        post.comments.select_related("author")
        .annotate(like_count=Count("liked_by", distinct=True))
        .order_by("created_at")
    )
    comments_by_id = {comment.pk: comment for comment in all_comments}
    comments = []
    for comment in all_comments:
        comment.children = []
    for comment in all_comments:
        if comment.parent_id in comments_by_id:
            comments_by_id[comment.parent_id].children.append(comment)
        elif comment.parent_id is None:
            comments.append(comment)

    comment_sort = request.GET.get("comment_sort", "popular")
    if comment_sort not in {"popular", "newest"}:
        comment_sort = "popular"
    if comment_sort == "popular":
        comments.sort(key=lambda item: (item.like_count, item.created_at), reverse=True)
    else:
        comments.reverse()
    try:
        comments_to_show = max(3, min(int(request.GET.get("comments", 3)), 100))
    except (TypeError, ValueError):
        comments_to_show = 3
    total_comments = len(comments)
    comments = comments[:comments_to_show]
    related_posts = (
        ForumPost.objects.filter(category=post.category)
        .exclude(pk=post.pk)
        .order_by("-created_at")[:3]
    )
    author_profile = Profile.objects.filter(user_id=post.author_id).first()
    attachments = [_attachment_data(item.file) for item in post.attachments.all()]
    if post.attachment:
        attachments.insert(0, _attachment_data(post.attachment))
    return render(
        request,
        "forum/forum_detail.html",
        {
            "post": post,
            "comments": comments,
            "comment_sort": comment_sort,
            "comments_to_show": comments_to_show,
            "has_more_comments": total_comments > comments_to_show,
            "related_posts": related_posts,
            "comment_form": CommentForm(),
            "author_profile": author_profile,
            "author_post_count": post.author.forum_posts.count(),
            "is_liked_by_user": request.user.is_authenticated
            and post.liked_by.filter(pk=request.user.pk).exists(),
            "is_saved_by_user": request.user.is_authenticated
            and post.saved_by.filter(pk=request.user.pk).exists(),
            "attachments": attachments,
        },
    )


@login_required(login_url="/auth/login/")
def post_create(request):
    form = ForumPostForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        post = form.save(commit=False)
        post.author = request.user
        post.save()
        _save_post_attachments(post, form.cleaned_data["attachments"])
        return redirect("forum:post_detail", pk=post.pk)
    return render(request, "forum/forum_form.html", {"form": form, "mode": "create"})


@login_required(login_url="/auth/login/")
def post_update(request, pk):
    post = get_object_or_404(ForumPost, pk=pk)
    if post.author_id != request.user.id:
        return HttpResponseForbidden("Kamu hanya bisa mengedit postingan milikmu.")
    form = ForumPostForm(request.POST or None, request.FILES or None, instance=post)
    if request.method == "POST" and form.is_valid():
        form.save()
        _save_post_attachments(post, form.cleaned_data["attachments"])
        return redirect("forum:post_detail", pk=post.pk)
    return render(
        request,
        "forum/forum_form.html",
        {
            "form": form,
            "mode": "edit",
            "post": post,
            "existing_attachments": _existing_post_attachments(post),
        },
    )


@login_required(login_url="/auth/login/")
@require_POST
def attachment_delete(request, post_pk, attachment_key):
    post = get_object_or_404(ForumPost, pk=post_pk)
    if post.author_id != request.user.id:
        return HttpResponseForbidden("Kamu hanya bisa menghapus lampiran postingan milikmu.")

    if attachment_key == "legacy":
        if not post.attachment:
            return JsonResponse({"error": "Lampiran sudah tidak tersedia."}, status=404)
        post.attachment.delete(save=True)
    else:
        attachment = get_object_or_404(
            ForumAttachment,
            pk=attachment_key,
            post=post,
        )
        attachment.file.delete(save=False)
        attachment.delete()

    return JsonResponse({"deleted": True})


@login_required(login_url="/auth/login/")
@require_POST
def post_delete(request, pk):
    post = get_object_or_404(ForumPost, pk=pk)
    if post.author_id != request.user.id:
        return HttpResponseForbidden("Kamu hanya bisa menghapus postingan milikmu.")
    post.delete()
    return redirect("forum:forum_list")


@login_required(login_url="/auth/login/")
@require_POST
def comment_create(request, pk):
    post = get_object_or_404(ForumPost, pk=pk)
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.post = post
        comment.author = request.user
        parent_id = request.POST.get("parent")
        if parent_id:
            comment.parent = get_object_or_404(Comment, pk=parent_id, post=post)
        comment.save()
    return redirect("forum:post_detail", pk=post.pk)


@login_required(login_url="/auth/login/")
@require_POST
def post_like(request, pk):
    post = get_object_or_404(ForumPost, pk=pk)
    if post.liked_by.filter(pk=request.user.pk).exists():
        post.liked_by.remove(request.user)
    else:
        post.liked_by.add(request.user)
    return _safe_next_redirect(request, "forum:post_detail", pk=post.pk)


@login_required(login_url="/auth/login/")
@require_POST
def post_save_toggle(request, pk):
    post = get_object_or_404(ForumPost, pk=pk)
    if post.saved_by.filter(pk=request.user.pk).exists():
        post.saved_by.remove(request.user)
    else:
        post.saved_by.add(request.user)

    return _safe_next_redirect(request, "forum:post_detail", pk=post.pk)


@login_required(login_url="/auth/login/")
@require_POST
def comment_like(request, pk):
    comment = get_object_or_404(Comment, pk=pk)
    if comment.liked_by.filter(pk=request.user.pk).exists():
        comment.liked_by.remove(request.user)
    else:
        comment.liked_by.add(request.user)
    return _safe_next_redirect(request, "forum:post_detail", pk=comment.post_id)

# Create your views here.
