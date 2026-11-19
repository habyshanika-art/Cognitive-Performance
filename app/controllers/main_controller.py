"""
Main Controller
---------------
Handles public routes: welcome/landing page and static content sections.
"""

from flask import Blueprint, render_template
from app.models.publication import Publication

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """Landing page with hero, features, publications preview, contact."""
    # Show latest 3 published articles on landing page
    publications = Publication.query.filter_by(status='published')\
        .order_by(Publication.date_published.desc())\
        .limit(3).all()
    return render_template('main/index.html', publications=publications)


@main_bp.route('/about')
def about():
    """About the system page."""
    return render_template('main/about.html')


@main_bp.route('/publications')
def publications():
    """Public list of published research articles."""
    articles = Publication.query.filter_by(status='published')\
        .order_by(Publication.date_published.desc()).all()
    return render_template('main/publications.html', articles=articles)


@main_bp.route('/publications/<int:pub_id>')
def publication_detail(pub_id):
    """Read a single published research article."""
    article = Publication.query.filter_by(id=pub_id, status='published').first_or_404()
    return render_template('main/publication_detail.html', article=article)
