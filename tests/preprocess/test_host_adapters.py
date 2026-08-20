"""Tests for obsidian2pdf.preprocess.host_adapters."""
from __future__ import annotations

from obsidian2pdf.preprocess.host_adapters import (
    GenericAdapter,
    ImgurAdapter,
    resolve_fetch_target,
)


def test_imgur_adapter_matches_direct_link():
    assert ImgurAdapter().matches("https://i.imgur.com/FgE3Y5N.png") is True


def test_imgur_adapter_does_not_match_other_hosts():
    assert ImgurAdapter().matches("https://example.com/img.png") is False


def test_imgur_adapter_rewrites_to_download_endpoint_with_page_referer():
    url, referer = ImgurAdapter().fetch_target("https://i.imgur.com/FgE3Y5N.png")
    assert url == "https://imgur.com/download/FgE3Y5N/"
    assert referer == "https://imgur.com/FgE3Y5N"


def test_generic_adapter_matches_anything():
    assert GenericAdapter().matches("https://anything.example.com/x") is True


def test_generic_adapter_strips_one_subdomain_for_referer():
    url, referer = GenericAdapter().fetch_target("https://cdn.example.com/img.png")
    assert url == "https://cdn.example.com/img.png"  # URL unchanged
    assert referer == "https://example.com/"


def test_generic_adapter_bare_domain_referer_is_itself():
    url, referer = GenericAdapter().fetch_target("https://example.com/img.png")
    assert referer == "https://example.com/"


def test_resolve_fetch_target_picks_imgur_adapter():
    url, referer = resolve_fetch_target("https://i.imgur.com/FgE3Y5N.png")
    assert url == "https://imgur.com/download/FgE3Y5N/"


def test_resolve_fetch_target_falls_back_to_generic():
    url, referer = resolve_fetch_target("https://cdn.example.com/img.png")
    assert url == "https://cdn.example.com/img.png"
    assert referer == "https://example.com/"
