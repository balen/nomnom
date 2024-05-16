from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render, resolve_url
from django_svcs.apps import svcs_from
from nominate.models import Election

from hugopacket.apps import S3Client
from hugopacket.models import ElectionPacket, PacketFile


@dataclass
class PacketFileMetadata:
    last_modified: datetime
    size: int


@dataclass
class PacketFileDisplay:
    packet_file: PacketFile
    metadata: PacketFileMetadata | None

    @property
    def id(self):
        return self.packet_file.id

    def __str__(self):
        return self.packet_file.name


def request_passes_test(
    test_func, login_url=None, redirect_field_name=REDIRECT_FIELD_NAME
):
    """
    Decorator for views that checks that the user passes the given test,
    redirecting to the log-in page if necessary. The test should be a callable
    that takes the user object and returns True if the user passes.
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapper_view(request, *args, **kwargs):
            if test_func(request):
                return view_func(request, *args, **kwargs)
            path = request.build_absolute_uri()
            resolved_login_url = resolve_url(login_url or settings.LOGIN_URL)
            # If the login url is the same scheme and net location then just
            # use the path as the "next" url.
            login_scheme, login_netloc = urlparse(resolved_login_url)[:2]
            current_scheme, current_netloc = urlparse(path)[:2]
            if (not login_scheme or login_scheme == current_scheme) and (
                not login_netloc or login_netloc == current_netloc
            ):
                path = request.get_full_path()
            from django.contrib.auth.views import redirect_to_login

            return redirect_to_login(path, resolved_login_url, redirect_field_name)

        return _wrapper_view

    return decorator


def member_can_vote():
    def test_func(request: HttpRequest) -> bool:
        election_id = request.resolver_match.kwargs.get("election_id")

        if not get_object_or_404(Election, slug=election_id).user_can_vote(
            request.user
        ):
            raise PermissionDenied()

        return True

    return request_passes_test(test_func)


@login_required
@member_can_vote()
def index(request: HttpRequest, election_id: str) -> HttpResponse:
    election = get_object_or_404(Election, slug=election_id)
    packet = get_object_or_404(ElectionPacket, election=election)

    # TODO get the size and modification time of the packet files; we
    # will do this by:
    # - finding all of the prefixes of the packet files (the directory part of their key)
    # - listing all files in those prefixes, storing them keyed by full key
    # - for each packet file, mark it up with the size and modification time by
    #   creating a wrapper object for it that adds those attributes but isn't DB-backed
    all_prefixes = set()

    for packet_file in packet.packetfile_set.all():
        all_prefixes.add(packet_file.s3_object_key.rsplit("/", 1)[0])

    s3 = svcs_from(request).get(S3Client)

    metadata = {}
    for prefix in all_prefixes:
        response = s3.list_objects_v2(Bucket=packet.s3_bucket_name, Prefix=prefix)
        for object in response.get("Contents", []):
            metadata[object["Key"]] = PacketFileMetadata(
                object["LastModified"], object["Size"]
            )

    packet_file_list = [
        PacketFileDisplay(pf, metadata.get(pf.s3_object_key))
        for pf in packet.packetfile_set.all()
    ]

    return render(
        request,
        "hugopacket/index.html",
        {
            "election": election,
            "packet": packet,
            "packet_files": packet_file_list,
        },
    )


@login_required
@member_can_vote()
def download_packet(
    request: HttpRequest, election_id: str, packet_file_id: int
) -> HttpResponse:
    election = get_object_or_404(Election, slug=election_id)
    packet_file = get_object_or_404(PacketFile, pk=packet_file_id)

    # ensure that the packet file belongs to the election
    if packet_file.packet.election != election:
        raise Http404()

    return redirect(packet_file.get_download_url(request))
