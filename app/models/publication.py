"""
Publication Model
-----------------
Research publications created and managed by researchers.
Visible to users when status is 'published'.
"""

from app import db


class Publication(db.Model):
    """Publication table - research articles and findings."""

    __tablename__ = 'publication'

    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    content = db.Column(db.Text)
    date_published = db.Column(db.Date)
    status = db.Column(
        db.Enum('draft', 'published', 'hidden', name='publication_status_enum'),
        default='draft'
    )
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(),
                          onupdate=db.func.now())

    # Relationships
    author = db.relationship('User', back_populates='publications')

    def __repr__(self):
        return f'<Publication {self.title[:30]}>'
