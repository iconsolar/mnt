"""Home, my profile and the language choice."""
from __future__ import annotations

from flask import Blueprint, redirect, render_template, request, session as cookie, url_for
from flask_login import current_user

from ..db import session
from ..people.access import signed_in
from ..people.registry import LANGUAGES, SCREENS

bp = Blueprint("web", __name__)

# Screens that have a page so far. Later steps add theirs here.
_PAGES = {"people": "people.index"}


@bp.get("/")
@signed_in
def home():
    pages = [
        {"name_key": s.name_key, "url": url_for(_PAGES[s.code])}
        for s in SCREENS
        if s.code in _PAGES and current_user.can(s.code)
    ]
    return render_template("home.html", pages=pages)


@bp.route("/profile", methods=["GET", "POST"])
@signed_in
def profile():
    if request.method == "POST":
        language = request.form.get("language")
        if language in LANGUAGES:
            current_user.language = language
            session.commit()
        return redirect(url_for("web.profile"))
    return render_template("profile.html", languages=LANGUAGES)


@bp.post("/language")
def set_language():
    """The sign-in page's language choice, before anyone is signed in."""
    language = request.form.get("language")
    if language in LANGUAGES:
        cookie["lang"] = language
    return redirect(url_for("auth.login"))
