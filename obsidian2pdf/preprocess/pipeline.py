"""Runs transforms in order with fenced and inline code masked out, so
Obsidian syntax inside code samples is never rewritten."""
from __future__ import annotations

import re

from .transforms import (
    FrontmatterStripper,
    IgnoredMediaFilter,
    ImageEmbedResolver,
    LocalMdImageResolver,
    NoteContext,
    NoteEmbedToLink,
    RemoteImageFetcher,
    Transform,
    VideoEmbedToLink,
    WikilinkToText,
)


class Pipeline:
    _FENCED = re.compile(
        r"^(```|~~~)[^\n]*\n.*?^\1[ \t]*$", re.DOTALL | re.MULTILINE
    )
    _INLINE = re.compile(r"`[^`\n]+`")
    _SLOT = re.compile(r"\x00(\d+)\x00")

    def __init__(self, transforms: list[Transform]):
        self.transforms = list(transforms)

    def run(self, text: str, ctx: NoteContext) -> str:
        stash: list[str] = []

        def mask(m: re.Match) -> str:
            stash.append(m.group(0))
            return f"\x00{len(stash) - 1}\x00"

        masked = self._FENCED.sub(mask, text)
        masked = self._INLINE.sub(mask, masked)
        for transform in self.transforms:
            masked = transform.apply(masked, ctx)
        return self._SLOT.sub(lambda m: stash[int(m.group(1))], masked)


def default_pipeline() -> Pipeline:
    """Order matters: filter ignored media before resolvers; classify video
    URLs before the remote fetcher; wiki image embeds before generic embeds."""
    return Pipeline([
        FrontmatterStripper(),
        IgnoredMediaFilter(),
        VideoEmbedToLink(),
        ImageEmbedResolver(),
        NoteEmbedToLink(),
        WikilinkToText(),
        LocalMdImageResolver(),
        RemoteImageFetcher(),
    ])
